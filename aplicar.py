import logging
import re
import subprocess
import sys
from pathlib import Path

from config import RUTA_CV_ADAPTADO_WORD, PLAYWRIGHT_TIMEOUT, BROWSERS

logger = logging.getLogger("aplicar")

SELECTORES_GENERICOS = {
    "aplicar": [
        "button:has-text('Apply')",
        "button:has-text('Solicitar')",
        "button:has-text('Postular')",
        "button:has-text('Easy Apply')",
        "a:has-text('Apply')",
        "a:has-text('Solicitar')",
        "button:has-text('Inscribirse')",
        "button:has-text('Enviar aplicación')",
    ],
    "nombre": [
        "input[name='name']",
        "input#name",
        "input[placeholder*='Name' i]",
        "input[placeholder*='Nombre' i]",
        "input[placeholder*='Full name' i]",
        "input[autocomplete='name']",
    ],
    "email": [
        "input[name='email']",
        "input#email",
        "input[placeholder*='Email' i]",
        "input[placeholder*='Correo' i]",
        "input[type='email']",
        "input[autocomplete='email']",
    ],
    "telefono": [
        "input[name='phone']",
        "input[type='tel']",
        "input[placeholder*='Tel' i]",
        "input[placeholder*='Phone' i]",
        "input[autocomplete='tel']",
    ],
    "archivo": [
        "input[type='file']",
    ],
    "siguiente": [
        "button:has-text('Next')",
        "button:has-text('Siguiente')",
        "button:has-text('Continue')",
        "button:has-text('Continuar')",
        "button[type='submit']",
    ],
    "revisar": [
        "button:has-text('Review')",
        "button:has-text('Revisar')",
        "button:has-text('Preview')",
    ],
    "enviar": [
        "button:has-text('Submit')",
        "button:has-text('Enviar')",
        "button[aria-label*='Submit' i]",
        "button:has-text('Send Application')",
    ],
}

SELECTORES_PORTAL = {
    "linkedin.com": {
        "aplicar": ["button:has-text('Easy Apply')"],
        "siguiente": ["button:has-text('Next')"],
        "revisar": ["button:has-text('Review')"],
        "enviar": ["button:has-text('Submit application')"],
    },
    "indeed.com": {
        "aplicar": ["button:has-text('Apply now')", "a:has-text('Apply now')"],
        "siguiente": ["button:has-text('Continue')", "button:has-text('Next')"],
        "enviar": ["button:has-text('Submit')", "button:has-text('Apply')"],
    },
    "computrabajo.com": {
        "aplicar": ["a:has-text('Postular')", "button:has-text('Postular')"],
        "enviar": ["button:has-text('Enviar')", "button[type='submit']"],
    },
    "infojobs.com": {
        "aplicar": ["button:has-text('Inscribirse')", "a:has-text('Inscribirse')"],
        "siguiente": ["button:has-text('Siguiente')"],
        "enviar": ["button:has-text('Enviar')"],
    },
}


def _detectar_portal(url):
    url_lower = url.lower()
    for dominio in SELECTORES_PORTAL:
        if dominio in url_lower:
            return dominio
    return "generico"


def _obtener_selectores(url):
    portal = _detectar_portal(url)
    if portal == "generico":
        return SELECTORES_GENERICOS
    base = dict(SELECTORES_GENERICOS)
    if portal in SELECTORES_PORTAL:
        for key, vals in SELECTORES_PORTAL[portal].items():
            base[key] = vals
    return base, portal


