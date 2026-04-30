"""
守护进程：监视 main.py 进程，被杀就重启。由 main.py 在专注模式启动时拉起。
"""
import sys
import os
import time
import subprocess
import psutil

POLL = 2
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(HERE, "main.py")


def is_alive(pid: int) -> bool:
    try:
        p = psutil.Process(pid)
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def main():
    if len(sys.argv) < 3:
        print("[guardian] 参数不足，退出", flush=True)
        return

    main_pid = int(sys.argv[1])
    focus_end = float(sys.argv[2])

    print(f"[guardian] 启动，守护 main pid={main_pid}，专注结束={focus_end}", flush=True)

    while time.time() < focus_end:
        time.sleep(POLL)
        if not is_alive(main_pid):
            print("[guardian] main.py 被杀，重启中...", flush=True)
            proc = subprocess.Popen(
                [sys.executable, MAIN_SCRIPT, "--focus", str(focus_end)],
                cwd=HERE,
            )
            main_pid = proc.pid
            print(f"[guardian] main.py 已重启，新 pid={main_pid}", flush=True)

    print("[guardian] 专注结束，守护退出。", flush=True)


if __name__ == "__main__":
    main()
