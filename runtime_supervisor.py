#!/usr/bin/env python3
"""Share the existing host; exit on child failure so its restart policy can recover."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent


def supervise(commands, stop=None, popen=subprocess.Popen):
    stop = stop or threading.Event()
    children = []
    try:
        for command in commands:
            if stop.is_set():
                break
            children.append(popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                  start_new_session=True))
        while not stop.is_set():
            if any(child.poll() is not None for child in children):
                # Even a clean unexpected exit means one worker is no longer running.
                return 1
            stop.wait(1)
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + 10
        for child in children:
            try:
                child.wait(timeout=max(0.01, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()


def main():
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    commands = [[sys.executable, str(ROOT/'content_worker.py')]]
    if os.getenv('APEX_REVENUE_WORKER_ENABLED', 'false').lower() == 'true':
        commands.append([sys.executable, str(ROOT/'revenue_worker.py')])
    return supervise(commands, stop)


if __name__ == '__main__':
    sys.exit(main())
