import logging
from pathlib import Path

from weasyprint import HTML

logger = logging.getLogger("generar_pdf_html")

HEADER_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
@page {{
    size: A4;
    margin: 1.2cm 1.2cm 1.0cm 1.2cm;
}}

body {{
    font-family: "Liberation Sans", "DejaVu Sans", Arial, Helvetica, sans-serif;
    font-size: 8pt;
    color: #1a2744;
    line-height: 1.2;
    margin: 0;
    padding: 0;
}}

/* ── HEADER ─────────────────────────────────────────── */
.name {{
    font-size: 16pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2pt;
    margin: 0 0 1pt 0;
    color: #1a2744;
    text-align: center;
}}

.title {{
    font-size: 8.5pt;
    color: #3a5a7a;
    margin: 0 0 2pt 0;
    text-align: center;
}}

.header-line {{
    border: none;
    border-top: 1.5pt solid #1a2744;
    margin: 4pt auto 5pt auto;
    width: 70%;
}}

.contact {{
    font-size: 7pt;
    color: #4a5a6a;
    margin: 0 0 5pt 0;
    text-align: center;
}}
.contact span.sep {{
    color: #8a9aaa;
    margin: 0 3pt;
}}

/* ── SECTIONS ────────────────────────────────────────── */
.section {{
    margin: 5pt 0 0 0;
}}
.section-title {{
    font-size: 9pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8pt;
    border-bottom: 1pt solid #1a2744;
    padding-bottom: 1pt;
    margin: 0 0 3pt 0;
    color: #1a2744;
}}

.profile-text {{
    font-size: 7.5pt;
    color: #2a3a4a;
    text-align: justify;
    margin: 1pt 0 2pt 0;
}}

.competencies {{
    font-size: 7.5pt;
    color: #1a2744;
    margin: 1pt 0;
    line-height: 1.45;
    background: #f0f3f8;
    padding: 3pt 5pt;
    border-radius: 2pt;
}}

/* ── SKILLS TABLE ────────────────────────────────────── */
.skills-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 0;
}}
.skills-table td {{
    vertical-align: top;
    padding: 0.5pt 0;
    font-size: 7.5pt;
}}
.skills-table td:first-child {{
    width: 22%;
    font-weight: 700;
    color: #1a2744;
    padding-right: 6pt;
}}
.skills-table td:last-child {{
    color: #2a3a4a;
}}

/* ── SOFT SKILLS ─────────────────────────────────────── */
.soft-skills {{
    font-size: 7.5pt;
    color: #2a3a4a;
    margin: 1pt 0;
    line-height: 1.4;
}}

/* ── PROJECTS ────────────────────────────────────────── */
.project {{
    margin: 3pt 0 0 0;
}}
.project-title {{
    font-size: 8.5pt;
    font-weight: 700;
    color: #1a2744;
    margin: 0;
}}
.project-tag {{
    font-size: 7pt;
    font-weight: 600;
    color: #3a6a8a;
    text-transform: uppercase;
    margin: 0;
}}
.project-subtitle {{
    font-size: 7pt;
    font-style: italic;
    color: #4a6a7a;
    margin: 0;
}}
.project-gh {{
    font-size: 6.5pt;
    color: #6a8aaa;
    margin: 0 0 1pt 0;
}}
.project ul {{
    list-style: none;
    padding: 0;
    margin: 0 0 1pt 0;
}}
.project ul li {{
    font-size: 7pt;
    color: #2a3a4a;
    padding-left: 10pt;
    position: relative;
    margin: 0;
    line-height: 1.25;
}}
.project ul li::before {{
    content: "\\25B8";
    position: absolute;
    left: 1pt;
    color: #3a6a8a;
    font-size: 7pt;
}}
.project-impact {{
    font-size: 7pt;
    color: #2a3a4a;
    margin: 0;
}}
.project-impact strong {{
    color: #1a2744;
}}

/* ── EDUCATION ENTRIES ──────────────────────────────── */
.entry {{
    font-size: 7.5pt;
    margin: 1pt 0;
}}
.entry-title {{
    font-weight: 700;
    color: #1a2744;
}}
.entry-sub {{
    color: #4a6a7a;
}}
.entry-year {{
    color: #7a8a9a;
}}

