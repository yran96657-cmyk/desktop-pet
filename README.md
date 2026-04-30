# 🐱 毒舌桌宠 (Desktop Pet)

> 一只嘴毒但贴心的 AI 桌宠，盯着你摸鱼，随时给你一句刻薄提醒。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Backend-Flask-green)](https://flask.palletsprojects.com/)

---

## 📥 直接下载使用

不想配置 Python 环境？下载 exe 直接双击运行，无需配置任何内容：

📦 **[desktop_pet_monitorfix.exe（Windows 版，32.8 MB）](releases/desktop_pet_monitorfix.exe)**

> exe 已配置好后端地址，下载后双击即可使用。

---

## ✨ 功能特性

- 🐾 **像素风桌宠**：常驻桌面右下角，随时陪伴
- 🔍 **摸鱼监控**：自动识别当前窗口类型（工作 / 摸鱼 / 娱乐）
- 🗣️ **毒舌吐槽**：根据你的摸鱼状态，定时生成刻薄一句话提醒
- 💬 **对话聊天**：随时和桌宠聊天，获得毒舌但不失分寸的回复
- 🎨 **自定义头像**：上传照片，AI 自动生成像素风桌宠形象

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Windows（其他平台理论可用，未完整测试）

### 1. 获取 API Key

本项目默认使用以下两个模型 API：

| 功能 | 服务 | 获取地址 |
|------|------|----------|
| 聊天 / 吐槽 | Moonshot（Kimi） | https://platform.moonshot.cn/ |
| 头像生成 | 阿里云 DashScope（Qwen） | https://dashscope.aliyun.com/ |

> 头像生成功能可选，不填 `DASHSCOPE_API_KEY` 也能正常运行。

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的密钥：

```bash
cp .env.example .env
```

`.env` 内容：

```env
MOONSHOT_API_KEY=your_moonshot_api_key_here
DASHSCOPE_API_KEY=your_dashscope_api_key_here   # 可选

PORT=8000
PET_BACKEND_URL=http://127.0.0.1:8000
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 启动后端

```bash
python server.py
```

Windows 也可以直接双击：

```
start_backend.bat
```

### 5. 启动桌宠

```bash
python main.py
```

Windows 也可以直接双击：

```
start_client.bat
```

---

## 🗂️ 项目结构

```
desktop_pet_open_source/
├── main.py              # 桌宠客户端主入口
├── pet_window.py        # 桌宠窗口 UI
├── monitor.py           # 摸鱼监控模块
├── guardian.py          # 守护进程
├── backend_client.py    # 后端通信客户端
├── server.py            # Flask 本地后端
├── env_utils.py         # 环境变量工具
├── assets/              # 图标资源
├── releases/            # 打包好的 exe（可直接下载使用）
├── hooks/               # PyInstaller 钩子
├── rthooks/             # PyInstaller 运行时钩子
├── requirements.txt     # 运行依赖
├── requirements-build.txt # 打包依赖
├── build.bat            # 一键打包脚本
├── start_backend.bat    # 启动后端
├── start_client.bat     # 启动客户端
└── .env.example         # 环境变量模板
```

---

## ❗ 注意事项

- 这是 **self-host 版本**，不提供官方托管服务
- 你需要自己申请并填写 API Key
- 本项目不附带任何生产环境凭证

---

## 🤝 贡献

欢迎提 Issue 和 PR！

- 🐛 发现 Bug → 提 Issue
- 💡 有新功能想法 → 提 Issue 讨论
- 🛠️ 想直接改代码 → Fork 后提 PR

---

## 📄 License

[MIT License](LICENSE) © 2026 Yiran
