import base64
import os
from typing import Any

import requests
from flask import Flask, jsonify, request
from openai import OpenAI

from env_utils import load_env_file

load_env_file()

app = Flask(__name__)
app.json.ensure_ascii = False

MOONSHOT_API_KEY = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY")
DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

AVATAR_PIXEL_PROMPT = (
    "请把图中的人物或主体转换成像素风桌宠形象。"
    "背景必须是单一、纯净、明亮的绿色纯色背景，接近 #00FF00，方便后续抠图。"
    "不要白底，不要透明背景，不要渐变，不要场景，不要地面阴影，不要背景装饰。"
    "主体必须完整保留，边缘清晰，颜色鲜明，输出 512x512。"
)

TAUNT_SYSTEM_PROMPT = (
    "你是一只嘴很毒的桌宠。"
    "只输出一句简短、尖锐、带一点嫌弃感的吐槽，不要解释，不要重复历史表达，控制在 30 字以内。"
)

CHAT_SYSTEM_PROMPT = (
    "你是一只嘴很毒但不失分寸的桌宠监工。"
    "回复要短、直接、有点嫌弃感，控制在 30 字以内。"
)


def _json_error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _moonshot_client() -> OpenAI:
    if not MOONSHOT_API_KEY:
        raise RuntimeError("服务器未配置 MOONSHOT_API_KEY。")
    return OpenAI(api_key=MOONSHOT_API_KEY, base_url=MOONSHOT_BASE_URL)


def _moonshot_chat(messages: list[dict[str, Any]], *, max_tokens: int) -> str:
    client = _moonshot_client()
    try:
        response = client.chat.completions.create(
            model="moonshot-v1-8k",
            max_tokens=max_tokens,
            messages=messages,
        )
    except Exception as exc:
        raise RuntimeError(f"上游聊天服务调用失败：{exc}") from exc
    return (response.choices[0].message.content or "").strip()


def _parse_json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return payload
    return {}


def _extract_generated_image_url(result: dict[str, Any]) -> str:
    try:
        return str(result["output"]["choices"][0]["message"]["content"][0]["image"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"头像服务返回格式异常：{result}") from exc


def _download_image_bytes(url: str) -> bytes:
    try:
        response = requests.get(url, timeout=(20, 60))
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"下载生成图片失败：{exc}") from exc
    return response.content


@app.get("/api/health")
def api_health():
    return jsonify(
        {
            "ok": True,
            "mode": "self_host_open_source",
            "moonshot_configured": bool(MOONSHOT_API_KEY),
            "dashscope_configured": bool(DASHSCOPE_API_KEY),
        }
    )


@app.post("/api/chat")
def api_chat():
    payload = _parse_json_payload()
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return _json_error("messages 必须是数组。", 400)

    try:
        reply = _moonshot_chat(
            [{"role": "system", "content": CHAT_SYSTEM_PROMPT}, *messages],
            max_tokens=100,
        )
    except RuntimeError as exc:
        return _json_error(str(exc), 502)

    return jsonify({"reply": reply})


@app.post("/api/taunt")
def api_taunt():
    payload = _parse_json_payload()
    history = payload.get("history") or []
    if not isinstance(history, list):
        history = []

    history_note = ""
    if history:
        recent = "；".join(str(item) for item in history[-8:])
        history_note = f"\n这些话已经说过了，不能重复：{recent}"

    user_message = (
        f"用户当前窗口是《{payload.get('window_title', '')}》，"
        f"分类是 {payload.get('category_label', '摸鱼')}，"
        f"已经持续 {payload.get('duration_text', '刚刚')}。"
        f"给他一句新的毒舌提醒。{history_note}"
    )

    try:
        reply = _moonshot_chat(
            [
                {"role": "system", "content": TAUNT_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=80,
        )
    except RuntimeError as exc:
        return _json_error(str(exc), 502)

    return jsonify({"reply": reply})


@app.post("/api/avatar")
def api_avatar():
    if not DASHSCOPE_API_KEY:
        return _json_error("服务器未配置 DASHSCOPE_API_KEY。", 500)

    payload = _parse_json_payload()
    image_data = str(payload.get("image", "")).strip()
    if not image_data:
        return _json_error("缺少图片。", 400)

    upstream_payload = {
        "model": "qwen-image-2.0-pro",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": image_data},
                        {"text": AVATAR_PIXEL_PROMPT},
                    ],
                }
            ]
        },
        "parameters": {
            "n": 1,
            "watermark": False,
            "prompt_extend": False,
            "size": "512*512",
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
    }

    try:
        response = requests.post(DASHSCOPE_API_URL, json=upstream_payload, headers=headers, timeout=(20, 120))
    except requests.RequestException as exc:
        return _json_error(f"上游头像服务调用失败：{exc}", 502)

    if response.status_code != 200:
        return _json_error(response.text, response.status_code)

    result = response.json()
    try:
        image_url = _extract_generated_image_url(result)
        image_bytes = _download_image_bytes(image_url)
    except RuntimeError as exc:
        return _json_error(str(exc), 502)

    return jsonify({"image_base64": base64.b64encode(image_bytes).decode("utf-8")})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