def _abrir_brave_directo(url, on_step=None):
    step = lambda msg: on_step(msg) if on_step else None
    brave_path = BROWSERS["Brave"]["path"]
    if not brave_path or not Path(brave_path).exists():
        step(f"ERROR: Brave no encontrado en {brave_path}")
        return False
    try:
        subprocess.Popen([brave_path, url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        step("Brave abierto con la URL de la oferta.")
        step("Como estás en tu navegador real, tus sesiones están activas.")
        step("Completa la aplicación manualmente.")
        step("Presiona 'Finalizar' cuando termines.")
        return True
    except Exception as e:
        step(f"ERROR: No se pudo abrir Brave: {e}")
        return False


def asistir_aplicacion(url, cv_data, ruta_cv=None, on_step=None, browser_name="Firefox (bundled)"):
    if not url or not url.startswith("http"):
        if on_step:
            on_step("ERROR: URL inválida")
        return False

    if ruta_cv is None:
        ruta_cv = RUTA_CV_ADAPTADO_WORD
    ruta_cv = Path(ruta_cv)

    step = lambda msg: on_step(msg) if on_step else None

    if browser_name == "Brave":
        return _abrir_brave_directo(url, on_step)

    if not ruta_cv.exists():
        step(f"ERROR: No se encuentra {ruta_cv.name}. Adapta el CV primero.")
        return False

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        step("ERROR: playwright no está instalado. Ejecuta: pip install playwright && playwright install firefox")
        return False

    selectores, portal = _obtener_selectores(url)

    try:
        with sync_playwright() as pw:
            cfg = BROWSERS.get(browser_name, BROWSERS["Firefox (bundled)"])
            browser_type = getattr(pw, cfg["type"])
            launch_kwargs = {"headless": False}
            if cfg["path"]:
                launch_kwargs["executable_path"] = cfg["path"]
                launch_kwargs.setdefault("args", []).extend(["--disable-single-instance", "--no-sandbox"])
            browser = browser_type.launch(**launch_kwargs)
            page = browser.new_page()
            page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

            step(f"Navegador: {browser_name}")
            step("Navegando a la URL...")
            page.goto(url, wait_until="domcontentloaded")

            step(f"Portal detectado: {portal}")

            def click_first(selectores_list):
                for sel in selectores_list:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=3000):
                            btn.click()
                            page.wait_for_timeout(1000)
                            return True
                    except Exception:
                        continue
                return False

            step("Buscando botón de aplicar...")
            if not click_first(selectores.get("aplicar", [])):
                step("⚠ No se encontró botón de aplicar. Continúa manualmente.")
                step("PAUSA: Revisa el navegador y completa los pasos iniciales.")
                page.wait_for_timeout(2000)
                input("Presiona ENTER en la terminal cuando estés listo...")

            def rellenar_campo(selectores_list, valor, label=""):
                for sel in selectores_list:
                    try:
                        campo = page.locator(sel).first
                        if campo.is_visible(timeout=2000):
                            campo.fill(valor)
                            step(f"  ✅ {label} rellenado: {valor[:30]}")
                            return True
                    except Exception:
                        continue
                step(f"  ⚠ No se encontró campo para: {label}")
                return False

            step("Rellenando campos del formulario...")
            rellenar_campo(selectores.get("nombre", []),
                           cv_data.get("nombre", ""), "Nombre")
            rellenar_campo(selectores.get("email", []),
                           cv_data.get("email", ""), "Email")
            rellenar_campo(selectores.get("telefono", []),
                           cv_data.get("telefono", ""), "Teléfono")

            step("Adjuntando CV...")
            cv_adjuntado = False
            for sel in selectores.get("archivo", []):
                try:
                    campo_file = page.locator(sel).first
                    if campo_file.is_visible(timeout=2000):
                        campo_file.set_input_files(str(ruta_cv.resolve()))
                        step(f"  ✅ CV adjuntado: {ruta_cv.name}")
                        cv_adjuntado = True
                        break
                except Exception:
                    continue
            if not cv_adjuntado:
                step("⚠ No se encontró campo para adjuntar CV. Adjúntalo manualmente.")

            step("=" * 50)
            step("REVISA LOS DATOS EN EL NAVEGADOR.")
            step("Presiona 'Continuar' cuando estés listo para el siguiente paso,")
            step("o 'Finalizar' para cerrar el navegador.")
            step("=" * 50)

            browser.close()
            step("Navegador cerrado.")
            return True

    except Exception as e:
        logger.exception("Error en Playwright: %s", e)
        if on_step:
            step(f"ERROR: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 aplicar.py --url URL [--cv RUTA] [--nombre NOMBRE] [--email EMAIL] [--telefono TEL] [--browser BROWSER]")
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser(description="Asistente de aplicación vía Playwright")
    parser.add_argument("--url", required=True, help="URL de la oferta")
    parser.add_argument("--cv", default=str(RUTA_CV_ADAPTADO_WORD), help="Ruta al CV")
    parser.add_argument("--nombre", default="", help="Nombre del candidato")
    parser.add_argument("--email", default="", help="Email")
    parser.add_argument("--telefono", default="", help="Teléfono")
    parser.add_argument("--browser", default="Firefox (bundled)", help="Navegador a usar")
    args = parser.parse_args()

    def log(msg):
        print(f"  {msg}")

    cv_data = {
        "nombre": args.nombre,
        "email": args.email,
        "telefono": args.telefono,
    }
    exito = asistir_aplicacion(args.url, cv_data, args.cv, on_step=log, browser_name=args.browser)
    sys.exit(0 if exito else 1)


if __name__ == "__main__":
    main()
