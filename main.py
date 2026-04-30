import ctypes
import os
import random
import subprocess
import sys
import threading
import time

import win32gui

from backend_client import PoisonTongueAgent
from monitor import classify_window, get_active_window_title, should_force_kill_window
from pet_window import PetWindow

POLL_INTERVAL = 2
SWITCH_COOLDOWN = 30
PERSIST_THRESHOLD = 300

HERE = os.path.dirname(os.path.abspath(__file__))

_SINGLE_INSTANCE_HANDLE = None
_MUTEX_NAME = "DesktopPetSingleInstanceMutex"
_ERROR_ALREADY_EXISTS = 183

focus_end: float = 0.0


def _show_native_message(title: str, message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x40)
    except Exception:
        print(f"{title}: {message}", file=sys.stderr)


def _acquire_single_instance() -> bool:
    global _SINGLE_INSTANCE_HANDLE

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if not handle:
        return True

    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False

    _SINGLE_INSTANCE_HANDLE = handle
    return True


def _release_single_instance() -> None:
    global _SINGLE_INSTANCE_HANDLE

    if not _SINGLE_INSTANCE_HANDLE:
        return
    try:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(_SINGLE_INSTANCE_HANDLE)
    except Exception:
        pass
    _SINGLE_INSTANCE_HANDLE = None


def start_focus(pet: PetWindow, minutes: int) -> None:
    global focus_end

    focus_end = time.time() + minutes * 60
    pet.set_focus_end(focus_end)

    _spawn_guardian_process(focus_end)
    print(f"[专注模式] 已启动，时长 {minutes} 分钟，guardian 已拉起", flush=True)


def _spawn_guardian_process(focus_end_ts: float) -> None:
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--guardian", str(os.getpid()), str(focus_end_ts)]
    else:
        guardian_script = os.path.join(HERE, "guardian.py")
        command = [sys.executable, guardian_script, str(os.getpid()), str(focus_end_ts)]
    subprocess.Popen(command, cwd=HERE)


def _monitor_loop(pet: PetWindow) -> None:
    last_title = ""
    last_taunt_time = 0.0
    fishing_since = 0.0
    persist_taunted = False

    while True:
        title = get_active_window_title()
        now = time.time()
        is_fishing, category = classify_window(title)

        if title != last_title:
            if is_fishing:
                fishing_since = now
                persist_taunted = False
                if now - last_taunt_time >= SWITCH_COOLDOWN:
                    hwnd = win32gui.GetForegroundWindow()
                    _taunt(
                        pet,
                        title,
                        category,
                        0,
                        hwnd,
                        force_kill=should_force_kill_window(hwnd, title, category),
                    )
                    last_taunt_time = now
            else:
                fishing_since = 0.0
                persist_taunted = False
            last_title = title
        elif is_fishing and fishing_since > 0:
            elapsed = now - fishing_since
            if not persist_taunted and elapsed >= PERSIST_THRESHOLD:
                hwnd = win32gui.GetForegroundWindow()
                _taunt(
                    pet,
                    title,
                    category,
                    elapsed / 60,
                    hwnd,
                    force_kill=should_force_kill_window(hwnd, title, category),
                )
                last_taunt_time = now
                persist_taunted = True

        time.sleep(POLL_INTERVAL)


def _taunt(
    pet: PetWindow,
    title: str,
    category: str,
    minutes: float,
    hwnd: int = 0,
    *,
    force_kill: bool = False,
) -> None:
    print(f"[触发嘲讽] 窗口: {title!r} 摸鱼时长: {minutes:.1f} 分钟", flush=True)

    agent = pet.get_agent()
    if agent is None:
        pet.show_bubble(
            random.choice(
                [
                    "给我滚去干活。",
                    "摸鱼又被抓了，废物。",
                    "你是不是又在装忙？",
                    "还不去工作？",
                    "别发呆了，快干活。",
                ]
            ),
            hwnd,
            force_kill=force_kill,
        )
        return

    try:
        text = agent.generate_taunt(title, category, minutes)
        pet.show_bubble(text, hwnd, force_kill=force_kill)
    except Exception as exc:
        print(f"[Agent 错误] {exc}", file=sys.stderr)


def _run_guardian() -> None:
    import psutil

    if len(sys.argv) < 4:
        print("[guardian] 参数不足，退出", flush=True)
        return

    main_pid = int(sys.argv[2])
    focus_ts = float(sys.argv[3])
    print(f"[guardian] 启动，守护 main pid={main_pid}，专注结束时间 {focus_ts}", flush=True)

    def is_alive(pid: int) -> bool:
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False

    while time.time() < focus_ts:
        time.sleep(2)
        if not is_alive(main_pid):
            print("[guardian] main 已退出，准备拉起", flush=True)
            proc = subprocess.Popen([sys.executable, "--focus", str(focus_ts)], cwd=HERE)
            main_pid = proc.pid
            print(f"[guardian] main 已重启，新 pid={main_pid}", flush=True)

    print("[guardian] 专注已结束，守护退出", flush=True)


def _build_agent() -> PoisonTongueAgent | None:
    try:
        return PoisonTongueAgent()
    except Exception as exc:
        print(f"[Agent 初始化失败] {exc}", file=sys.stderr)
    return None


def _apply_agent_state(pet: PetWindow, *, agent: PoisonTongueAgent | None) -> None:
    pet.set_agent(agent)


def _initialize_agent_async(pet: PetWindow) -> None:
    def worker() -> None:
        try:
            agent = _build_agent()
            pet.root.after(0, lambda: _apply_agent_state(pet, agent=agent))
        except Exception as exc:
            print(f"[Agent 初始化失败] {exc}", file=sys.stderr)
            pet.root.after(0, lambda: _apply_agent_state(pet, agent=None))

    threading.Thread(target=worker, daemon=True).start()


def _parse_focus_end_from_argv() -> float:
    if "--focus" not in sys.argv:
        return 0.0
    idx = sys.argv.index("--focus")
    if idx + 1 >= len(sys.argv):
        return 0.0
    try:
        return float(sys.argv[idx + 1])
    except ValueError:
        return 0.0


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--guardian":
        _run_guardian()
        return

    if not _acquire_single_instance():
        _show_native_message("桌宠已在运行", "桌宠已经启动了，不会再打开第二只。")
        return

    current_focus_end = _parse_focus_end_from_argv()
    print("毒舌桌宠已启动，右键桌宠可以退出。", flush=True)

    pet = PetWindow()
    pet.set_focus_callback(lambda minutes: start_focus(pet, minutes))

    if current_focus_end > time.time():
        pet.set_focus_end(current_focus_end)

    pet.root.after(120, lambda: _initialize_agent_async(pet))

    monitor_thread = threading.Thread(target=_monitor_loop, args=(pet,), daemon=True)
    monitor_thread.start()

    try:
        pet.run()
    except KeyboardInterrupt:
        pass
    finally:
        _release_single_instance()


if __name__ == "__main__":
    main()
