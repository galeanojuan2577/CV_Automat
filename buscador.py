import csv
import io
import logging
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    RUTA_CAREER_OPS, FUENTES_JOBDROP,
)
from scorer import calcular_score

logger = logging.getLogger("buscador")


def _jobdrop_disponible():
    try:
        import jobdrop
        return True
    except ImportError:
        return False


def buscar_jobdrop(search_term="", location="", is_remote=False,
                   hours_old=72, results_wanted=20):
    if not _jobdrop_disponible():
        logger.warning("jobdrop no está instalado")
        return []
    try:
        from jobdrop import scrape_jobs
        df = scrape_jobs(
            site_name=FUENTES_JOBDROP,
            search_term=search_term or None,
            location=location or None,
            is_remote=is_remote,
            results_wanted=results_wanted,
            hours_old=hours_old if hours_old > 0 else None,
            description_format="markdown",
            verbose=0,
        )
        if df is None or df.empty:
            return []
        ofertas = []
        for _, row in df.iterrows():
            desc = str(row.get("description") or row.get("text") or "")
            titulo = str(row.get("title", ""))
            empresa = str(row.get("company", ""))
            ubicacion = str(row.get("location", ""))
            url = str(row.get("url", ""))
            ofertas.append({
                "id": url or titulo + empresa,
                "titulo": titulo,
                "empresa": empresa,
                "ubicacion": ubicacion,
                "descripcion": desc,
                "url": url,
                "fuente": "jobdrop",
                "remoto": is_remote,
                "fecha_publicacion": str(row.get("date_posted", "")),
                "score": 0.0,
                "detalle_score": None,
            })
        return ofertas
    except Exception as e:
        logger.error("Error en jobdrop: %s", e)
        return []


def _parsear_tsv_career_ops(texto_tsv):
    ofertas = []
    reader = csv.reader(io.StringIO(texto_tsv), delimiter="\t")
    for row in reader:
        if len(row) >= 7:
            url, fecha, fuente, titulo, empresa, estado, ubicacion = row[:7]
            if estado.strip() == "added":
                ofertas.append({
                    "id": url.strip(),
                    "titulo": titulo.strip(),
                    "empresa": empresa.strip(),
                    "ubicacion": ubicacion.strip(),
                    "descripcion": "",
                    "url": url.strip(),
                    "fuente": "career-ops",
                    "remoto": "remote" in ubicacion.lower() or "remoto" in ubicacion.lower(),
                    "fecha_publicacion": fecha.strip(),
                    "score": 0.0,
                    "detalle_score": None,
                })
    return ofertas


def buscar_career_ops():
    if not RUTA_CAREER_OPS.exists():
        logger.warning("career-ops no encontrado en %s", RUTA_CAREER_OPS)
        return []
    try:
        result = subprocess.run(
            ["node", "scan.mjs", "--dry-run"],
            cwd=str(RUTA_CAREER_OPS),
            capture_output=True, text=True, timeout=120,
        )
        tsv_path = RUTA_CAREER_OPS / "data" / "scan-history.tsv"
        if tsv_path.exists():
            with open(tsv_path, "r", encoding="utf-8") as f:
                contenido = f.read()
            return _parsear_tsv_career_ops(contenido)
        return []
    except FileNotFoundError:
        logger.warning("node no encontrado o scan.mjs no existe en career-ops")
        return []
    except subprocess.TimeoutExpired:
        logger.warning("career-ops scan timeout")
        return []
    except Exception as e:
        logger.error("Error en career-ops: %s", e)
        return []


def _deduplicar(ofertas):
    vistos = set()
    unicas = []
    for o in ofertas:
        key = o["id"]
        if key not in vistos:
            vistos.add(key)
            unicas.append(o)
    return unicas


def _extraer_descripcion_por_url(url):
    import requests
    from bs4 import BeautifulSoup
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        texto = soup.get_text(separator="\n", strip=True)
        texto = re.sub(r"\n{3,}", "\n\n", texto)
        return texto[:3000]
    except Exception as e:
        logger.warning("No se pudo extraer descripción de %s: %s", url, e)
        return ""


def enriquecer_descripcion(oferta):
    if not oferta.get("descripcion") and oferta.get("url"):
        desc = _extraer_descripcion_por_url(oferta["url"])
        oferta["descripcion"] = desc
    return oferta


_FILTERS_MODULE = None

def _cargar_filtros():
    global _FILTERS_MODULE
    if _FILTERS_MODULE is not None:
        return _FILTERS_MODULE
    try:
        import importlib.util
        from config import RUTA_BASE
        filters_path = RUTA_BASE / "filters.py"
        if not filters_path.exists():
            alt = Path(os.environ.get("FILTERS_PY_PATH", ""))
            if alt.exists():
                filters_path = alt
        if filters_path.exists():
            spec = importlib.util.spec_from_file_location("filters_module", str(filters_path))
            _FILTERS_MODULE = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_FILTERS_MODULE)
            return _FILTERS_MODULE
    except Exception as e:
        logger.warning("No se pudieron cargar filtros: %s", e)
    return None


