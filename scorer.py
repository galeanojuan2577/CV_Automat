import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    PESOS_SCORING, BONOS_UBICACION, KEYWORDS_REMOTO,
    KEYWORDS_HIBRIDO, KEYWORDS_BOGOTA, MODELO_LLM,
    MODELO_FALLBACK, URL_OLLAMA,
)

logger = logging.getLogger("scorer")

SENIOR_KEYWORDS = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|head\s+(of|ing)?|director|vp\b|vice\s+president"
    r"|chief|cto|manager\s+(of|for)|arquitecto|architect|líder|lider)\b", re.I,
)

JUNIOR_KEYWORDS = re.compile(
    r"\b(junior|jr\.?|entry|trainee|intern|graduate|new\s*grad|associate|early\s+career"
    r"|sin experiencia|no experience)\b", re.I,
)

EXP_YEARS_RE = re.compile(
    r"(?:m[íi]nimo|minimum|at least|al menos|m[aá]ximo|maximum|up to|hasta|de|of)?"
    r"\s*(\d+)\s*(?:\+)?\s*(años|año|year|yr)s?\.?"
    r"\s*(?:de|of)?\s*(?:experiencia|experience)?", re.I,
)

EXP_BONUS = {
    "sin_experiencia": {0: 1.20, 1: 1.20, 2: 0.90, 3: 0.70, 5: 0.50},
    "proyectos_only":  {0: 1.15, 1: 1.15, 2: 1.05, 3: 0.85, 5: 0.65},
    "con_experiencia": {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 5: 1.00},
}

PROJECT_KEYWORDS = [
    [
        "scanner", "vulnerability", "web", "scan", "appsec", "owasp",
        "xss", "sqli", "cve", "llm", "ollama", "security testing",
        "offensive", "pentest", "burp", "recon", "exploit",
        "vulnerabilidad", "seguridad", "análisis", "ciberseguridad",
        "escáner", "web", "penetración", "riesgo", "automatización",
        "inteligencia artificial", "machine learning",
    ],
    [
        "monitor", "network", "ticket", "chatbot", "infrastructure",
        "telco", "telecom", "notification", "alert", "incident", "soc",
        "healthcheck", "queue", "concurrency",
        "monitoreo", "red", "infraestructura", "alerta", "incidente",
        "soporte", "telecomunicaciones", "notificación",
    ],
    [
        "web", "platform", "client", "legal", "document", "digitalization",
        "solution", "full-stack", "automation", "saas", "dashboard",
        "encryption", "forensic",
        "plataforma", "cliente", "legal", "documento", "digitalización",
        "solución", "automatización", "encriptación", "forense",
        "fullstack", "desarrollo web",
    ],
]


def analizar_ubicacion(texto_ubicacion):
    t = texto_ubicacion.lower()
    if any(k in t for k in KEYWORDS_REMOTO):
        return "remoto"
    if any(k in t for k in KEYWORDS_HIBRIDO):
        return "hibrido"
    if any(k in t for k in KEYWORDS_BOGOTA):
        return "presencial_bogota"
    return "presencial_otra"


def _coincidencias(lista_strings, texto):
    t = texto.lower()
    coinciden = 0
    for item in lista_strings:
        if isinstance(item, str) and item.lower() in t:
            coinciden += 1
    return coinciden


def _puntuar_skills(cv, texto_oferta):
    skills_planas = []
    for cat, skills_str in cv.get("skills", {}).items():
        for s in skills_str.split(","):
            s = s.strip()
            if s:
                skills_planas.append(s)
    if not skills_planas:
        return 0, []
    text = texto_oferta.lower()
    matched = [s for s in skills_planas if s.lower() in text]
    score = (len(matched) / len(skills_planas)) * PESOS_SCORING["skills"] * 100
    return score, matched


STOPWORDS = set("""
a ante bajo cabe con contra de desde durante en entre hacia hasta mediante para
por según sin so sobre tras y e o u el la los las lo un una unos unas
del al le les su sus tu mi tu mis tus nuestro nuestros
que cual quien quienes cuyo cuya cuyos cuyas como tan tanto
este esta estos estas ese esa esos esas aquel aquella aquellos aquellas
no si pero mas sino también ya bien aunque mientras pues porque
ser haber estar tener hacer poder decir entre parecer quedar
conocer ver llegar llegar dar sentir tomar venir
""".split())

