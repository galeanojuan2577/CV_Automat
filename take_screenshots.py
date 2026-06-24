import os, time, subprocess, signal, sys
from pathlib import Path

os.environ["CV_AUTOMAT_DIR"] = str(Path("/tmp/opencode/CV_Automat"))
os.environ["CV_OUTPUT_DIR"] = str(Path("/tmp/opencode/CV_Automat/screenshots"))
os.makedirs("/tmp/opencode/CV_Automat/screenshots", exist_ok=True)

SCREENSHOTS = Path("/tmp/opencode/CV_Automat/screenshots")

print("[1/5] Launching CV_Automat...")
proc = subprocess.Popen(
    [sys.executable, "main.py"],
    cwd="/tmp/opencode/CV_Automat",
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
time.sleep(4)

print("[2/5] Capturing main window (Mi CV tab)...")
subprocess.run(
    ["import", "-window", "root", str(SCREENSHOTS / "cv_editor.png")],
    timeout=10,
)
time.sleep(1)

print("[3/5] Switching to Buscar Ofertas tab...")
import pyautogui
except ImportError:
    print("pyautogui not available, using xdotool alternative")
    pass

proc.terminate()
proc.wait()
print("Done")
