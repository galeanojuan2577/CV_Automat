import json
import shutil
import sys
import logging
from pathlib import Path

from config import (
    RUTA_CV_BASE, RUTA_CV_BASE_BAK, RUTA_AUTO_CV_AGENT,
)

logger = logging.getLogger("cv_manager")

CV_TEMPLATE = {
    "nombre": "",
    "email": "",
    "telefono": "",
    "linkedin": "",
    "github": "",
    "ciudad": "",
    "resumen": "",
    "soft_skills": [],
    "core_competencies": [],
    "skills": {},
    "education": [],
    "certifications": [],
    "projects": [],
    "infra_items": [],
    "experiencia": [],
    "idiomas": [],
}


def _import_auto_cv_config():
    config_path = RUTA_AUTO_CV_AGENT / "config.py"
    if not config_path.exists():
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("auto_cv_config", str(config_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, "PROFILE", None)
    except Exception as e:
        logger.warning("Error importing auto-cv-agent/config.py: %s", e)
        return None


def _mapear_desde_config(p):
    cv = dict(CV_TEMPLATE)
    cv["nombre"] = p.get("name", "")
    cv["telefono"] = p.get("phone", "")
    cv["email"] = p.get("email", "")
    cv["linkedin"] = p.get("linkedin", "")
    cv["github"] = p.get("github", "")
    cv["ciudad"] = p.get("location", "")
    cv["soft_skills"] = list(p.get("soft_skills", []))
    cv["core_competencies"] = list(p.get("core_competencies", []))
    cv["skills"] = dict(p.get("skills", {}))
    cv["education"] = [list(e) for e in p.get("education", [])]
    cv["certifications"] = [list(c) for c in p.get("certifications", [])]
    cv["projects"] = [dict(pr) for pr in p.get("projects", [])]
    cv["infra_items"] = [list(i) for i in p.get("infra_items", [])]
    return cv


def _mapear_a_config(cv):
    return {
        "name": cv.get("nombre", ""),
        "phone": cv.get("telefono", ""),
        "email": cv.get("email", ""),
        "linkedin": cv.get("linkedin", ""),
        "github": cv.get("github", ""),
        "location": cv.get("ciudad", ""),
        "soft_skills": list(cv.get("soft_skills", [])),
        "core_competencies": list(cv.get("core_competencies", [])),
        "skills": dict(cv.get("skills", {})),
        "education": [tuple(e) for e in cv.get("education", [])],
        "certifications": [tuple(c) for c in cv.get("certifications", [])],
        "projects": [dict(p) for p in cv.get("projects", [])],
        "infra_items": [tuple(i) for i in cv.get("infra_items", [])],
    }


def cargar_cv():
    datos_auto = _import_auto_cv_config()
    if datos_auto:
        logger.info("CV loaded from auto-cv-agent/config.py")
        cv = _mapear_desde_config(datos_auto)
        guardar_cv(cv)
        return cv
    if RUTA_CV_BASE.exists():
        try:
            with open(RUTA_CV_BASE, "r", encoding="utf-8") as f:
                cv = json.load(f)
            _completar_template(cv)
            logger.info("CV loaded from cv_base.json")
            return cv
        except (json.JSONDecodeError, Exception) as e:
            logger.error("Error reading cv_base.json: %s", e)
            if RUTA_CV_BASE.exists():
                shutil.copy2(RUTA_CV_BASE, RUTA_CV_BASE_BAK)
                logger.info("Backup created: cv_base.json.bak")
    logger.info("No CV found, returning empty template")
    return dict(CV_TEMPLATE)


def guardar_cv(cv):
    _completar_template(cv)
    if RUTA_CV_BASE.exists():
        shutil.copy2(RUTA_CV_BASE, RUTA_CV_BASE_BAK)
    with open(RUTA_CV_BASE, "w", encoding="utf-8") as f:
        json.dump(cv, f, indent=2, ensure_ascii=False)
    exportar_a_auto_cv_agent(cv)
    logger.info("CV saved to cv_base.json and auto-cv-agent/config.py")


def exportar_a_auto_cv_agent(cv):
    profile = _mapear_a_config(cv)
    lines = ["PROFILE = " + json.dumps(profile, indent=4, ensure_ascii=False)]
    ruta = RUTA_AUTO_CV_AGENT / "config.py"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info("CV exported to auto-cv-agent/config.py")


def _completar_template(cv):
    for k, v in CV_TEMPLATE.items():
        if k not in cv:
            cv[k] = v
    for p in cv.get("projects", []):
        for pk in ("title", "tag", "subtitle", "bullets", "github", "impact"):
            if pk not in p:
                p[pk] = "" if pk != "bullets" else []
