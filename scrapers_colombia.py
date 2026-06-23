import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("scrapers_colombia")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

FORMATO_OFERTA = {
    "id": "",
    "titulo": "",
    "empresa": "",
    "ubicacion": "",
    "descripcion": "",
    "url": "",
    "fuente": "",
    "remoto": False,
    "fecha_publicacion": "",
    "score": 0.0,
    "detalle_score": None,
}


def _extraer_descripcion(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        texto = soup.get_text(separator="\n", strip=True)
        texto = re.sub(r"\n{3,}", "\n\n", texto)
        return texto[:4000]
    except Exception as e:
        logger.warning("No se pudo extraer descripción de %s: %s", url, e)
        return ""


def scrape_linkedin_colombia(search_term="", hours_old=72, results_wanted=20):
    try:
        import jobdrop
        from jobdrop import scrape_jobs

        df = scrape_jobs(
            site_name="linkedin",
            search_term=search_term or None,
            location="Colombia",
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
                "id": f"li_co_{url or titulo + empresa}",
                "titulo": titulo,
                "empresa": empresa,
                "ubicacion": ubicacion,
                "descripcion": desc,
                "url": url,
                "fuente": "linkedin_co",
                "remoto": "remote" in ubicacion.lower() or "remoto" in ubicacion.lower(),
                "fecha_publicacion": str(row.get("date_posted", "")),
                "score": 0.0,
                "detalle_score": None,
            })
        return ofertas
    except ImportError:
        logger.warning("jobdrop no instalado, LinkedIn Colombia no disponible")
        return []
    except Exception as e:
        logger.error("Error en LinkedIn Colombia: %s", e)
        return []


def scrape_computrabajo(search_term="", pages=1):
    ofertas = []
    base_url = "https://www.computrabajo.com.co"
    seen = set()

    for page in range(1, pages + 1):
        try:
            url = f"{base_url}/ofertas-de-trabajo/?q={requests.utils.quote(search_term)}&page={page}"
            if not search_term:
                url = f"{base_url}/ofertas-de-trabajo/?page={page}"
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.error("Error fetching Computrabajo page %d: %s", page, e)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.find_all("article", class_=lambda x: x and "box_offer" in x)

        for art in articles:
            try:
                h2 = art.find("h2")
                if not h2:
                    continue
                a = h2.find("a")
                if not a:
                    continue
                titulo = a.get_text(strip=True)
                rel_url = a.get("href", "")
                if not rel_url:
                    continue
                full_url = base_url + rel_url if rel_url.startswith("/") else rel_url
                if full_url in seen:
                    continue
                seen.add(full_url)

                company_link = art.select_one("a[offer-grid-article-company-url]")
                empresa = company_link.get_text(strip=True) if company_link else ""
                if not empresa:
                    first_p = art.select_one("p.dFlex.vm_fx.fs16.fc_base.mt5")
                    if first_p:
                        txt = first_p.get_text(strip=True)
                        txt = re.sub(r'^[\d,.]+\s*', '', txt).strip()
                        empresa = txt

                loc_ps = art.select("p.fs16.fc_base.mt5:not(.dFlex)")
                ubicacion = loc_ps[0].get_text(strip=True) if loc_ps else ""

                salary_tag = art.select_one("span.dIB.mr10 span.icon.i_salary")
                salario = ""
                if salary_tag and salary_tag.parent:
                    salario = salary_tag.parent.get_text(strip=True)

                tipo_trabajo = ""
                for span in art.find_all("span", class_="icon"):
                    icon_class = " ".join(span.get("class", []))
                    if "home_office" in icon_class:
                        parent = span.parent
                        if parent:
                            tipo_trabajo = parent.get_text(strip=True)
                        break

                es_remoto = any(k in (tipo_trabajo + " " + ubicacion).lower()
                                for k in ["remoto", "teletrabajo", "a distancia"])

                detalle_url = full_url.replace("#lc=", "?")
                o = dict(FORMATO_OFERTA)
                o.update({
                    "id": f"ct_{full_url}",
                    "titulo": titulo,
                    "empresa": empresa,
                    "ubicacion": ubicacion,
                    "descripcion": f"{titulo} - {empresa}\nUbicación: {ubicacion}\nSalario: {salario}\nTipo: {tipo_trabajo}",
                    "url": detalle_url,
                    "fuente": "computrabajo",
                    "remoto": es_remoto,
                })
                ofertas.append(o)
            except Exception as e:
                logger.warning("Error parsing Computrabajo card: %s", e)
                continue

        time.sleep(1)

    with ThreadPoolExecutor(max_workers=5) as ex:
        fut_map = {ex.submit(_extraer_descripcion, o["url"]): o for o in ofertas}
        for fut in as_completed(fut_map):
            o = fut_map[fut]
            try:
                desc = fut.result()
                if desc:
                    o["descripcion"] = desc
            except Exception:
                pass

    return ofertas


