import logging
from pathlib import Path

import generar_documento as gendoc

logger = logging.getLogger("cv_maestro")

PROFILE = {
    "nombre": "Tu Nombre",
    "titulo": "Tu Título Profesional",
    "telefono": "",
    "email": "email@example.com",
    "linkedin": "",
    "github": "",
    "ciudad": "",
    "resumen": "",
    "core_competencies": [],
    "soft_skills": [],
    "skills": {},
    "projects": [],
    "education": [],
    "certifications": [],
}


def generar_cv_maestro(ruta=None):
    if ruta is None:
        from config import RUTA_CV_DIR
        ruta = RUTA_CV_DIR / "CV_Diego_Galeano_Maestro.pdf"
    ruta = Path(ruta)
    if ruta.suffix == ".pdf":
        return gendoc.generar_pdf(PROFILE, ruta_pdf=ruta)
    return gendoc.generar_word(PROFILE, ruta=ruta)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pdf = generar_cv_maestro()
    print(f"CV Maestro generado: {pdf}")
