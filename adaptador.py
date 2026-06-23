import logging
import re
import time

import requests

from config import URL_OLLAMA, MODELO_LLM, MODELO_FALLBACK

logger = logging.getLogger("adaptador")

PROMPTS = {
    "resumen": (
        "Basado ESTRICTAMENTE en el RESUMEN ORIGINAL y la OFERTA, "
        "reorganiza el énfasis para alinearlo con la oferta. "
        "NO CAMBIES ningún hecho, título, especialización o logro. "
        "NO inventes información. NO modifiques el perfil profesional. "
        "Máximo 3 oraciones. Sin comillas ni prefijos."
    ),
    "experiencia": (
        "Reescribe la siguiente experiencia laboral ({puesto} en {empresa}) "
        "para alinearla con la oferta de trabajo. Enfatiza logros y tecnologías relevantes. "
        "No inventes información falsa. Máximo 3 líneas. "
        "Devuelve solo el texto adaptado, sin comillas ni prefijos."
    ),
    "skills": (
        "Reordena las siguientes habilidades según su relevancia para la oferta de trabajo. "
        "Las más relevantes primero. No añadas ni elimines habilidades. "
        "Devuelve solo la lista separada por comas, sin texto adicional."
    ),
}


def verificar_ollama():
    try:
        resp = requests.get(f"{URL_OLLAMA}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False, f"Ollama respondió con código {resp.status_code}"
        modelos = resp.json().get("models", [])
        disponibles = [m["name"] for m in modelos]
        if MODELO_LLM not in disponibles and MODELO_FALLBACK not in disponibles:
            return False, f"No se encontró {MODELO_LLM} ni {MODELO_FALLBACK}. Ejecuta: ollama pull {MODELO_LLM}"
        return True, "Ollama disponible"
    except requests.exceptions.ConnectionError:
        return False, "Ollama no está corriendo. Ejecuta: ollama serve"
    except Exception as e:
        return False, f"Error al conectar con Ollama: {e}"


def _llamar_ollama(prompt, sistema="", modelo=MODELO_LLM, timeout=60):
    modelo_usar = modelo
    try:
        resp = requests.get(f"{URL_OLLAMA}/api/tags", timeout=3)
        if resp.status_code == 200:
            disponibles = [m["name"] for m in resp.json().get("models", [])]
            if modelo_usar not in disponibles:
                modelo_usar = MODELO_FALLBACK
                logger.info("Falling back to %s", modelo_usar)
    except Exception:
        modelo_usar = MODELO_FALLBACK
        logger.info("Cannot check models, falling back to %s", modelo_usar)

    for intento in range(3):
        try:
            resp = requests.post(
                f"{URL_OLLAMA}/api/generate",
                json={
                    "model": modelo_usar,
                    "prompt": prompt,
                    "system": sistema,
                    "stream": False,
                    "options": {"temperature": 0.3, "max_tokens": 500},
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            texto = resp.json()["response"].strip()
            return _limpiar_respuesta(texto)
        except requests.exceptions.Timeout:
            logger.warning("Ollama timeout (intento %d/3)", intento + 1)
            time.sleep(2)
        except Exception as e:
            logger.error("Ollama error (intento %d/3): %s", intento + 1, e)
            time.sleep(2)
    return None


def _limpiar_respuesta(texto):
    texto = re.sub(r'^["\']+|["\']+$', "", texto)
    texto = re.sub(r"^(Aquí está|Claro|Por supuesto|Aquí tienes)[^:]*:?\s*", "", texto, flags=re.IGNORECASE)
    return texto.strip()


def adaptar_resumen(texto_original, texto_oferta, cv=None):
    prompt = f"{PROMPTS['resumen']}\n\nRESUMEN ORIGINAL:\n{texto_original}\n\nOFERTA:\n{texto_oferta[:2000]}"
    respuesta = _llamar_ollama(prompt, "Eres un asistente que adapta currículums vitae profesionalmente.", timeout=90)
    if respuesta:
        for area in cv.get("core_competencies", []) if cv else []:
            if area.lower() not in respuesta.lower():
                pass
        return respuesta
    return texto_original


def adaptar_experiencia(puesto, empresa, descripcion, texto_oferta):
    prompt_text = PROMPTS["experiencia"].format(puesto=puesto, empresa=empresa)
    prompt = f"{prompt_text}\n\nDESCRIPCIÓN ORIGINAL:\n{descripcion}\n\nOFERTA:\n{texto_oferta[:2000]}"
    respuesta = _llamar_ollama(prompt, "Eres un asistente que adapta currículums vitae profesionalmente.")
    return respuesta if respuesta else descripcion


def adaptar_skills_texto(skills_texto, texto_oferta):
    prompt = f"{PROMPTS['skills']}\n\nHABILIDADES:\n{skills_texto}\n\nOFERTA:\n{texto_oferta[:2000]}"
    respuesta = _llamar_ollama(prompt, "Eres un asistente que adapta currículums vitae profesionalmente.")
    return respuesta if respuesta else skills_texto


def adaptar_cv_completo(cv, texto_oferta, on_step=None):
    nuevo = dict(cv)

    if on_step:
        on_step("Adaptando resumen profesional...")
    nuevo["resumen"] = adaptar_resumen(cv.get("resumen", ""), texto_oferta, cv)

    if on_step:
        on_step("Adaptando habilidades...")
    skills_lines = []
    for cat, skills_str in cv.get("skills", {}).items():
        skills_lines.append(f"{cat}: {skills_str}")
    skills_texto = "\n".join(skills_lines)
    skills_adaptado = adaptar_skills_texto(skills_texto, texto_oferta)
    if skills_adaptado and skills_adaptado != skills_texto:
        nuevo["skills"] = {}
        for line in skills_adaptado.split("\n"):
            if ":" in line:
                cat, vals = line.split(":", 1)
                nuevo["skills"][cat.strip()] = vals.strip()

    experiencias = cv.get("experiencia", [])
    nuevas_exp = []
    for i, exp in enumerate(experiencias):
        if on_step:
            on_step(f"Adaptando experiencia: {exp.get('puesto', '')}...")
        desc_adaptada = adaptar_experiencia(
            exp.get("puesto", ""),
            exp.get("empresa", ""),
            exp.get("descripcion", ""),
            texto_oferta,
        )
        nueva_exp = dict(exp)
        nueva_exp["descripcion"] = desc_adaptada
        nuevas_exp.append(nueva_exp)
    nuevo["experiencia"] = nuevas_exp

    return nuevo
