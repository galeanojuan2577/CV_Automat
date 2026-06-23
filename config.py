import os
import shutil
from pathlib import Path

_HOME = Path(os.environ.get("HOME", "/home/user"))
_PROJECT_DIR = Path(os.environ.get("CV_AUTOMAT_DIR", _HOME / "Documentos/Personal/CV_Automat"))
_CV_DIR = Path(os.environ.get("CV_OUTPUT_DIR", _HOME / "Documentos/CV"))
_AUTO_CV_DIR = Path(os.environ.get("AUTO_CV_AGENT_DIR", _HOME / "auto-cv-agent"))
_CAREER_OPS_DIR = Path(os.environ.get("CAREER_OPS_DIR", _HOME / "career-ops"))

RUTA_BASE = _PROJECT_DIR
RUTA_CV_DIR = _CV_DIR
RUTA_CV_BASE = RUTA_BASE / "cv_base.json"
RUTA_CV_BASE_BAK = RUTA_BASE / "cv_base.json.bak"
RUTA_OFERTA = RUTA_BASE / "oferta.txt"
RUTA_CV_ADAPTADO_WORD = RUTA_CV_DIR / "CV_Adaptado.docx"
RUTA_CV_ADAPTADO_PDF = RUTA_CV_DIR / "CV_Adaptado.pdf"
LOG_FILE = RUTA_BASE / "asistente_cv.log"

RUTA_AUTO_CV_AGENT = _AUTO_CV_DIR
RUTA_CAREER_OPS = _CAREER_OPS_DIR

URL_OLLAMA = "http://localhost:11434"
MODELO_LLM = "llama3.2"
MODELO_FALLBACK = "qwen2.5:0.5b"

PESOS_SCORING = {
    "skills": 0.35,
    "proyectos": 0.25,
    "core_comp": 0.20,
    "educacion_certs": 0.10,
    "soft_skills": 0.10,
}

BONOS_UBICACION = {
    "remoto": 1.15,
    "hibrido": 1.05,
    "presencial_bogota": 0.90,
    "presencial_otra": 0.70,
}

KEYWORDS_REMOTO = ["remoto", "remote", "100% remoto", "work from home", "wfh", "a distancia", "teletrabajo"]
KEYWORDS_HIBRIDO = ["hibrido", "híbrido", "hybrid", "mixto", "presencial/remoto", "semipresencial"]
KEYWORDS_BOGOTA = ["bogota", "bogotá", "bog"]

FUENTES_JOBDROP = [
    "linkedin", "indeed", "glassdoor", "google", "wellfound",
    "remoteok", "weworkremotely", "zip_recruiter",
]

PLAYWRIGHT_TIMEOUT = 30000

BROWSERS = {
    "Firefox (bundled)": {"type": "firefox", "path": None},
    "Chromium (bundled)": {"type": "chromium", "path": None},
    "Brave": {"type": "chromium", "path": "/usr/bin/brave-browser"},
    "Chrome": {"type": "chromium", "path": None},
}

TERMINAL = (
    shutil.which("x-terminal-emulator")
    or shutil.which("gnome-terminal")
    or shutil.which("xfce4-terminal")
    or shutil.which("xterm")
    or "xterm"
)
