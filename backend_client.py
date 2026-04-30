import base64
import mimetypes
import os
from io import BytesIO

import requests

from env_utils import load_env_file
from monitor import get_category_label

load_env_file()

DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000"
BACKEND_BASE_URL = os.environ.get("PET_BACKEND_URL", DEFAULT_BACKEND_BASE_URL).rstrip("/")
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 120
MAX_RETRIES = 3
RETRY_DELAY = 1.5


def _build_headers() -> dict[str, str]:
    return {"Accept": "application/json"}


def _request_with_retry(method: str, path: str, *, stage: str, **kwargs) -> requests.Response:
    last_error = None
    url = f"{BACKEND_BASE_URL}{path}"
    retriable_statuses = {408, 425, 500, 502, 503, 504}

    headers = dict(kwargs.pop("headers", {}) or {})
    headers = {**_build_headers(), **headers}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.request(
                method,
                url,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                headers=headers,
                **kwargs,
            )

            if resp.status_code == 200:
                return resp

            detail = _extract_error_text(resp)
            if resp.status_code in retriable_statuses and attempt < MAX_RETRIES:
                last_error = RuntimeError(f"{stage}暂时不可用（HTTP {resp.status_code}）：{detail}")
                time.sleep(RETRY_DELAY * attempt)
                continue

            if resp.status_code == 429:
                retry_after = _extract_retry_after(resp)
                wait_note = f" 请在约 {retry_after} 秒后重试。" if retry_after else ""
                raise RuntimeError(f"{stage}失败（HTTP 429）：{detail}{wait_note}")

            raise RuntimeError(f"{stage}失败（HTTP {resp.status_code}）：{detail}")
        except requests.exceptions.RequestException as exc:
            last_error = exc
            if attempt >= MAX_RETRIES:
                break
            time.sleep(RETRY_DELAY * attempt)

    raise RuntimeError(f"{stage}失败，无法连接到服务器：{BACKEND_BASE_URL}") from last_error


def _extract_error_text(resp: requests.Response) -> str:
    try:
        payload = resp.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        detail = str(payload.get("error") or payload.get("message") or "").strip()
        if detail:
            return detail[:240]

    detail = resp.text.strip()
    return (detail[:240] + "...") if len(detail) > 240 else detail