def _puntuar_proyectos(cv, texto_oferta):
    proyectos = cv.get("projects", [])
    if not proyectos:
        return 0, []
    text_lower = texto_oferta.lower()

    # Tech-specific keyword match
    max_proyectos = min(len(proyectos), len(PROJECT_KEYWORDS))
    scored_tech = []
    for i in range(max_proyectos):
        keywords = PROJECT_KEYWORDS[i] if i < len(PROJECT_KEYWORDS) else PROJECT_KEYWORDS[-1]
        matches = sum(1 for kw in keywords if kw in text_lower)
        weight = matches / len(keywords) if keywords else 0
        scored_tech.append(weight * PESOS_SCORING["proyectos"] * 100)

    # General word-overlap match (for any job type)
    scored_general = []
    for p in proyectos:
        proj_text = " ".join(filter(None, [
            p.get("title", ""),
            p.get("subtitle", ""),
            p.get("impact", ""),
            " ".join(p.get("bullets", [])),
        ])).lower()
        proj_words = {w for w in proj_text.split() if len(w) > 3 and w not in STOPWORDS}
        if not proj_words:
            scored_general.append(0)
            continue
        offer_words = set(text_lower.split())
        overlap = proj_words & offer_words
        score = len(overlap) / len(proj_words) * PESOS_SCORING["proyectos"] * 100
        scored_general.append(score)

    matched_projects = []
    total = 0
    for i in range(len(proyectos)):
        tech = scored_tech[i] if i < len(scored_tech) else 0
        gen = scored_general[i] if i < len(scored_general) else 0
        best = max(tech, gen)
        total += best
        if best > 0:
            matched_projects.append(proyectos[i].get("title", f"Proyecto {i+1}"))

    avg = total / len(proyectos)
    return avg, matched_projects


def _puntuar_core_comp(cv, texto_oferta):
    comps = cv.get("core_competencies", [])
    if not comps:
        return 0, []
    texto_lower = texto_oferta.lower()
    matched = []
    for c in comps:
        c_lower = c.lower()
        if c_lower in texto_lower:
            matched.append(c)
        else:
            palabras = [p for p in c_lower.replace("/", " ").split() if len(p) > 3]
            if palabras and sum(1 for p in palabras if p in texto_lower) >= len(palabras) * 0.5:
                matched.append(c)
    score = (len(matched) / len(comps)) * PESOS_SCORING["core_comp"] * 100
    return score, matched


def _puntuar_educacion_certs(cv, texto_oferta):
    text = texto_oferta.lower()
    keywords_edu = []
    for edu in cv.get("education", []):
        if isinstance(edu, (list, tuple)) and len(edu) >= 1:
            keywords_edu.append(edu[0].lower())
    keywords_cert = []
    for cert in cv.get("certifications", []):
        if isinstance(cert, (list, tuple)) and len(cert) >= 1:
            keywords_cert.append(cert[0].lower())
    all_kw = keywords_edu + keywords_cert
    if not all_kw:
        return 0, []
    matched_kw = []
    for kw in all_kw:
        if kw in text:
            matched_kw.append(kw)
        else:
            palabras = [p for p in kw.split() if len(p) > 3]
            if palabras and sum(1 for p in palabras if p in text) >= len(palabras) * 0.5:
                matched_kw.append(kw)
    score = (len(matched_kw) / len(all_kw)) * PESOS_SCORING["educacion_certs"] * 100
    return score, matched_kw


def _puntuar_soft_skills(cv, texto_oferta):
    soft = cv.get("soft_skills", [])
    if not soft:
        return 0, []
    texto_lower = texto_oferta.lower()
    matched = []
    for s in soft:
        s_lower = s.lower()
        if s_lower in texto_lower:
            matched.append(s)
        else:
            palabras = [p for p in s_lower.split() if len(p) > 3]
            if palabras and sum(1 for p in palabras if p in texto_lower) >= len(palabras) * 0.5:
                matched.append(s)
    score = (len(matched) / len(soft)) * PESOS_SCORING["soft_skills"] * 100
    return score, matched