def _texto_busqueda(oferta):
    return f"{oferta.get('titulo', '')} {oferta.get('descripcion', '')} {oferta.get('ubicacion', '')}"


def _clasificar_nivel_experiencia(oferta):
    try:
        from scorer import SENIOR_KEYWORDS, JUNIOR_KEYWORDS, EXP_YEARS_RE
    except ImportError:
        return ""
    texto = _texto_busqueda(oferta).lower()

    is_senior = bool(SENIOR_KEYWORDS.search(texto))
    is_junior = bool(JUNIOR_KEYWORDS.search(texto))

    match = EXP_YEARS_RE.search(texto)
    anios = int(match.group(1)) if match else 0

    if anios >= 5 or is_senior:
        if any(k in texto for k in ["lead", "manager", "director", "head", "vp", "chief", "cto"]):
            return "lead"
        return "senior"
    if anios >= 3:
        return "semi-senior"
    if anios <= 1 or is_junior:
        if anios > 0 or is_junior:
            return "junior"
    return ""


def _aplicar_filtros(ofertas, ubicacion_filter="", ingles_min="", filtro_experiencia=""):
    flt = _cargar_filtros()
    filtradas = []

    for o in ofertas:
        titulo = o.get("titulo", "")
        desc = o.get("descripcion", "")
        ubic = o.get("ubicacion", "")
        texto = _texto_busqueda(o)

        if ubicacion_filter == "remoto":
            if flt:
                ok, _ = flt.passes_location(titulo, desc, ubic, remote_only=True)
                if not ok:
                    continue
            elif "remoto" not in texto.lower() and "remote" not in texto.lower():
                continue
        elif ubicacion_filter == "bogota":
            if not any(k in ubic.lower() for k in ["bogota", "bogotá", "bog"]):
                continue
        elif ubicacion_filter == "colombia":
            pass

        if filtro_experiencia:
            nivel = _clasificar_nivel_experiencia(o)
            if nivel != filtro_experiencia:
                continue

        if ingles_min and flt:
            text_lower = texto.lower()
            nivel_ing = ingles_min.lower()
            menciona_idioma = any(k in text_lower for k in [
                "english", "inglés", "ingles", "b1", "b2", "c1", "c2",
                "native", "nativo", "fluent", "fluido",
                "advanced", "avanzado", "intermediate", "intermedio", "basic", "básico",
                "bilingüe", "bilingue",
            ])
            if not menciona_idioma:
                filtradas.append(o)
                continue
            nivel_min = {"b1": 1, "b2": 2, "c1": 3, "nativo": 4}
            nivel_requerido = 0
            if any(k in text_lower for k in ["native", "nativo", "bilingüe", "bilingue"]):
                nivel_requerido = 4
            elif any(k in text_lower for k in ["c1", "c2", "advanced", "avanzado", "fluent", "fluido"]):
                nivel_requerido = 3
            elif any(k in text_lower for k in ["b2", "intermediate", "intermedio"]):
                nivel_requerido = 2
            elif any(k in text_lower for k in ["b1", "basic", "básico"]):
                nivel_requerido = 1
            if nivel_requerido > nivel_min.get(nivel_ing, 0):
                continue

        filtradas.append(o)

    return filtradas


def buscar_todo(search_term="", location="", fuente="todas",
                solo_remoto=False, hours_old=72, results_wanted=20,
                cv=None,
                ubicacion_filter="", ingles_min="", filtro_experiencia=""):
    todas = []

    usar_jobdrop = fuente in ("jobdrop", "todas")
    usar_career = fuente in ("career-ops", "todas")
    usar_colombia = fuente in ("colombia", "todas")

    if usar_jobdrop:
        jd = buscar_jobdrop(search_term, location, solo_remoto,
                            hours_old, results_wanted)
        todas.extend(jd)

    if usar_career:
        co = buscar_career_ops()
        todas.extend(co)

    if usar_colombia:
        from scrapers_colombia import buscar_colombia
        co_scrapers = buscar_colombia(search_term, hours_old, results_wanted)
        todas.extend(co_scrapers)

    todas = _deduplicar(todas)

    todas = _aplicar_filtros(todas, ubicacion_filter, ingles_min, filtro_experiencia)

    if cv:
        sin_desc = [o for o in todas if not o.get("descripcion")]
        if sin_desc:
            with ThreadPoolExecutor(max_workers=10) as ex:
                list(ex.map(enriquecer_descripcion, sin_desc))

        for o in todas:
            texto = o.get("descripcion", "") or ""
            if not texto:
                texto = f"{o.get('titulo', '')} {o.get('empresa', '')} {o.get('ubicacion', '')}"
            detalle = calcular_score(texto, cv, o.get("ubicacion", ""))
            o["score"] = detalle["score_final"]
            o["detalle_score"] = detalle
        todas.sort(key=lambda o: o["score"], reverse=True)

    return todas
