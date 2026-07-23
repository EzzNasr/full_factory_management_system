"""
ERP Launcher
------------
Double-click entry point for the Invoice App ERP.
Starts the FastAPI backend, starts the Vite frontend dev server,
waits until both ports are actually up, then opens your browser.

Closing this window (or Ctrl+C) shuts down both servers cleanly.
"""

import subprocess
import sys
import os
import socket
import time
import webbrowser

PROJECT_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # go up 2: Logic/ -> root
FRONTEND_DIR   = os.path.join(PROJECT_ROOT, "full_factory_management_system_ui") # where package.json lives

print("PROJECT_ROOT:", PROJECT_ROOT)
print("FRONTEND_DIR:", FRONTEND_DIR)

BACKEND_CMD    = [sys.executable, "-m", "uvicorn", "Logic.fastapi_app:app", "--reload"]

FRONTEND_CMD   = ["npm", "run", "dev"]

BACKEND_PORT   = 8000
FRONTEND_PORT  = 3000                  # Vite's default; check your vite.config.ts

# ──────────────────────────────────────────────────────────────────────────────


def wait_for_port(port, timeout=60, label=""):
    """Blocks until something is listening on localhost:port, or times out."""
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                print(f"  ✓ {label} is up on port {port}")
                return True
        time.sleep(0.5)
    print(f"  ⚠ Timed out waiting for {label} on port {port} — opening browser anyway.")
    return False


def main():
    print("Starting ERP...\n")

    # On Windows, CREATE_NEW_CONSOLE gives each server its own window so you can
    # see their logs / Ctrl+C them individually if something goes wrong.
    creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0

    print("[1/2] Launching backend (FastAPI)...")
    backend_proc = subprocess.Popen(
        BACKEND_CMD, cwd=PROJECT_ROOT, creationflags=creationflags
    )

    print("[2/2] Launching frontend (Vite)...")
    frontend_proc = subprocess.Popen(
        FRONTEND_CMD, cwd=FRONTEND_DIR, creationflags=creationflags, shell=(os.name == "nt")
    )

    try:
        print("\nWaiting for servers to come online...")
        wait_for_port(BACKEND_PORT, label="Backend")
        wait_for_port(FRONTEND_PORT, label="Frontend")

        url = f"http://localhost:{FRONTEND_PORT}"
        print(f"\nOpening {url}")
        webbrowser.open(url)

        print("\nERP is running. Close this window (or Ctrl+C) to stop both servers.")
        # Keep this launcher alive so it can clean up the children on exit.
        while True:
            time.sleep(1)
            # If either server process died on its own, stop everything.
            if backend_proc.poll() is not None or frontend_proc.poll() is not None:
                print("\nA server process exited unexpectedly — shutting down.")
                break

    except KeyboardInterrupt:
        print("\nShutting down...")

    finally:
        for proc, name in [(backend_proc, "backend"), (frontend_proc, "frontend")]:
            if proc.poll() is None:
                print(f"Stopping {name}...")
                if os.name == "nt":
                    # .terminate() only kills the cmd.exe/shell wrapper, not the
                    # node/uvicorn process it spawned underneath — taskkill /T
                    # kills the whole tree so the port actually gets freed.
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True
                    )
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    main()