def _score_ubicacion(tipo_ubicacion):
    mult = BONOS_UBICACION.get(tipo_ubicacion, 1.0)
    return mult


def _analizar_experiencia_cv(cv):
    experiencias = cv.get("experiencia", [])
    proyectos = cv.get("projects", [])
    if experiencias:
        return "con_experiencia"
    if proyectos:
        return "proyectos_only"
    return "sin_experiencia"


def _extraer_anios_requeridos(texto_oferta):
    t = texto_oferta.lower()
    if JUNIOR_KEYWORDS.search(t):
        return 1
    if SENIOR_KEYWORDS.search(t):
        return 5
    match = EXP_YEARS_RE.search(t)
    if match:
        return int(match.group(1))
    return 2


def _calcular_bono_experiencia(cv, texto_oferta):
    perfil = _analizar_experiencia_cv(cv)
    anios = _extraer_anios_requeridos(texto_oferta)
    bucket = 0 if anios <= 1 else (2 if anios <= 2 else (3 if anios <= 4 else 5))
    mult = EXP_BONUS.get(perfil, {}).get(bucket, 1.0)
    etiqueta = {"sin_experiencia": "sin exp formal", "proyectos_only": "solo proyectos", "con_experiencia": "con exp formal"}
    return mult, f"{anios}año req, {etiqueta.get(perfil, perfil)}: ×{mult}"


def calcular_score(texto_oferta, cv, ubicacion=""):
    tipo_ubic = analizar_ubicacion(ubicacion or "")
    mult_ubic = _score_ubicacion(tipo_ubic)
    if mult_ubic == 0.0:
        return {
            "score_final": 0.0, "score_bruto": 0.0,
            "score_skills": 0.0, "score_proyectos": 0.0,
            "score_core": 0.0, "score_educacion": 0.0,
            "score_soft": 0.0, "multiplicador_ubicacion": mult_ubic,
            "multiplicador_experiencia": 1.0,
            "tipo_ubicacion": tipo_ubic,
            "skills_match": [], "proyectos_match": [],
            "core_match": [], "educacion_match": [],
            "soft_match": [], "razon_ia": "",
        }

    score_skills, skills_match = _puntuar_skills(cv, texto_oferta)
    score_proy, proy_match = _puntuar_proyectos(cv, texto_oferta)
    score_core, core_match = _puntuar_core_comp(cv, texto_oferta)
    score_edu, edu_match = _puntuar_educacion_certs(cv, texto_oferta)
    score_soft, soft_match = _puntuar_soft_skills(cv, texto_oferta)

    score_bruto = score_skills + score_proy + score_core + score_edu + score_soft

    mult_exp, razon_exp = _calcular_bono_experiencia(cv, texto_oferta)
    score_final = min(round(score_bruto * mult_ubic * mult_exp, 1), 100.0)

    return {
        "score_final": score_final,
        "score_bruto": round(score_bruto, 1),
        "score_skills": round(score_skills, 1),
        "score_proyectos": round(score_proy, 1),
        "score_core": round(score_core, 1),
        "score_educacion": round(score_edu, 1),
        "score_soft": round(score_soft, 1),
        "multiplicador_ubicacion": mult_ubic,
        "multiplicador_experiencia": mult_exp,
        "tipo_ubicacion": tipo_ubic,
        "razon_experiencia": razon_exp,
        "skills_match": skills_match,
        "proyectos_match": proy_match,
        "core_match": core_match,
        "educacion_match": edu_match,
        "soft_match": soft_match,
        "razon_ia": "",
    }


