import uvicorn
import os
import sys

# Ensure UTF-8 output stream on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("YouTube AI Video Studio - Professional Video Creation Pipeline")
    print("=" * 60)
    print("Server starting at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("=" * 60 + "\n")
    
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