def _extract_retry_after(resp: requests.Response) -> int | None:
    try:
        payload = resp.json()
    except ValueError:
        return None
    value = payload.get("retry_after")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _encode_image(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if not mime or not mime.startswith("image/"):
        raise ValueError(f"不支持的图片格式: {path}")
    with open(path, "rb") as file_obj:
        data = base64.b64encode(file_obj.read()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def _has_real_transparency(img) -> bool:
    if "A" not in img.getbands():
        return False
    alpha_min, _alpha_max = img.getchannel("A").getextrema()
    return alpha_min < 250


def _remove_bg(img):
    from collections import deque

    from PIL import Image

    original = img.convert("RGBA")
    working = original.copy()
    pixels = working.load()
    width, height = working.size
    if height == 0 or width == 0:
        return working

    border_coords = []
    for x in range(width):
        border_coords.append((x, 0))
        if height > 1:
            border_coords.append((x, height - 1))
    for y in range(1, height - 1):
        border_coords.append((0, y))
        if width > 1:
            border_coords.append((width - 1, y))

    border_pixels = [pixels[x, y] for x, y in border_coords]
    opaque_border = [px for px in border_pixels if px[3] > 24]
    transparent_bg = any(px[3] <= 24 for px in border_pixels)
    visited = bytearray(width * height)
    queue = deque()

    def pixel_saturation(pixel) -> float:
        r, g, b = (pixel[0] / 255.0, pixel[1] / 255.0, pixel[2] / 255.0)
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        if max_c <= 0.0:
            return 0.0
        return (max_c - min_c) / max_c

    def pixel_luma(pixel) -> float:
        r, g, b = (float(pixel[0]), float(pixel[1]), float(pixel[2]))
        return 0.299 * r + 0.587 * g + 0.114 * b

    def channel_spread(pixel) -> int:
        r, g, b = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
        return max(abs(r - g), abs(r - b), abs(g - b))

    def visited_index(x: int, y: int) -> int:
        return y * width + x

    def mark_transparent(x: int, y: int) -> None:
        r, g, b, _a = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)

    def color_distance(a, b) -> float:
        dr = int(a[0]) - int(b[0])
        dg = int(a[1]) - int(b[1])
        db = int(a[2]) - int(b[2])
        return (dr * dr + dg * dg + db * db) ** 0.5

    def is_white_bg_like(pixel) -> bool:
        alpha = int(pixel[3])
        if alpha <= 24:
            return True
        return (
            alpha >= 180
            and min(int(pixel[0]), int(pixel[1]), int(pixel[2])) >= 235
            and channel_spread(pixel) <= 18
            and pixel_saturation(pixel) <= 0.10
        )

    def is_green_bg_like(pixel) -> bool:
        alpha = int(pixel[3])
        if alpha <= 24:
            return True
        r, g, b = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
        return (
            alpha >= 160
            and g >= 140
            and g - r >= 40
            and g - b >= 35
            and pixel_saturation(pixel) >= 0.28
        )

    def flood_fill(match_fn):
        queue.clear()
        for x, y in border_coords:
            pixel = pixels[x, y]
            if match_fn(pixel):
                idx = visited_index(x, y)
                if not visited[idx]:
                    visited[idx] = 1
                    queue.append((x, y))

        while queue:
            x, y = queue.popleft()
            mark_transparent(x, y)
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    idx = visited_index(nx, ny)
                    if not visited[idx] and match_fn(pixels[nx, ny]):
                        visited[idx] = 1
                        queue.append((nx, ny))

    white_border_ratio = (
        float(sum(1 for px in border_pixels if is_white_bg_like(px))) / float(len(border_coords))
        if border_coords
        else 0.0
    )
    green_border_ratio = (
        float(sum(1 for px in border_pixels if is_green_bg_like(px))) / float(len(border_coords))
        if border_coords
        else 0.0
    )

    if transparent_bg or green_border_ratio >= 0.35:
        def is_bg_like(pixel) -> bool:
            alpha = int(pixel[3])
            if alpha <= 24:
                return True
            r, g, b = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
            return (
                alpha >= 140
                and g >= 125
                and g - r >= 28
                and g - b >= 24
                and pixel_saturation(pixel) >= 0.20
            )

        flood_fill(is_bg_like)
    elif white_border_ratio >= 0.45:
        def is_bg_like(pixel) -> bool:
            alpha = int(pixel[3])
            if alpha <= 24:
                return True
            return (
                alpha >= 160
                and min(int(pixel[0]), int(pixel[1]), int(pixel[2])) >= 232
                and channel_spread(pixel) <= 22
                and pixel_saturation(pixel) <= 0.12
                and pixel_luma(pixel) >= 236
            )

        flood_fill(is_bg_like)
    else:
        def collect_bg_refs() -> list:
            if not opaque_border:
                return []

            buckets: dict[tuple[int, int, int], list] = {}
            for px in opaque_border:
                key = (px[0] // 16, px[1] // 16, px[2] // 16)
                buckets.setdefault(key, []).append(px)

            min_count = max(6, int(len(border_coords) * 0.08))
            refs = []
            for group in sorted(buckets.values(), key=len, reverse=True):
                if len(group) < min_count and refs:
                    break
                count = float(len(group))
                refs.append(
                    (
                        sum(px[0] for px in group) / count,
                        sum(px[1] for px in group) / count,
                        sum(px[2] for px in group) / count,
                        sum(px[3] for px in group) / count,
                    )
                )
                if len(refs) >= 3:
                    break
            return refs

        bg_refs = collect_bg_refs()
        bg_ref_stats = [
            {
                "ref": ref,
                "sat": pixel_saturation(ref),
                "luma": pixel_luma(ref),
            }
            for ref in bg_refs
        ]

        def is_bg_like(pixel) -> bool:
            alpha = int(pixel[3])
            if alpha <= 24:
                return True
            pixel_sat = pixel_saturation(pixel)
            pixel_lum = pixel_luma(pixel)
            for item in bg_ref_stats:
                ref = item["ref"]
                rgb_dist = color_distance(pixel, ref)
                alpha_dist = abs(alpha - int(ref[3]))
                sat_gap = pixel_sat - item["sat"]
                luma_gap = abs(pixel_lum - item["luma"])

                if rgb_dist <= 24 and alpha_dist <= 48 and sat_gap <= 0.10 and luma_gap <= 22:
                    return True
            return False

        if bg_refs:
            flood_fill(is_bg_like)

    opaque_pixels = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] > 0:
                opaque_pixels += 1
    opaque_ratio = float(opaque_pixels) / float(width * height)
    if opaque_ratio < 0.14:
        return original

    x0 = width // 4
    x1 = max(width * 3 // 4, x0 + 1)
    y0 = height // 4
    y1 = max(height * 3 // 4, y0 + 1)
    center_total = max((x1 - x0) * (y1 - y0), 1)
    center_opaque = 0
    for y in range(y0, min(y1, height)):
        for x in range(x0, min(x1, width)):
            if pixels[x, y][3] > 0:
                center_opaque += 1
    center_opaque_ratio = float(center_opaque) / float(center_total)
    if center_opaque_ratio < 0.35:
        return original

    return working


class PoisonTongueAgent:
    def __init__(self):
        self._chat_history: list[dict] = []
        self._taunt_history: list[str] = []

    def chat(self, user_message: str) -> str:
        self._chat_history.append({"role": "user", "content": user_message})
        history = self._chat_history[-20:]
        resp = _request_with_retry(
            "POST",
            "/api/chat",
            stage="聊天请求",
            json={"messages": history},
        )
        reply = resp.json()["reply"].strip()
        self._chat_history.append({"role": "assistant", "content": reply})
        return reply

    def generate_taunt(self, window_title: str, category: str, minutes: float) -> str:
        label = get_category_label(category)
        duration_str = f"{int(minutes)} 分钟" if minutes >= 1 else "刚刚"
        resp = _request_with_retry(
            "POST",
            "/api/taunt",
            stage="嘲讽请求",
            json={
                "window_title": window_title,
                "category": category,
                "category_label": label,
                "minutes": minutes,
                "duration_text": duration_str,
                "history": self._taunt_history[-8:],
            },
        )
        result = resp.json()["reply"].strip()
        self._taunt_history.append(result)
        return result


def generate_pixel_avatar(image_path: str, save_path: str, progress_cb=None) -> str:
    if progress_cb:
        progress_cb("正在编码图片...")

    payload = {"image": _encode_image(image_path)}

    if progress_cb:
        progress_cb("正在调用服务器生成像素形象（约 15-30 秒）...")

    resp = _request_with_retry(
        "POST",
        "/api/avatar",
        stage="生成请求",
        json=payload,
    )
    result = resp.json()
    image_b64 = result.get("image_base64")
    if not image_b64:
        raise RuntimeError("服务器返回结果缺少图片数据")

    if progress_cb:
        progress_cb("正在下载并处理图片...")

    from PIL import Image

    img = Image.open(BytesIO(base64.b64decode(image_b64))).convert("RGBA")
    if not _has_real_transparency(img):
        img = _remove_bg(img)
    img.save(save_path, "PNG")

    if progress_cb:
        progress_cb("完成")

    return save_path
