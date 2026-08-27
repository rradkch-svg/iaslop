"""
Ponto de entrada unificado para execução do Minuto Inexplicável Studio.
"""
import os
import sys
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

if __name__ == "__main__":
    app_path = os.path.join(SRC_DIR, "app.py")
    cmd = [sys.executable, "-m", "streamlit", "run", app_path, "--server.port", "8501", "--browser.gatherUsageStats", "false"]
    subprocess.run(cmd, cwd=PROJECT_ROOT)
