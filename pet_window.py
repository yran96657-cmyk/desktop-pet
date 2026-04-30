import os
import random
import shutil
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

import psutil
import win32con
import win32gui
import win32process

try:
    from PIL import Image, ImageTk

    _PIL_OK = True
except ImportError:
    _PIL_OK = False


TRANSPARENT = "#00ff00"
PIXEL = 4
SIZE = 16
CANVAS_W = SIZE * PIXEL
CANVAS_H = SIZE * PIXEL
CHAT_W = 380
CHAT_H = 500
SCREEN_PAD = 12
FONT_UI = "Microsoft YaHei UI"
DEFAULT_CHAT_HINT = "先启动本地后端并配置 API Key，我就能陪你聊天。"
DEFAULT_CHAT_GREETING = "我在，想聊什么？"
CHAT_THINKING_TEXT = "正在思考中..."
AVATAR_PROGRESS_VALUES = {
    "正在编码图片...": 10,
    "正在调用服务端生成像素形象（约 15-30 秒）...": 45,
    "正在下载并处理图片...": 80,
    "完成": 100,
}


def _get_base_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _user_data_dir() -> Path:
    root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    base_dir = Path(root) if root else Path.home()
    target = base_dir / "DesktopPet"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _custom_avatar_path() -> str:
    return str(_user_data_dir() / "custom_avatar.png")


def _legacy_custom_avatar_path() -> str:
    return os.path.join(_get_base_dir(), "custom_avatar.png")


COLORS = {
    "b": "#2d2d2d",
    "w": "#f5f0e8",
    "g": "#c8a882",
    "p": "#ffb3ba",
    "e": "#4a9eff",
    "t": None,
}

IDLE_0 = [
    "tttttttttttttttt",
    "tttbbttttttbbttt",
    "ttbggbttttbggbtt",
    "ttbpgbttttbgpbtt",
    "ttbbbbbbbbbbbbtt",
    "ttbggggggggggbtt",
    "ttbgeggggggegbtt",
    "ttbggggggggggbtt",
    "ttbggpgggpggggbt",
    "ttbgggwwwgggggbt",
    "tttbgggggggggbtt",
    "tttbbgggggggbbtt",
    "ttttbgggggggbttt",
    "ttttbbbbbbbbbttt",
    "tttttttttttttttt",
    "tttttttttttttttt",
]

IDLE_1 = [
    "tttttttttttttttt",
    "tttbbttttttbbttt",
    "ttbggbttttbggbtt",
    "ttbpgbttttbgpbtt",
    "ttbbbbbbbbbbbbtt",
    "ttbggggggggggbtt",
    "ttbgbbbbbbbbgbtt",
    "ttbggggggggggbtt",
    "ttbggpgggpggggbt",
    "ttbgggwwwgggggbt",
    "tttbgggggggggbtt",
    "tttbbgggggggbbtt",
    "ttttbgggggggbttt",
    "ttttbbbbbbbbbttt",
    "tttttttttttttttt",
    "tttttttttttttttt",
]

TAUNT_0 = [
    "tttttttttttttttt",
    "tttbbttttttbbttt",
    "ttbggbttttbggbtt",
    "ttbpgbttttbgpbtt",
    "ttbbbbbbbbbbbbtt",
    "ttbggggggggggbtt",
    "ttbgbbgggbbggbtt",
    "ttbggbbgbbggggtt",
    "ttbggpgggpggggbt",
    "ttbggbwwwbggggbt",
    "tttbgggggggggbtt",
    "tttbbgggggggbbtt",
    "ttttbgggggggbttt",
    "ttttbbbbbbbbbttt",
    "tttttttttttttttt",
    "tttttttttttttttt",
]

FRAMES = {
    "idle": [IDLE_0, IDLE_1],
    "taunt": [TAUNT_0, TAUNT_0],
}


