import os
import sys
import time
import threading
import webbrowser
import urllib.request
from pathlib import Path
import uvicorn

# Ensure UTF-8 output stream on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

def open_browser_when_ready(url: str = "http://localhost:8000"):
    """Waits for the FastAPI server to respond and then opens the browser automatically."""
    for _ in range(30):
        time.sleep(0.3)
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            pass
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Não foi possível abrir o navegador automaticamente: {e}")

if __name__ == "__main__":
    os.chdir(APP_DIR)
    url = "http://localhost:8000"
    print("\n" + "=" * 60)
    print("🎬 YouTube AI Video Studio — High Retention Engine")
    print("=" * 60)
    print(f"🌐 Abrindo navegador em: {url}")
    print(f"📚 Documentação da API:  {url}/docs")
    print("=" * 60 + "\n")
    
    # Start auto-open in background thread
    threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True, app_dir=str(APP_DIR))
