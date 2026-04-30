import psutil
import win32gui
import win32process


WORK_KEYWORDS = (
    "visual studio",
    "vscode",
    "vs code",
    "pycharm",
    "idea",
    "intellij",
    "excel",
    "word",
    "powerpoint",
    "outlook",
    "notion",
    "github",
    "gitlab",
    "terminal",
    "cmd",
    "powershell",
    "bash",
    "figma",
    "xcode",
    "android studio",
    "cursor",
    "postman",
    "navicat",
    "dbeaver",
    "datagrip",
)


FISHING_KEYWORDS = {
    "video": (
        "youtube",
        "bilibili",
        "\u54d4\u54e9\u54d4\u54e9",
        "\u6296\u97f3",
        "douyin",
        "tiktok",
        "\u5feb\u624b",
        "kuaishou",
        "netflix",
        "\u7231\u5947\u827a",
        "\u4f18\u9177",
        "\u817e\u8baf\u89c6\u9891",
        "\u8292\u679ctv",
        "\u89c6\u9891\u53f7",
        "\u5fae\u4fe1\u89c6\u9891\u53f7",
        "\u5c0f\u89c6\u9891",
        "\u76f4\u64ad",
        "\u6597\u9c7c",
        "\u864e\u7259",
        "acfun",
        "\u897f\u74dc\u89c6\u9891",
    ),
    "social": (
        "\u670b\u53cb\u5708",
        "moments",
        "\u5fae\u535a",
        "weibo",
        "\u5c0f\u7ea2\u4e66",
        "xiaohongshu",
        "twitter",
        "x.com",
        "facebook",
        "instagram",
        "threads",
        "discord",
        "\u8c46\u74e3",
        "douban",
    ),
    "game": (
        "steam",
        "wegame",
        "epic games",
        "epic games launcher",
        "minecraft",
        "elden ring",
        "\u539f\u795e",
        "\u82f1\u96c4\u8054\u76df",
        "\u738b\u8005\u8363\u8000",
        "genshin",
        "\u5d29\u574f",
        "\u661f\u7a79\u94c1\u9053",
        "\u7edd\u533a\u96f6",
    ),
    "shopping": (
        "\u6dd8\u5b9d",
        "taobao",
        "\u5929\u732b",
        "\u4eac\u4e1c",
        "jd.com",
        "\u62fc\u591a\u591a",
        "pinduoduo",
        "\u95f2\u9c7c",
        "\u54b8\u9c7c",
        "amazon",
        "\u4e9a\u9a6c\u900a",
        "\u5f97\u7269",
        "poizon",
    ),
    "forum": (
        "\u77e5\u4e4e",
        "zhihu",
        "reddit",
        "hacker news",
        "cc98",
        "cc98.org",
        "\u864e\u6251",
        "\u767e\u5ea6\u8d34\u5427",
        "tieba",
        "nga",
        "chiphell",
        "v2ex",
    ),
    "novel": (
        "\u5c0f\u8bf4",
        "\u8d77\u70b9",
        "\u664b\u6c5f",
        "\u756a\u8304\u5c0f\u8bf4",
        "\u5fae\u4fe1\u8bfb\u4e66",
        "\u8bfb\u4e66",
        "\u8d77\u70b9\u4e2d\u6587\u7f51",
        "jjwxc",
    ),
    "music": (
        "\u7f51\u6613\u4e91\u97f3\u4e50",
        "cloudmusic",
        "qq\u97f3\u4e50",
        "spotify",
        "apple music",
        "\u6c7d\u6c34\u97f3\u4e50",
    ),
}


CATEGORY_LABELS = {
    "video": "\u770b\u89c6\u9891",
    "social": "\u5237\u793e\u4ea4\u5185\u5bb9",
    "game": "\u6253\u6e38\u620f",
    "shopping": "\u901b\u8d2d\u7269\u7f51\u7ad9",
    "forum": "\u5237\u8bba\u575b\u8d44\u8baf",
    "novel": "\u770b\u5c0f\u8bf4",
    "music": "\u542c\u97f3\u4e50\u6478\u9c7c",
    "unknown": "\u6478\u9c7c",
}


BROWSER_PROCESS_NAMES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "opera.exe",
    "iexplore.exe",
    "qqbrowser.exe",
    "360chrome.exe",
    "sogouexplorer.exe",
    "brave.exe",
    "chrome_proxy.exe",
}


DIRECT_FISHING_PROCESS_KEYWORDS = {
    "bilibili",
    "douyin",
    "kuaishou",
    "steam",
    "wegame",
    "epic",
    "cloudmusic",
    "qqmusic",
    "spotify",
    "potplayer",
    "vlc",
}


FORCE_KILL_TITLE_KEYWORDS = {
    "\u89c6\u9891\u53f7",
    "\u5fae\u4fe1\u89c6\u9891\u53f7",
    "\u670b\u53cb\u5708",
    "\u54d4\u54e9\u54d4\u54e9",
    "bilibili",
    "\u6296\u97f3",
    "douyin",
    "\u5feb\u624b",
    "steam",
    "wegame",
}


def _normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def _contains_any_keyword(text: str, keywords) -> bool:
    return any(keyword in text for keyword in keywords)


def get_active_window_title() -> str:
    try:
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd) or ""
    except Exception:
        return ""


def get_category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, "\u6478\u9c7c")


def _get_window_process_name(hwnd: int) -> str:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            return ""
        return _normalize_text(psutil.Process(pid).name() or "")
    except Exception:
        return ""


def _infer_process_only_category(process_name: str) -> str:
    if not process_name or process_name in BROWSER_PROCESS_NAMES:
        return "unknown"

    if any(keyword in process_name for keyword in ("bilibili", "douyin", "kuaishou", "potplayer", "vlc")):
        return "video"
    if any(keyword in process_name for keyword in ("steam", "wegame", "epic")):
        return "game"
    if any(keyword in process_name for keyword in ("cloudmusic", "qqmusic", "spotify")):
        return "music"
    return "unknown"


def classify_window(title: str) -> tuple[bool, str]:
    lower_title = _normalize_text(title)
    if not lower_title:
        return False, "unknown"

    if _contains_any_keyword(lower_title, WORK_KEYWORDS):
        return False, "working"

    for category, keywords in FISHING_KEYWORDS.items():
        if _contains_any_keyword(lower_title, keywords):
            return True, category

    hwnd = win32gui.GetForegroundWindow()
    process_name = _get_window_process_name(hwnd)
    category = _infer_process_only_category(process_name)
    if category != "unknown":
        return True, category

    return False, "unknown"


def should_force_kill_window(hwnd: int, title: str, category: str) -> bool:
    if not hwnd or category == "working":
        return False

    process_name = _get_window_process_name(hwnd)
    if not process_name:
        return False
    if process_name in BROWSER_PROCESS_NAMES:
        return False

    lower_title = _normalize_text(title)
    if _contains_any_keyword(lower_title, FORCE_KILL_TITLE_KEYWORDS):
        return True
    if any(keyword in process_name for keyword in DIRECT_FISHING_PROCESS_KEYWORDS):
        return True

    return False
