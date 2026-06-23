# CV Automat — Asistente de CV Inteligente

Aplicación de escritorio (Tkinter) que integra **búsqueda inteligente de empleo**, **adaptación automática de CV con IA local (Ollama)**, **generación de PDF profesional** y **asistencia en postulación** vía Playwright o navegador real.

> Desarrollado por **Juan Diego Galeano Chica** — Ingeniero en Telecomunicaciones, Ciberseguridad & IA

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                       main.py (GUI Tkinter)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │  Mi CV   │ │ Buscar   │ │ Oferta   │ │ Aplicar  │        │
│  │ (edición)│ │ Ofertas  │ │ (cargada) │ │ (auto)   │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│  cv_manager  │ │  buscador  │ │ adaptador  │ │  aplicar   │
│  (persist)   │ │(jobdrop +  │ │(Ollama IA) │ │(Playwright │
│              │ │ career-ops │ │            │ │  + Brave)  │
│              │ │ + Colombia)│ │            │ │            │
└──────────────┘ └────────────┘ └────────────┘ └────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│  cv_base.json│ │  scorer    │ │generar_doc │ │  config    │
│  auto-cv-    │ │(híbrido:   │ │(Word +     │ │(paths,     │
│  agent       │ │ reglas+IA) │ │ WeasyPrint)│ │  modelos)  │
└──────────────┘ └────────────┘ └────────────┘ └────────────┘
```

---

## Funcionalidades

### 🧠 Edición de CV
- Formulario completo con pestañas: Datos Personales, Skills (por categorías), Proyectos, Educación, Certificaciones
- Persistencia en `cv_base.json` + exportación automática a `auto-cv-agent/config.py`
- Plantilla vacía incluida para empezar desde cero

### 🔍 Búsqueda Inteligente de Empleo
- **Jobdrop** (28 fuentes globales: LinkedIn, Indeed, Glassdoor, RemoteOK, etc.)
- **Career-Ops** (scanner de portales)
- **Scrapers Colombia** (LinkedIn CO, Computrabajo, Elempleo)
- **Filtros**: ubicación, nivel de experiencia (junior/semi-senior/senior/lead), inglés mínimo
- **Scoring híbrido**: skills (35%) + proyectos (25%) + competencias clave (20%) + educación/certs (10%) + soft skills (10%), ajustado por ubicación y experiencia
- ✅ Funciona para **cualquier tipo de trabajo** (no solo tech) — matching general por solapamiento de palabras

### 🤖 Adaptación con IA Local (Ollama)
- Usa **llama3.2** (fallback qwen2.5:0.5b) para adaptar resumen, skills y experiencia a la oferta
- Prompts diseñados para **no inventar información** — solo reordenar énfasis
- Sin dependencia de APIs externas ni envío de datos a la nube

### 📄 Generación de Documentos Profesionales
- **Word** (python-docx) con cabecera azul marino, secciones con chips, bullets, paleta profesional
- **PDF** (WeasyPrint) con HTML+CSS tipográfico, mismo estilo profesional
- Cada CV adaptado se guarda con el **nombre de la oferta**: `CV_Adaptado_senior_full_stack_empresa.docx`
- Carpeta de salida configurable (Archivo → Carpeta de salida...)

### 🚀 Postulación Asistida
- **Brave real**: abre el navegador con tus sesiones activas (sin bloqueos de Google/LinkedIn)
- **Playwright** (Firefox/Chromium): rellena formularios automáticamente con datos del CV
- Muestra nombre, email, teléfono y ruta del CV listos para copiar/pegar

---

## Instalación

### Requisitos
- Python 3.10+
- Ollama (con modelo `llama3.2`)
- LibreOffice (para conversión DOCX→PDF, opcional si usas WeasyPrint)
- Playwright browsers (para automatización con Firefox/Chromium)

### Rápida
```bash
git clone https://github.com/galeanojuan2577/CV_Automat.git
cd CV_Automat
chmod +x instalar.sh && ./instalar.sh
trabajo
```

### Manual
```bash
# Dependencias Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install playwright weasyprint
playwright install firefox chromium

# Modelo IA local
ollama pull llama3.2

# Iniciar
python3 main.py
```

### Configuración
Variables de entorno (opcional, ver `.env.example`):
| Variable | Por defecto |
|---|---|
| `CV_AUTOMAT_DIR` | `~/Documentos/Personal/CV_Automat` |
| `CV_OUTPUT_DIR` | `~/Documentos/CV` |
| `AUTO_CV_AGENT_DIR` | `~/auto-cv-agent` |
| `CAREER_OPS_DIR` | `~/career-ops` |
| `FILTERS_PY_PATH` | `auto-cv-gui/filters.py` |

---

## Stack Tecnológico

| Capa | Tecnología |
|---|---|
| GUI | Python Tkinter + ttk |
| IA Local | Ollama (llama3.2 / qwen2.5) |
| PDF | WeasyPrint (HTML+CSS) |
| Word | python-docx |
| Web Scraping | jobdrop, requests + BeautifulSoup, Playwright |
| Automatización | Playwright + zendriver (Brave) |
| Scrapers Colombia | requests + BeautifulSoup (LinkedIn CO, Computrabajo, Elempleo) |

---

## Estructura del Proyecto

```
CV_Automat/
├── main.py                  # GUI principal (Tkinter, 5 tabs)
├── config.py                # Rutas, modelos, pesos de scoring
├── cv_manager.py            # Persistencia del CV (JSON + auto-cv-agent)
├── adaptador.py             # Adaptación con Ollama (resumen, skills, experiencia)
├── scorer.py                # Motor de scoring híbrido (reglas + IA)
├── buscador.py              # Búsqueda y filtrado de ofertas
├── scrapers_colombia.py     # Scrapers Colombia (LinkedIn, Computrabajo, Elempleo)
├── aplicar.py               # Postulación automática (Playwright + Brave)
├── generar_documento.py     # Generación de Word
├── generar_pdf_html.py      # Generación de PDF con WeasyPrint
├── generar_cv_maestro.py    # CV gold master (plantilla)
├── credly_importer.py       # Importador de badges Credly
├── requirements.txt         # Dependencias Python
├── instalar.sh              # Instalación automatizada
├── trabajo.sh               # Script de inicio
├── cv_base.json.example     # Plantilla de CV vacía
├── .env.example             # Variables de entorno
└── .gitignore
```

---

## Licencia

MIT
