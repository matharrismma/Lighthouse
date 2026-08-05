"""Engine launcher — selector event loop on Windows.

The proactor loop (Windows default) dies on `OSError: WinError 64` when a tunnel
client drops mid-accept: the accept loop exits, the server goes deaf on :8000,
and the watchdog restart-thrashes (an elevated console per cycle — the window
storm of 2026-08-05). The selector loop does not have that failure mode.
start_server.ps1 launches THIS instead of `-m uvicorn` so the policy is set
before uvicorn builds its loop.
"""
import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.app:app", host="0.0.0.0",
                port=int(os.environ.get("PORT", "8000")), workers=1)