def _frame_to_image(frame: list[str]):
    image = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    for row_index, row in enumerate(frame):
        for col_index, char in enumerate(row):
            color = COLORS.get(char)
            if color is None:
                continue
            rgba = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5)) + (255,)
            for dy in range(PIXEL):
                for dx in range(PIXEL):
                    image.putpixel((col_index * PIXEL + dx, row_index * PIXEL + dy), rgba)
    return image


class ChatDialog:
    def __init__(self, owner: "PetWindow"):
        self.owner = owner
        self.window = tk.Toplevel(owner.root)
        self.window.title("聊天")
        self.window.geometry(f"{CHAT_W}x{CHAT_H}")
        self.window.minsize(CHAT_W, CHAT_H)
        self.window.configure(bg="#1f2937")
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        owner._apply_window_icon(self.window)

        shell = tk.Frame(self.window, bg="#1f2937")
        shell.pack(fill="both", expand=True, padx=12, pady=12)

        header = tk.Frame(shell, bg="#1f2937")
        header.pack(fill="x", pady=(0, 10))
        tk.Label(
            header,
            text="聊天",
            bg="#1f2937",
            fg="#f9fafb",
            font=(FONT_UI, 12, "bold"),
        ).pack(anchor="w", pady=(4, 0))

        row = tk.Frame(shell, bg="#1f2937")
        row.pack(side="bottom", fill="x", pady=(10, 0))

        history_shell = tk.Frame(shell, bg="#1f2937")
        history_shell.pack(fill="both", expand=True)

        self.history = tk.Text(
            history_shell,
            bg="#111827",
            fg="#f9fafb",
            relief="flat",
            wrap="word",
            font=(FONT_UI, 10),
            padx=10,
            pady=10,
        )
        scrollbar = tk.Scrollbar(history_shell, command=self.history.yview)
        self.history.configure(yscrollcommand=scrollbar.set)
        self.history.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y", padx=(8, 0))
        self.history.configure(state="disabled")

        self.entry = tk.Entry(
            row,
            bg="#374151",
            fg="#f9fafb",
            relief="flat",
            insertbackground="#f9fafb",
            font=(FONT_UI, 10),
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.entry.bind("<Return>", self._send)

        self.send_button = tk.Button(
            row,
            text="发送",
            command=self._send,
            bg="#d1495b",
            fg="#ffffff",
            activebackground="#b93b4b",
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            font=(FONT_UI, 10, "bold"),
        )
        self.send_button.pack(side="left", padx=(8, 0))

    def _send(self, _event=None) -> None:
        message = self.entry.get().strip()
        if not message:
            return
        self.entry.delete(0, "end")
        self.owner._send_chat(message)

    def show(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.update_idletasks()
        self.entry.focus_set()

    def hide(self) -> None:
        self.window.withdraw()

    def is_visible(self) -> bool:
        return self.window.state() != "withdrawn"

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.entry.configure(state=state)
        self.send_button.configure(state=state)

    def append_message(self, who: str, text: str) -> tuple[str, str]:
        prefix = "你" if who == "user" else "桌宠"
        self.history.configure(state="normal")
        start_index = self.history.index("end-1c")
        self.history.insert("end", f"{prefix}：{text}\n\n")
        end_index = self.history.index("end-1c")
        self.history.see("end")
        self.history.configure(state="disabled")
        return start_index, end_index

    def remove_range(self, marker: tuple[str, str] | None) -> None:
        if not marker:
            return
        start_index, end_index = marker
        self.history.configure(state="normal")
        try:
            self.history.delete(start_index, end_index)
        except tk.TclError:
            pass
        self.history.configure(state="disabled")

    def destroy(self) -> None:
        self.window.destroy()


class ProgressDialog:
    def __init__(self, owner: "PetWindow"):
        self.window = tk.Toplevel(owner.root)
        self.window.title("生成像素头像")
        self.window.geometry("360x150")
        self.window.configure(bg="#1f2937")
        self.window.attributes("-topmost", True)
        self.window.resizable(False, False)
        owner._apply_window_icon(self.window)

        shell = tk.Frame(self.window, bg="#1f2937")
        shell.pack(fill="both", expand=True, padx=18, pady=18)

        self.title = tk.Label(shell, text="头像生成中", bg="#1f2937", fg="#f9fafb", font=(FONT_UI, 12, "bold"))
        self.title.pack(anchor="w")

        self.status = tk.Label(
            shell,
            text="正在准备上传图片...",
            bg="#1f2937",
            fg="#f9fafb",
            justify="left",
            wraplength=320,
            font=(FONT_UI, 10),
        )
        self.status.pack(anchor="w", pady=(10, 10))

        self.progress = ttk.Progressbar(shell, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x")

    def close(self) -> None:
        self.window.destroy()


class PetWindow:
    BUBBLE_DURATION = 4.0

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT)
        self.root.attributes("-topmost", True)
        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass

        self._state = "idle"
        self._frame_idx = 0
        self._bubble_hide_at = 0.0
        self._pending_close_hwnd = 0
        self._pending_force_kill = False
        self._focus_end = 0.0
        self._agent = None
        self._chat_win: ChatDialog | None = None
        self._progress_dialog: ProgressDialog | None = None
        self._start_focus_callback: Callable[[int], None] | None = None
        self._closing = False
        self._chat_pending = False
        self._custom_image = None
        self._drag_start = (0, 0)
        self._drag_origin = (0, 0)
        self._move_path: list[tuple[int, int]] = []
        self._chat_pending_marker: tuple[str, str] | None = None

        self.bubble_win = None
        self.countdown_win = None
        self.bubble_label = None
        self.countdown_label = None

        self._frame_cache = {
            name: [ImageTk.PhotoImage(_frame_to_image(frame)) for frame in frames]
            for name, frames in FRAMES.items()
        }
        self._window_icon = self._create_window_icon()
        self._apply_window_icon(self.root)

        self.canvas = tk.Canvas(
            self.root,
            width=CANVAS_W,
            height=CANVAS_H,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.canvas.pack()
        self._sprite_id = self.canvas.create_image(0, 0, anchor="nw", image=self._current_image())

        self._build_overlay_windows()
        self._build_menu()
        self._bind_events()
        self._load_custom_avatar()
        self._redraw_sprite()
        self._reset_position()

        self.root.after(180, self._tick)
        self.root.after(1000, self._update_countdown)

    def _create_window_icon(self):
        if not _PIL_OK:
            return None
        image = _frame_to_image(IDLE_0).resize((64, 64), Image.NEAREST)
        return ImageTk.PhotoImage(image)

    def _apply_window_icon(self, window: tk.Misc) -> None:
        if not self._window_icon:
            return
        try:
            window.iconphoto(True, self._window_icon)
        except tk.TclError:
            pass

    def _build_overlay_windows(self) -> None:
        self.bubble_win = tk.Toplevel(self.root)
        self.bubble_win.withdraw()
        self.bubble_win.overrideredirect(True)
        self.bubble_win.attributes("-topmost", True)
        self.bubble_win.configure(bg="#fff8dc")
        self.bubble_label = tk.Label(
            self.bubble_win,
            text="",
            bg="#fff8dc",
            fg="#333333",
            justify="left",
            wraplength=220,
            padx=10,
            pady=8,
            font=(FONT_UI, 10),
        )
        self.bubble_label.pack()

        self.countdown_win = tk.Toplevel(self.root)
        self.countdown_win.withdraw()
        self.countdown_win.overrideredirect(True)
        self.countdown_win.attributes("-topmost", True)
        self.countdown_win.configure(bg="#1a1a2e")
        self.countdown_label = tk.Label(
            self.countdown_win,
            text="",
            bg="#1a1a2e",
            fg="#f8d66d",
            padx=10,
            pady=6,
            font=(FONT_UI, 10, "bold"),
        )
        self.countdown_label.pack()

    def _bind_events(self) -> None:
        self.canvas.bind("<Button-1>", self._on_left_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_release)
        self.canvas.bind("<Button-3>", self._show_menu)

    def _build_menu(self) -> None:
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="开始专注", command=self._open_focus_dialog)
        self.menu.add_command(label="更换头像", command=self._open_avatar_dialog)
        self.menu.add_command(label="重置头像", command=self._reset_avatar)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self._try_exit)

    def _screen_size(self) -> tuple[int, int]:
        return self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def set_agent(self, agent: Any) -> None:
        self._agent = agent
        self._sync_chat_enabled_state()

    def get_agent(self) -> Any:
        return self._agent

    def set_focus_callback(self, callback: Callable[[int], None] | None) -> None:
        self._start_focus_callback = callback

    def _current_image(self):
        if self._custom_image is not None:
            return self._custom_image
        frames = self._frame_cache[self._state]
        return frames[self._frame_idx % len(frames)]

    def _redraw_sprite(self) -> None:
        self.canvas.itemconfigure(self._sprite_id, image=self._current_image())

    def _reset_position(self) -> None:
        sw, sh = self._screen_size()
        x = sw - CANVAS_W - 40
        y = sh - CANVAS_H - 80
        self.root.geometry(f"{CANVAS_W}x{CANVAS_H}+{x}+{y}")
        self._reposition_overlays()

    def _root_pos(self) -> tuple[int, int]:
        self.root.update_idletasks()
        return self.root.winfo_x(), self.root.winfo_y()

    def _move_root_to(self, x: int, y: int) -> None:
        self.root.geometry(f"+{int(x)}+{int(y)}")
        self._reposition_overlays()

    def _start_taunt_motion(self, hwnd: int) -> None:
        self._move_path = []
        if not hwnd:
            return
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except Exception:
            return

        sw, sh = self._screen_size()
        start_x, start_y = self._root_pos()
        close_center_x = right - 23
        close_center_y = top + 16
        target_x = max(0, min(int(close_center_x - CANVAS_W / 2), sw - CANVAS_W))
        target_y = max(0, min(int(close_center_y - CANVAS_H / 2), sh - CANVAS_H))
        steps = 12
        for step in range(1, steps + 1):
            progress = step / steps
            x = round(start_x + (target_x - start_x) * progress)
            y = round(start_y + (target_y - start_y) * progress)
            self._move_path.append((x, y))

    def _reposition_overlays(self) -> None:
        self._reposition_bubble()
        self._reposition_countdown()
        self._reposition_chat()

    def _reposition_bubble(self) -> None:
        if not self.bubble_win or not self.bubble_win.winfo_viewable():
            return
        self.bubble_win.update_idletasks()
        x, y = self._root_pos()
        sw, sh = self._screen_size()
        bubble_w = self.bubble_win.winfo_width()
        bubble_h = self.bubble_win.winfo_height()
        target_x = x - bubble_w - 8
        if target_x < SCREEN_PAD:
            target_x = x + CANVAS_W + 8
        target_y = max(SCREEN_PAD, min(y - bubble_h // 3, sh - bubble_h - SCREEN_PAD))
        self.bubble_win.geometry(f"+{target_x}+{target_y}")

    def _reposition_countdown(self) -> None:
        if not self.countdown_win or not self.countdown_win.winfo_viewable():
            return
        self.countdown_win.update_idletasks()
        x, y = self._root_pos()
        target_x = x + CANVAS_W // 2 - self.countdown_win.winfo_width() // 2
        target_y = y - self.countdown_win.winfo_height() - 8
        self.countdown_win.geometry(f"+{target_x}+{target_y}")

    def _reposition_chat(self) -> None:
        if not self._chat_win or not self._chat_win.is_visible():
            return
        self._chat_win.window.update_idletasks()
        x, y = self._root_pos()
        sw, sh = self._screen_size()
        chat_w = max(self._chat_win.window.winfo_width(), CHAT_W)
        chat_h = max(self._chat_win.window.winfo_height(), CHAT_H)
        space_left = x
        space_right = sw - (x + CANVAS_W)
        if space_left >= chat_w + 10 or space_left >= space_right:
            target_x = x - chat_w - 10
        else:
            target_x = x + CANVAS_W + 10
        target_y = max(SCREEN_PAD, min(y - chat_h + CANVAS_H, sh - chat_h - SCREEN_PAD))
        self._chat_win.window.geometry(f"{chat_w}x{chat_h}+{target_x}+{target_y}")

    def _on_left_press(self, event) -> None:
        self._drag_start = (event.x_root, event.y_root)
        self._drag_origin = self._root_pos()

    def _on_drag(self, event) -> None:
        dx = event.x_root - self._drag_start[0]
        dy = event.y_root - self._drag_start[1]
        new_x = self._drag_origin[0] + dx
        new_y = self._drag_origin[1] + dy
        self.root.geometry(f"+{new_x}+{new_y}")
        self._reposition_overlays()

    def _on_left_release(self, event) -> None:
        dx = abs(event.x_root - self._drag_start[0])
        dy = abs(event.y_root - self._drag_start[1])
        if dx <= 2 and dy <= 2:
            self._open_chat()

    def _show_menu(self, event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _load_custom_avatar(self) -> None:
        self._custom_image = None
        if not _PIL_OK:
            return
        path = _custom_avatar_path()
        legacy_path = _legacy_custom_avatar_path()
        if not os.path.exists(path) and os.path.exists(legacy_path):
            try:
                shutil.copyfile(legacy_path, path)
            except OSError:
                pass
        if not os.path.exists(path):
            return
        try:
            image = Image.open(path).convert("RGBA").resize((CANVAS_W, CANVAS_H), Image.NEAREST)
            self._custom_image = ImageTk.PhotoImage(image)
        except Exception as exc:
            print(f"[custom avatar load failed] {exc}")

    def _open_avatar_dialog(self) -> None:
        if not _PIL_OK:
            messagebox.showerror("缺少依赖", "当前环境缺少 Pillow，无法处理头像。", parent=self.root)
            return
        path = filedialog.askopenfilename(
            title="选择一张图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.webp *.bmp"), ("所有文件", "*.*")],
            parent=self.root,
        )
        if not path:
            return

        self._progress_dialog = ProgressDialog(self)

        def worker() -> None:
            try:
                from backend_client import generate_pixel_avatar

                save_path = _custom_avatar_path()

                def progress_cb(message: str) -> None:
                    self.root.after(0, lambda: self._on_avatar_progress(message))

                generate_pixel_avatar(path, save_path, progress_cb)
                self.root.after(0, self._on_avatar_done)
            except Exception as exc:
                self.root.after(0, lambda: self._on_avatar_error(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_avatar_progress(self, message: str) -> None:
        if not self._progress_dialog:
            return
        self._progress_dialog.status.configure(text=message)
        self._progress_dialog.progress["value"] = AVATAR_PROGRESS_VALUES.get(
            message,
            self._progress_dialog.progress["value"],
        )

    def _on_avatar_done(self) -> None:
        self._load_custom_avatar()
        self._redraw_sprite()
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        self.show_bubble("头像已更新")

    def _on_avatar_error(self, error_message: str) -> None:
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        messagebox.showerror("头像生成失败", error_message, parent=self.root)

    def _reset_avatar(self) -> None:
        try:
            path = _custom_avatar_path()
            if os.path.exists(path):
                os.remove(path)
        except OSError as exc:
            messagebox.showerror("重置失败", str(exc), parent=self.root)
            return
        self._custom_image = None
        self._redraw_sprite()
        self.show_bubble("已恢复默认头像")

    def _open_focus_dialog(self) -> None:
        if self._focus_end and time.time() < self._focus_end:
            remaining = max(0, int(self._focus_end - time.time()))
            minutes, seconds = divmod(remaining, 60)
            messagebox.showinfo("专注进行中", f"当前专注尚未结束，剩余 {minutes:02d}:{seconds:02d}", parent=self.root)
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("开始专注")
        dialog.attributes("-topmost", True)
        dialog.configure(bg="#1f2937")
        dialog.resizable(False, False)

        shell = tk.Frame(dialog, bg="#1f2937")
        shell.pack(fill="both", expand=True, padx=18, pady=18)
        tk.Label(shell, text="输入专注时长（分钟）", bg="#1f2937", fg="#f9fafb", font=(FONT_UI, 10)).pack(anchor="w")

        entry = tk.Entry(shell, justify="center", font=(FONT_UI, 12))
        entry.insert(0, "25")
        entry.pack(fill="x", ipady=8, pady=(10, 12))

        row = tk.Frame(shell, bg="#1f2937")
        row.pack(fill="x")

        def confirm(_event=None):
            try:
                minutes = int(entry.get().strip())
                if minutes <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("输入错误", "请输入大于 0 的整数分钟数。", parent=dialog)
                return
            dialog.destroy()
            if self._start_focus_callback:
                self._start_focus_callback(minutes)

        tk.Button(row, text="开始", command=confirm, bg="#d1495b", fg="#ffffff", relief="flat", bd=0).pack(
            side="left", fill="x", expand=True, ipady=8
        )
        tk.Button(row, text="取消", command=dialog.destroy, bg="#4b5563", fg="#ffffff", relief="flat", bd=0).pack(
            side="left", fill="x", expand=True, ipady=8, padx=(8, 0)
        )

        entry.bind("<Return>", confirm)
        entry.focus_set()

    def set_focus_end(self, ts: float) -> None:
        self._focus_end = float(ts)
        self._update_countdown()

    def _update_countdown(self) -> None:
        if self._closing:
            return
        if not self._focus_end:
            self.countdown_win.withdraw()
        else:
            remaining = self._focus_end - time.time()
            if remaining <= 0:
                self._focus_end = 0.0
                self.countdown_win.withdraw()
                self.show_bubble("专注结束")
            else:
                total_seconds = int(remaining)
                minutes, seconds = divmod(total_seconds, 60)
                hours, minutes = divmod(minutes, 60)
                if hours:
                    text = f"专注剩余 {hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    text = f"专注剩余 {minutes:02d}:{seconds:02d}"
                self.countdown_label.configure(text=text)
                self.countdown_win.deiconify()
                self._reposition_countdown()
        self.root.after(1000, self._update_countdown)

    def _open_chat(self) -> None:
        if self._chat_win is None:
            self._chat_win = ChatDialog(self)
        self._ensure_chat_intro()
        self._chat_win.show()
        self._sync_chat_enabled_state()
        self._reposition_chat()

    def _ensure_chat_intro(self) -> None:
        if not self._chat_win:
            return
        if self._chat_win.history.get("1.0", "end").strip():
            return
        opening_line = DEFAULT_CHAT_GREETING if self._agent is not None else DEFAULT_CHAT_HINT
        self._chat_win.append_message("pet", opening_line)

    def _sync_chat_enabled_state(self) -> None:
        if not self._chat_win:
            return
        enabled = self._agent is not None and not self._chat_pending
        self._chat_win.set_enabled(enabled)
        if self._agent is None and self._chat_win.history.get("1.0", "end").strip() == "":
            self._chat_win.append_message("pet", DEFAULT_CHAT_HINT)

    def _send_chat(self, message: str) -> None:
        if not self._agent or not self._chat_win or self._chat_pending:
            return
        self._chat_pending = True
        self._chat_win.append_message("user", message)
        self._chat_pending_marker = self._chat_win.append_message("pet", CHAT_THINKING_TEXT)
        self._sync_chat_enabled_state()

        def worker() -> None:
            try:
                reply = self._agent.chat(message)
            except Exception as exc:
                reply = f"聊天失败：{exc}"
            self.root.after(0, lambda: self._on_chat_reply(reply))

        threading.Thread(target=worker, daemon=True).start()

    def _on_chat_reply(self, reply: str) -> None:
        self._chat_pending = False
        if self._chat_win:
            self._chat_win.remove_range(self._chat_pending_marker)
            self._chat_win.append_message("pet", reply)
        self._chat_pending_marker = None
        self._sync_chat_enabled_state()
        self.show_bubble(reply)

    def show_bubble(self, text: str, hwnd: int = 0, *, force_kill: bool = False) -> None:
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, lambda: self._show_bubble_main(text, hwnd, force_kill))
            return
        self._show_bubble_main(text, hwnd, force_kill)

    def _show_bubble_main(self, text: str, hwnd: int, force_kill: bool) -> None:
        self._state = "taunt"
        self._frame_idx = 0
        self._pending_close_hwnd = hwnd
        self._pending_force_kill = force_kill
        self._start_taunt_motion(hwnd)
        self.bubble_label.configure(text=text)
        self.bubble_win.deiconify()
        self._reposition_bubble()
        self._redraw_sprite()
        self._bubble_hide_at = time.time() + self.BUBBLE_DURATION

    def _tick(self) -> None:
        if self._closing:
            return
        now = time.time()
        if self._move_path:
            next_x, next_y = self._move_path.pop(0)
            self._move_root_to(next_x, next_y)
        if self._bubble_hide_at and now >= self._bubble_hide_at:
            self.bubble_win.withdraw()
            self._bubble_hide_at = 0.0
            if self._pending_close_hwnd:
                hwnd = self._pending_close_hwnd
                force_kill = self._pending_force_kill
                self._pending_close_hwnd = 0
                self._pending_force_kill = False
                self._finish_close_window(hwnd, force_kill)
            else:
                self._state = "idle"

        self._frame_idx += 1
        self._redraw_sprite()
        if self._move_path:
            interval = 40
        else:
            interval = 120 if self._state != "idle" else (150 if self._frame_idx % 2 else random.randint(1800, 3200))
        self.root.after(interval, self._tick)

    def _finish_close_window(self, hwnd: int, force_kill: bool) -> None:
        try:
            if force_kill:
                self._kill_process_tree(hwnd)
            else:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        except Exception as exc:
            print(f"[close window failed] {exc}")
        self._state = "idle"
        self._frame_idx = 0
        self._redraw_sprite()

    def _kill_process_tree(self, hwnd: int) -> None:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if not pid:
                return
            proc = psutil.Process(pid)
            children = proc.children(recursive=True)
            for child in reversed(children):
                try:
                    child.kill()
                except Exception:
                    pass
            try:
                proc.kill()
            except Exception:
                pass
            psutil.wait_procs(children + [proc], timeout=3)
        except Exception as exc:
            print(f"[kill process failed] {exc}")

    def _try_exit(self) -> None:
        if self._focus_end and time.time() < self._focus_end:
            remaining = max(0, int(self._focus_end - time.time()))
            minutes, seconds = divmod(remaining, 60)
            messagebox.showwarning(
                "专注进行中",
                f"当前还在专注模式中，剩余 {minutes:02d}:{seconds:02d}，暂时不能退出。",
                parent=self.root,
            )
            return
        self.shutdown()

    def shutdown(self) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            if self._chat_win:
                self._chat_win.destroy()
        except Exception:
            pass
        try:
            if self._progress_dialog:
                self._progress_dialog.close()
        except Exception:
            pass
        for win in [self.bubble_win, self.countdown_win]:
            try:
                if win is not None:
                    win.destroy()
            except Exception:
                pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
