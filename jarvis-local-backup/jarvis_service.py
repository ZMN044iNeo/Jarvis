#!/usr/bin/env python3
"""
jarvis_service.py - simple manager to start/stop/status/logs for Jarvis on Windows.
Usage: python jarvis_service.py start|stop|status|logs [--lines N]

Starts jarvis.py using the project's .venv python, writes jarvis.pid and appends logs to jarvis.log.
"""
import os
import sys
import subprocess
import signal
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(ROOT, '.venv', 'Scripts', 'python.exe')
JARVIS_PY = os.path.join(ROOT, 'jarvis.py')
PID_FILE = os.path.join(ROOT, 'jarvis.pid')
LOG_FILE = os.path.join(ROOT, 'jarvis.log')

def is_running(pid):
    try:
        # Use tasklist to check for pid on Windows
        out = subprocess.check_output(['tasklist', '/FI', f'PID eq {pid}'], text=True)
        return str(pid) in out
    except Exception:
        return False

def start():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            if is_running(pid):
                print(f"Jarvis already running with PID {pid}")
                return
            else:
                print("Stale PID file found, starting a new process")
        except Exception:
            pass
    python = VENV_PY if os.path.exists(VENV_PY) else sys.executable
    logfile = open(LOG_FILE, 'ab')
    # DETACHED_PROCESS flag on Windows is 0x00000008
    creationflags = 0x00000008
    proc = subprocess.Popen([python, JARVIS_PY], stdout=logfile, stderr=logfile, stdin=subprocess.DEVNULL, creationflags=creationflags)
    pid = proc.pid
    with open(PID_FILE, 'w') as f:
        f.write(str(pid))
    print(f"Started Jarvis with PID {pid}; logs -> {LOG_FILE}")

def stop():
    if not os.path.exists(PID_FILE):
        print("No PID file found; Jarvis may not be running")
        return
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
    except Exception:
        print("Could not read PID file")
        return
    try:
        subprocess.check_call([
            'powershell.exe',
            '-NoLogo',
            '-NoProfile',
            '-NonInteractive',
            '-Command',
            f'Stop-Process -Id {pid} -Force'
        ])
        print(f"Stopped Jarvis PID {pid}")
    except subprocess.CalledProcessError:
        print(f"Failed to stop process {pid}. It may have already exited.")
    try:
        os.remove(PID_FILE)
    except Exception:
        pass

def status():
    if not os.path.exists(PID_FILE):
        print("Jarvis is not running (no PID file)")
        return
    with open(PID_FILE, 'r') as f:
        pid = int(f.read().strip())
    running = is_running(pid)
    print(f"PID: {pid} Running: {running} Log: {LOG_FILE}")

def logs(lines=200):
    if not os.path.exists(LOG_FILE):
        print("No log file yet")
        return
    try:
        with open(LOG_FILE, 'rb') as f:
            data = f.read().splitlines()
            for line in data[-lines:]:
                try:
                    print(line.decode('utf-8', errors='replace'))
                except Exception:
                    print(line)
    except Exception as e:
        print(f"Could not read log file: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd == 'start':
        start()
    elif cmd == 'stop':
        stop()
    elif cmd == 'status':
        status()
    elif cmd == 'logs':
        n = 200
        if len(sys.argv) > 2 and sys.argv[2].isdigit():
            n = int(sys.argv[2])
        logs(n)
    else:
        print('Unknown command')
        print(__doc__)
