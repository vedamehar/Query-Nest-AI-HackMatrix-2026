import asyncio
import sys
import uvicorn

def main():
    # ── WINDOWS PERMANENT FIX ────────────────────────────────
    # This MUST happen before any event loop is created.
    if sys.platform == 'win32':
        print("[SiteSense] Configuring Windows Proactor Event Loop...")
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Start Uvicorn programmatically
    print("[SiteSense] Starting FastAPI server on http://localhost:8000")
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