/* ── CERTIFICATIONS (2-COLUMN) ──────────────────────── */
.certs {{
    list-style: none;
    padding: 0;
    margin: 0;
    column-count: 2;
    column-gap: 10pt;
}}
.certs li {{
    font-size: 7pt;
    margin: 0 0 0.5pt 0;
    padding-left: 8pt;
    position: relative;
    break-inside: avoid;
    color: #2a3a4a;
}}
.certs li::before {{
    content: "\\25B8";
    position: absolute;
    left: 0;
    color: #3a6a8a;
    font-size: 7pt;
}}
.cert-org {{
    color: #5a7a8a;
}}
.cert-year {{
    color: #8a9aaa;
}}
</style>
</head>
<body>
"""


def _build_contact_html(cv):
    parts = []
    ciudad = cv.get("ciudad", "") or cv.get("location", "")
    if ciudad:
        parts.append(ciudad)
    phone = cv.get("telefono", "")
    if phone:
        parts.append(phone)
    email = cv.get("email", "")
    if email:
        parts.append(email)
    gh = cv.get("github", "")
    if gh:
        parts.append(gh)
    li = cv.get("linkedin", "")
    if li:
        parts.append(li)
    sep = '<span class="sep">|</span>'
    return f'<p class="contact">{(" " + sep + " ").join(parts)}</p>'


def _build_skills_html(cv):
    skills = cv.get("skills", {})
    if not skills:
        return ""
    rows = ""
    for cat, items in skills.items():
        if isinstance(items, list):
            items = ", ".join(str(i) for i in items)
        rows += f"<tr><td>{cat}</td><td>{items}</td></tr>"
    return f'<table class="skills-table">{rows}</table>'


def _build_projects_html(cv):
    proyectos = cv.get("projects", [])
    if not proyectos:
        return ""
    html = ""
    for proj in proyectos:
        title = proj.get("title", "")
        tag = proj.get("tag", "")
        subtitle = proj.get("subtitle", "")
        gh = proj.get("github", "")
        bullets = proj.get("bullets", [])
        impact = proj.get("impact", "")

        html += '<div class="project">'
        html += f'<p class="project-title">{title}</p>'
        if tag:
            html += f'<p class="project-tag">{tag}</p>'
        if subtitle:
            html += f'<p class="project-subtitle">{subtitle}</p>'
        if gh:
            html += f'<p class="project-gh">{gh}</p>'
        if bullets:
            html += "<ul>"
            for b in bullets:
                if b.strip():
                    html += f"<li>{b.strip()}</li>"
            html += "</ul>"
        if impact:
            html += f'<p class="project-impact"><strong>Impacto:</strong> {impact}</p>'
        html += "</div>"
    return html


def _build_education_html(cv):
    edu_list = cv.get("education", [])
    if not edu_list:
        return ""
    html = ""
    for edu in edu_list:
        if isinstance(edu, (list, tuple)):
            title = str(edu[0]) if len(edu) > 0 else ""
            sub = str(edu[1]) if len(edu) > 1 else ""
            year = str(edu[2]) if len(edu) > 2 else ""
            html += f'<div class="entry"><span class="entry-title">{title}</span>'
            if sub:
                html += f'<span class="entry-sub"> &mdash; {sub}</span>'
            if year:
                html += f'<span class="entry-year"> ({year})</span>'
            html += "</div>"
    return html


def _build_certifications_html(cv):
    certs = cv.get("certifications", [])
    if not certs:
        return ""
    html = '<ul class="certs">'
    for c in certs:
        if isinstance(c, (list, tuple)):
            name = str(c[0]) if len(c) > 0 else ""
            org = str(c[1]) if len(c) > 1 else ""
            year = str(c[2]) if len(c) > 2 else ""
            html += "<li>"
            html += name
            if org:
                html += f' <span class="cert-org">&mdash; {org}</span>'
            if year:
                html += f' <span class="cert-year">({year})</span>'
            html += "</li>"
    html += "</ul>"
    return html


def _build_soft_skills_html(cv):
    soft = cv.get("soft_skills", [])
    if not soft:
        return ""
    items = " &bull; ".join(soft)
    return f'<p class="soft-skills">&bull; {items}</p>'


def _build_core_competencies_html(cv):
    comps = cv.get("core_competencies", [])
    if not comps:
        return ""
    return f'<p class="competencies">{" | ".join(comps)}</p>'


def generar_html(cv):
    html = HEADER_HTML
    name = cv.get("nombre", "") or "Tu Nombre"
    title = cv.get("titulo", "")

    html += f'<p class="name">{name}</p>'
    if title:
        html += f'<p class="title">{title}</p>'
    html += _build_contact_html(cv)
    html += '<hr class="header-line">'

    resumen = cv.get("resumen", "").strip()
    if resumen:
        html += '<div class="section"><p class="section-title">Perfil Profesional</p>'
        html += f'<p class="profile-text">{resumen}</p></div>'

    comps = _build_core_competencies_html(cv)
    if comps:
        html += '<div class="section"><p class="section-title">Competencias Clave</p>'
        html += comps + "</div>"

    skills = _build_skills_html(cv)
    if skills:
        html += '<div class="section"><p class="section-title">Habilidades Técnicas</p>'
        html += skills + "</div>"

    proyectos = _build_projects_html(cv)
    if proyectos:
        html += '<div class="section"><p class="section-title">Proyectos Destacados</p>'
        html += proyectos + "</div>"

    edu = _build_education_html(cv)
    if edu:
        html += '<div class="section"><p class="section-title">Formación Académica</p>'
        html += edu + "</div>"

    certs = _build_certifications_html(cv)
    if certs:
        html += '<div class="section"><p class="section-title">Certificaciones</p>'
        html += certs + "</div>"

    soft = _build_soft_skills_html(cv)
    if soft:
        html += '<div class="section"><p class="section-title">Habilidades Blandas</p>'
        html += soft + "</div>"

    html += "</body></html>"
    return html


def generar_pdf(cv, ruta_pdf=None):
    if ruta_pdf is None:
        from config import RUTA_CV_DIR
        ruta_pdf = RUTA_CV_DIR / "CV_Diego_Galeano_Maestro.pdf"
    ruta_pdf = Path(ruta_pdf)
    ruta_pdf.parent.mkdir(parents=True, exist_ok=True)

    html_str = generar_html(cv)
    HTML(string=html_str).write_pdf(str(ruta_pdf))
    logger.info("PDF generated: %s", ruta_pdf)
    return ruta_pdf


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from generar_cv_maestro import PROFILE
    pdf = generar_pdf(PROFILE)
    print(f"PDF: {pdf}")