def _llamar_ollama(prompt, sistema, modelo=MODELO_LLM):
    import requests
    try:
        resp = requests.post(
            f"{URL_OLLAMA}/api/generate",
            json={
                "model": modelo,
                "prompt": prompt,
                "system": sistema,
                "stream": False,
                "options": {"temperature": 0.2, "max_tokens": 100},
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        logger.warning("Ollama error in scorer: %s", e)
        return None


def _puntuar_con_ia_individual(texto_oferta, cv):
    resumen = cv.get("resumen", "")[:300]
    skills_list = []
    for cat, skills_str in cv.get("skills", {}).items():
        skills_list.append(skills_str)
    skills_txt = ", ".join(skills_list)[:300]
    proyectos_txt = "; ".join(
        p.get("title", "") for p in cv.get("projects", [])
    )[:200]

    prompt = (
        f"OFERTA: {texto_oferta[:2000]}\n\n"
        f"PERFIL: {resumen}\n"
        f"SKILLS: {skills_txt}\n"
        f"PROYECTOS: {proyectos_txt}\n\n"
        "Evalúa la compatibilidad del perfil con la oferta. "
        "Responde SOLO con: SCORE:X RAZON:máximo 15 palabras"
    )
    sistema = "Eres un reclutador experto evaluando compatibilidad laboral. Sé objetivo y preciso."
    respuesta = _llamar_ollama(prompt, sistema)
    if not respuesta:
        return None

    score_match = re.search(r"SCORE:\s*(\d+)", respuesta, re.IGNORECASE)
    razon_match = re.search(r"RAZON:\s*(.+?)$", respuesta, re.IGNORECASE | re.DOTALL)
    score_ia = int(score_match.group(1)) if score_match else None
    razon = razon_match.group(1).strip() if razon_match else ""

    if score_ia is not None and 0 <= score_ia <= 100:
        return score_ia, razon
    return None


def calcular_score_con_ia(texto_oferta, cv, ubicacion=""):
    base = calcular_score(texto_oferta, cv, ubicacion)
    if base["multiplicador_ubicacion"] == 0.0:
        return base

    resultado_ia = _puntuar_con_ia_individual(texto_oferta, cv)
    if resultado_ia:
        score_ia, razon = resultado_ia
        base["score_final"] = round(base["score_bruto"] * 0.6 + score_ia * 0.4, 1)
        mult_total = base.get("multiplicador_experiencia", 1.0) * base["multiplicador_ubicacion"]
        base["score_final"] = min(base["score_final"] * mult_total, 100.0)
        base["score_final"] = round(base["score_final"], 1)
        base["razon_ia"] = razon
    return base


def calcular_scores_masivo(ofertas, cv):
    for oferta in ofertas:
        detalle = calcular_score(
            oferta.get("descripcion", "") or oferta.get("titulo", ""),
            cv,
            oferta.get("ubicacion", ""),
        )
        oferta["score"] = detalle["score_final"]
        oferta["detalle_score"] = detalle
    ofertas.sort(key=lambda o: o["score"], reverse=True)
    return ofertas


def calcular_scores_masivo_con_ia(ofertas, cv, on_progress=None):
    ofertas = calcular_scores_masivo(ofertas, cv)
    top = [o for o in ofertas if o["score"] > 0][:10]
    completados = 0

    def procesar_una(o):
        detalle_base = o["detalle_score"]
        resultado_ia = _puntuar_con_ia_individual(
            o.get("descripcion", "") or o.get("titulo", ""), cv
        )
        if resultado_ia:
            score_ia, razon = resultado_ia
            score_bruto = detalle_base["score_bruto"]
            score_hibrido = round(score_bruto * 0.6 + score_ia * 0.4, 1)
            mult_total = detalle_base.get("multiplicador_experiencia", 1.0) * detalle_base["multiplicador_ubicacion"]
            score_hibrido = min(score_hibrido * mult_total, 100.0)
            score_hibrido = round(score_hibrido, 1)
            o["score"] = score_hibrido
            o["detalle_score"]["score_final"] = score_hibrido
            o["detalle_score"]["razon_ia"] = razon
        return o

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(procesar_una, o): o for o in top}
        for future in as_completed(futures):
            completados += 1
            if on_progress:
                on_progress(completados, len(top))

    ofertas.sort(key=lambda o: o["score"], reverse=True)
    return ofertas