def scrape_elempleo(search_term="", pages=1):
    ofertas = []
    base_url = "https://www.elempleo.com"
    seen = set()

    for page in range(0, pages):
        try:
            params = {"keyword": search_term} if search_term else {}
            if page > 0:
                params["page"] = page
            url = f"{base_url}/co/ofertas-empleo/"
            resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.error("Error fetching Elempleo page %d: %s", page, e)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.find_all("div", class_="result-item")

        for item in items:
            try:
                h2 = item.find("h2")
                if not h2:
                    continue
                titulo = h2.get_text(strip=True)
                if not titulo or titulo in ("COP",):
                    continue

                oferta_url = ""
                for a in item.find_all("a", href=True):
                    href = a["href"]
                    if "/ofertas-trabajo/" in href.lower():
                        oferta_url = href if href.startswith("http") else base_url + href
                        break
                if not oferta_url or oferta_url in seen:
                    continue
                seen.add(oferta_url)

                h3 = item.find("h3")
                empresa = ""
                if h3:
                    empresa = h3.get_text(strip=True).replace("industry", "").strip()

                texto = item.get_text(separator="|", strip=True)
                partes = [p.strip() for p in texto.split("|") if p.strip()]

                ubicacion = ""
                salario = ""
                tipo_trabajo = ""
                for i, p in enumerate(partes):
                    p_lower = p.lower()
                    if p_lower.startswith("$") or "millones" in p_lower:
                        salario = p
                    elif p_lower in ("presencial", "híbrido", "hibrido", "remoto", "teletrabajo"):
                        tipo_trabajo = p
                    elif p_lower in ("bogotá", "medellín", "cali", "barranquilla", "cartagena",
                                     "bucaramanga", "pereira", "manizales", "cúcuta", "ibagué",
                                     "girardot", "soacha", "santa marta", "villavicencio",
                                     "pasto", "montería", "neiva", "armenia", "popayán",
                                     "sincelejo", "tunja", "riohacha", "florencia", "mocoa",
                                     "quibdó", "yopal", "san andrés", "leticia", "inírida",
                                     "mitú", "puerto carreño", "bogota", "cucuta"):
                        ubicacion = p
                    elif p_lower.startswith("salario") and i + 1 < len(partes):
                        if partes[i + 1].startswith("$"):
                            salario = partes[i + 1]

                es_remoto = tipo_trabajo.lower() == "remoto"

                o = dict(FORMATO_OFERTA)
                o.update({
                    "id": f"el_{oferta_url}",
                    "titulo": titulo,
                    "empresa": empresa,
                    "ubicacion": ubicacion,
                    "descripcion": f"{titulo} - {empresa}\nUbicación: {ubicacion}\nSalario: {salario}\nTipo: {tipo_trabajo}",
                    "url": oferta_url,
                    "fuente": "elempleo",
                    "remoto": es_remoto,
                })
                ofertas.append(o)
            except Exception as e:
                logger.warning("Error parsing Elempleo card: %s", e)
                continue

        time.sleep(1)

    with ThreadPoolExecutor(max_workers=5) as ex:
        fut_map = {ex.submit(_extraer_descripcion, o["url"]): o for o in ofertas}
        for fut in as_completed(fut_map):
            o = fut_map[fut]
            try:
                desc = fut.result()
                if desc:
                    o["descripcion"] = desc
            except Exception:
                pass

    return ofertas


def buscar_colombia(search_term="", hours_old=72, results_wanted=20):
    todas = []

    with ThreadPoolExecutor(max_workers=3) as ex:
        fut_linkedin = ex.submit(scrape_linkedin_colombia, search_term, hours_old, results_wanted)
        fut_compu = ex.submit(scrape_computrabajo, search_term, 2)
        fut_elem = ex.submit(scrape_elempleo, search_term, 2)

        for fut in as_completed([fut_linkedin, fut_compu, fut_elem]):
            try:
                resultados = fut.result()
                todas.extend(resultados)
            except Exception as e:
                logger.error("Error en scraper colombiano: %s", e)

    logger.info("Colombia scrapers: %d ofertas en total", len(todas))
    return todas
