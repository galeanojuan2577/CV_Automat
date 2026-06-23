import logging
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "asistente_cv.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("main")

sys.path.insert(0, str(Path(__file__).parent))

import cv_manager
import adaptador
import generar_documento as gendoc
import buscador
import aplicar
import credly_importer
from config import RUTA_BASE, RUTA_CV_ADAPTADO_WORD, BROWSERS


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Asistente de CV Inteligente")
        self.geometry("1200x750")
        self.minsize(1000, 650)
        self._centrar_ventana()

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=28)
        style.configure("StatusBar.TLabel", relief=tk.SUNKEN, anchor=tk.W, padding=(4, 2))

        self.cv_data = cv_manager.cargar_cv()
        self.resultados_busqueda = []
        self.proceso_playwright = None
        self.hilo_busqueda = None
        self.hilo_adaptacion = None
        self.busqueda_cancelada = False
        self.ollama_ok, self.ollama_msg = adaptador.verificar_ollama()

        self.output_dir = self._cargar_output_dir()
        self._ruta_word_generado = None
        self._ruta_pdf_generado = None

        self._crear_menu()
        self._crear_widgets()
        self._poblar_cv()

        self.after(1000, self._verificar_ollama_inicio)
        self.after(1500, lambda: self._set_status(f"CVs se guardan en: {self.output_dir}"))

        self.protocol("WM_DELETE_WINDOW", self._on_cerrar)

    def _centrar_ventana(self):
        self.update_idletasks()
        ancho = 1200
        alto = 750
        x = (self.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.winfo_screenheight() // 2) - (alto // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")

    _SETTINGS_FILE = Path(__file__).parent / "settings.json"

    def _cargar_output_dir(self):
        import json
        if self._SETTINGS_FILE.exists():
            try:
                with open(self._SETTINGS_FILE) as f:
                    s = json.load(f)
                p = Path(s.get("output_dir", ""))
                if p:
                    return p
            except Exception:
                pass
        from config import RUTA_CV_DIR
        return RUTA_CV_DIR

    def _guardar_output_dir(self):
        import json
        try:
            with open(self._SETTINGS_FILE, "w") as f:
                json.dump({"output_dir": str(self.output_dir)}, f)
        except Exception as e:
            logger.warning("No se pudo guardar settings: %s", e)

    def _seleccionar_output_dir(self):
        ruta = filedialog.askdirectory(
            title="Carpeta para guardar los CVs",
            initialdir=str(self.output_dir),
        )
        if ruta:
            self.output_dir = Path(ruta)
            self._guardar_output_dir()
            self._set_status(f"Carpeta de salida: {self.output_dir}")

    def _crear_menu(self):
        menubar = tk.Menu(self)
        archivo = tk.Menu(menubar, tearoff=0)
        archivo.add_command(label="Cargar CV", command=self._cargar_cv_desde_json)
        archivo.add_command(label="Guardar CV", command=self._guardar_cv)
        archivo.add_separator()
        archivo.add_command(label="Exportar a auto-cv-agent", command=self._exportar_cv)
        archivo.add_separator()
        archivo.add_command(label="Carpeta de salida...", command=self._seleccionar_output_dir)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self._on_cerrar)
        menubar.add_cascade(label="Archivo", menu=archivo)

        ayuda = tk.Menu(menubar, tearoff=0)
        ayuda.add_command(label="Acerca de", command=self._acerca_de)
        menubar.add_cascade(label="Ayuda", menu=ayuda)

        self.config(menu=menubar)

    def _crear_widgets(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))

        self.tab_mi_cv = ttk.Frame(self.notebook)
        self.tab_buscar = ttk.Frame(self.notebook)
        self.tab_oferta = ttk.Frame(self.notebook)
        self.tab_vista = ttk.Frame(self.notebook)
        self.tab_aplicar = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_mi_cv, text="  Mi CV  ")
        self.notebook.add(self.tab_buscar, text="  Buscar Ofertas  ")
        self.notebook.add(self.tab_oferta, text="  Oferta  ")
        self.notebook.add(self.tab_vista, text="  Vista Previa  ")
        self.notebook.add(self.tab_aplicar, text="  Aplicar  ")

        self._crear_tab_mi_cv()
        self._crear_tab_buscar()
        self._crear_tab_oferta()
        self._crear_tab_vista_previa()
        self._crear_tab_aplicar()

        self.status_var = tk.StringVar(value="Listo")
        self.status_bar = ttk.Label(self, textvariable=self.status_var, style="StatusBar.TLabel")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ─── TAB: MI CV ─────────────────────────────────────────────

    def _crear_tab_mi_cv(self):
        self.cv_notebook = ttk.Notebook(self.tab_mi_cv)
        self.cv_notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._crear_subtab_datos()
        self._crear_subtab_skills()
        self._crear_subtab_proyectos()
        self._crear_subtab_educacion()
        self._crear_subtab_certificaciones()

        btn_frame = ttk.Frame(self.tab_mi_cv)
        btn_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Button(btn_frame, text="Cargar CV desde disco", command=self._cargar_cv_desde_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Guardar CV", command=self._guardar_cv).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Exportar a auto-cv-agent", command=self._exportar_cv).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Recargar desde auto-cv-agent", command=self._restaurar_cv).pack(side=tk.LEFT, padx=2)

    def _crear_subtab_datos(self):
        frame = ttk.Frame(self.cv_notebook)
        self.cv_notebook.add(frame, text="Datos Personales")

        pad = {"padx": 8, "pady": 3}
        row = 0

        campos = [
            ("nombre", "Nombre:"),
            ("email", "Email:"),
            ("telefono", "Teléfono:"),
            ("linkedin", "LinkedIn:"),
            ("github", "GitHub:"),
            ("ciudad", "Ciudad:"),
        ]
        self.cv_entries = {}
        for key, label in campos:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, **pad)
            var = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=var, width=60)
            entry.grid(row=row, column=1, sticky=tk.W, **pad)
            self.cv_entries[key] = var
            row += 1

        ttk.Label(frame, text="Resumen Profesional:").grid(row=row, column=0, sticky=tk.NW, **pad)
        self.cv_resumen = tk.Text(frame, height=5, width=60, wrap=tk.WORD)
        self.cv_resumen.grid(row=row, column=1, sticky=tk.W, **pad)
        row += 1

        ttk.Label(frame, text="Soft Skills (separadas por coma):").grid(row=row, column=0, sticky=tk.W, **pad)
        self.cv_soft = tk.Text(frame, height=3, width=60, wrap=tk.WORD)
        self.cv_soft.grid(row=row, column=1, sticky=tk.W, **pad)
        row += 1

        ttk.Label(frame, text="Core Competencies (separadas por coma):").grid(row=row, column=0, sticky=tk.W, **pad)
        self.cv_core = tk.Text(frame, height=3, width=60, wrap=tk.WORD)
        self.cv_core.grid(row=row, column=1, sticky=tk.W, **pad)
        row += 1

        ttk.Label(frame, text="Idiomas (separados por coma):").grid(row=row, column=0, sticky=tk.W, **pad)
        self.cv_idiomas = tk.Text(frame, height=2, width=60, wrap=tk.WORD)
        self.cv_idiomas.grid(row=row, column=1, sticky=tk.W, **pad)

    def _crear_subtab_skills(self):
        frame = ttk.Frame(self.cv_notebook)
        self.cv_notebook.add(frame, text="Skills")

        panes = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        left = ttk.Frame(panes)
        panes.add(left, weight=1)
        ttk.Label(left, text="Categorías:").pack(anchor=tk.W)
        self.skills_listbox = tk.Listbox(left, width=25)
        self.skills_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.skills_listbox.bind("<<ListboxSelect>>", self._on_skill_select)

        btn_frame_l = ttk.Frame(left)
        btn_frame_l.pack(fill=tk.X)
        ttk.Button(btn_frame_l, text="+ Categoría", command=self._agregar_categoria).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame_l, text="- Categoría", command=self._eliminar_categoria).pack(side=tk.LEFT, padx=2)

        right = ttk.Frame(panes)
        panes.add(right, weight=2)
        ttk.Label(right, text="Skills (separados por coma):").pack(anchor=tk.W)
        self.skills_text = tk.Text(right, height=10, width=40, wrap=tk.WORD)
        self.skills_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        ttk.Button(right, text="Guardar cambios en categoría", command=self._guardar_skill_categoria).pack(pady=4)

    def _on_skill_select(self, event):
        sel = self.skills_listbox.curselection()
        if not sel:
            return
        categoria = self.skills_listbox.get(sel[0])
        skills_str = self.cv_data.get("skills", {}).get(categoria, "")
        self.skills_text.delete("1.0", tk.END)
        self.skills_text.insert("1.0", skills_str)
        self._categoria_seleccionada = categoria

    def _agregar_categoria(self):
        nombre = simpledialog.askstring("Nueva categoría", "Nombre de la categoría:")
        if nombre and nombre not in self.cv_data.setdefault("skills", {}):
            self.cv_data["skills"][nombre] = ""
            self._refrescar_skills_listbox()
            self._set_status(f"Categoría '{nombre}' agregada")

    def _eliminar_categoria(self):
        sel = self.skills_listbox.curselection()
        if not sel:
            return
        nombre = self.skills_listbox.get(sel[0])
        if messagebox.askyesno("Confirmar", f"¿Eliminar categoría '{nombre}'?"):
            self.cv_data["skills"].pop(nombre, None)
            self._refrescar_skills_listbox()
            self.skills_text.delete("1.0", tk.END)
            self._set_status(f"Categoría '{nombre}' eliminada")

    def _guardar_skill_categoria(self):
        if not hasattr(self, "_categoria_seleccionada") or not self._categoria_seleccionada:
            messagebox.showinfo("Info", "Selecciona una categoría primero")
            return
        skills_text = self.skills_text.get("1.0", tk.END).strip()
        self.cv_data["skills"][self._categoria_seleccionada] = skills_text
        self._set_status(f"Skills de '{self._categoria_seleccionada}' actualizados")

    def _refrescar_skills_listbox(self):
        self.skills_listbox.delete(0, tk.END)
        for cat in self.cv_data.get("skills", {}):
            self.skills_listbox.insert(tk.END, cat)

    def _crear_subtab_proyectos(self):
        frame = ttk.Frame(self.cv_notebook)
        self.cv_notebook.add(frame, text="Proyectos")

        columns = ("title", "tag", "github")
        self.proy_tree = ttk.Treeview(frame, columns=columns, show="headings", height=8)
        self.proy_tree.heading("title", text="Título")
        self.proy_tree.heading("tag", text="Tag")
        self.proy_tree.heading("github", text="GitHub")
        self.proy_tree.column("title", width=200)
        self.proy_tree.column("tag", width=120)
        self.proy_tree.column("github", width=250)
        self.proy_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.proy_tree.bind("<Double-1>", self._editar_proyecto)

        btn_f = ttk.Frame(frame)
        btn_f.pack(fill=tk.X, padx=4, pady=2)
        ttk.Button(btn_f, text="+ Agregar", command=self._agregar_proyecto).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Editar", command=self._editar_proyecto_btn).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="- Eliminar", command=self._eliminar_proyecto).pack(side=tk.LEFT, padx=2)

    def _populate_proyectos(self):
        for item in self.proy_tree.get_children():
            self.proy_tree.delete(item)
        for p in self.cv_data.get("projects", []):
            self.proy_tree.insert("", tk.END, values=(
                p.get("title", ""), p.get("tag", ""), p.get("github", "")
            ))

    def _dialogo_proyecto(self, titulo, datos=None):
        dialog = tk.Toplevel(self)
        dialog.title(titulo)
        dialog.geometry("550x480")
        dialog.transient(self)
        dialog.grab_set()

        vars_dict = {}
        fields = [
            ("title", "Título:"),
            ("tag", "Tag:"),
            ("subtitle", "Subtítulo:"),
            ("github", "GitHub:"),
            ("impact", "Impacto:"),
        ]
        row = 0
        for key, label in fields:
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky=tk.W, padx=6, pady=2)
            var = tk.StringVar(value=(datos or {}).get(key, ""))
            entry = ttk.Entry(dialog, textvariable=var, width=50)
            entry.grid(row=row, column=1, sticky=tk.W, padx=6, pady=2)
            vars_dict[key] = var
            row += 1

        ttk.Label(dialog, text="Bullets (uno por línea):").grid(row=row, column=0, sticky=tk.NW, padx=6, pady=2)
        bullets_text = tk.Text(dialog, height=8, width=50, wrap=tk.WORD)
        bullets_text.grid(row=row, column=1, padx=6, pady=2)
        if datos:
            bullets_text.insert("1.0", "\n".join(datos.get("bullets", [])))
        row += 1

        resultado = {"aceptado": False, "datos": None}

        def aceptar():
            resultado["datos"] = {
                "title": vars_dict["title"].get(),
                "tag": vars_dict["tag"].get(),
                "subtitle": vars_dict["subtitle"].get(),
                "github": vars_dict["github"].get(),
                "impact": vars_dict["impact"].get(),
                "bullets": [b.strip() for b in bullets_text.get("1.0", tk.END).strip().split("\n") if b.strip()],
            }
            resultado["aceptado"] = True
            dialog.destroy()

        btn_f = ttk.Frame(dialog)
        btn_f.grid(row=row, column=0, columnspan=2, pady=8)
        ttk.Button(btn_f, text="Guardar", command=aceptar).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_f, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=4)

        self.wait_window(dialog)
        return resultado

    def _agregar_proyecto(self):
        res = self._dialogo_proyecto("Agregar Proyecto")
        if res["aceptado"]:
            self.cv_data.setdefault("projects", []).append(res["datos"])
            self._populate_proyectos()
            self._set_status("Proyecto agregado")

    def _editar_proyecto(self, event=None):
        sel = self.proy_tree.selection()
        if not sel:
            return
        idx = self.proy_tree.index(sel[0])
        proyectos = self.cv_data.get("projects", [])
        if idx < len(proyectos):
            res = self._dialogo_proyecto("Editar Proyecto", proyectos[idx])
            if res["aceptado"]:
                proyectos[idx] = res["datos"]
                self._populate_proyectos()
                self._set_status("Proyecto actualizado")

    def _editar_proyecto_btn(self):
        self._editar_proyecto()

    def _eliminar_proyecto(self):
        sel = self.proy_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar proyecto seleccionado?"):
            idx = self.proy_tree.index(sel[0])
            proyectos = self.cv_data.get("projects", [])
            if idx < len(proyectos):
                proyectos.pop(idx)
                self._populate_proyectos()
                self._set_status("Proyecto eliminado")

    def _crear_subtab_educacion(self):
        frame = ttk.Frame(self.cv_notebook)
        self.cv_notebook.add(frame, text="Educación")

        columns = ("titulo", "universidad", "año")
        self.edu_tree = ttk.Treeview(frame, columns=columns, show="headings", height=6)
        self.edu_tree.heading("titulo", text="Título")
        self.edu_tree.heading("universidad", text="Universidad")
        self.edu_tree.heading("año", text="Año")
        self.edu_tree.column("titulo", width=220)
        self.edu_tree.column("universidad", width=250)
        self.edu_tree.column("año", width=80)
        self.edu_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        btn_f = ttk.Frame(frame)
        btn_f.pack(fill=tk.X, padx=4, pady=2)
        ttk.Button(btn_f, text="+ Agregar", command=lambda: self._agregar_tupla("education", self._dialogo_tupla_edu)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Editar", command=lambda: self._editar_tupla("education", self._dialogo_tupla_edu)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="- Eliminar", command=lambda: self._eliminar_tupla("education")).pack(side=tk.LEFT, padx=2)

    def _dialogo_tupla_edu(self, titulo, datos=None):
        dialog = tk.Toplevel(self)
        dialog.title(titulo)
        dialog.geometry("400x180")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Título:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=4)
        v1 = tk.StringVar(value=(datos[0] if datos else ""))
        ttk.Entry(dialog, textvariable=v1, width=40).grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(dialog, text="Universidad:").grid(row=1, column=0, sticky=tk.W, padx=6, pady=4)
        v2 = tk.StringVar(value=(datos[1] if datos else ""))
        ttk.Entry(dialog, textvariable=v2, width=40).grid(row=1, column=1, padx=6, pady=4)

        ttk.Label(dialog, text="Año:").grid(row=2, column=0, sticky=tk.W, padx=6, pady=4)
        v3 = tk.StringVar(value=(datos[2] if datos else ""))
        ttk.Entry(dialog, textvariable=v3, width=15).grid(row=2, column=1, sticky=tk.W, padx=6, pady=4)

        res = {"aceptado": False, "datos": None}
        def aceptar():
            res["datos"] = [v1.get(), v2.get(), v3.get()]
            res["aceptado"] = True
            dialog.destroy()

        btn_f = ttk.Frame(dialog)
        btn_f.grid(row=3, column=0, columnspan=2, pady=8)
        ttk.Button(btn_f, text="Guardar", command=aceptar).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_f, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=4)

        self.wait_window(dialog)
        return res

    def _populate_education(self):
        for item in self.edu_tree.get_children():
            self.edu_tree.delete(item)
        for e in self.cv_data.get("education", []):
            vals = [str(v) for v in (e if isinstance(e, (list, tuple)) else [e, "", ""])]
            while len(vals) < 3:
                vals.append("")
            self.edu_tree.insert("", tk.END, values=vals[:3])

    def _crear_subtab_certificaciones(self):
        frame = ttk.Frame(self.cv_notebook)
        self.cv_notebook.add(frame, text="Certificaciones")

        columns = ("cert", "org", "año")
        self.cert_tree = ttk.Treeview(frame, columns=columns, show="headings", height=6)
        self.cert_tree.heading("cert", text="Certificación")
        self.cert_tree.heading("org", text="Organización")
        self.cert_tree.heading("año", text="Año")
        self.cert_tree.column("cert", width=280)
        self.cert_tree.column("org", width=200)
        self.cert_tree.column("año", width=80)
        self.cert_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        btn_f = ttk.Frame(frame)
        btn_f.pack(fill=tk.X, padx=4, pady=2)
        ttk.Button(btn_f, text="+ Agregar", command=lambda: self._agregar_tupla("certifications", self._dialogo_tupla_cert)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Editar", command=lambda: self._editar_tupla("certifications", self._dialogo_tupla_cert)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="- Eliminar", command=lambda: self._eliminar_tupla("certifications")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Importar desde Credly", command=self._importar_credly).pack(side=tk.RIGHT, padx=2)

    def _dialogo_tupla_cert(self, titulo, datos=None):
        dialog = tk.Toplevel(self)
        dialog.title(titulo)
        dialog.geometry("400x180")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Certificación:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=4)
        v1 = tk.StringVar(value=(datos[0] if datos else ""))
        ttk.Entry(dialog, textvariable=v1, width=40).grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(dialog, text="Organización:").grid(row=1, column=0, sticky=tk.W, padx=6, pady=4)
        v2 = tk.StringVar(value=(datos[1] if datos else ""))
        ttk.Entry(dialog, textvariable=v2, width=40).grid(row=1, column=1, padx=6, pady=4)

        ttk.Label(dialog, text="Año:").grid(row=2, column=0, sticky=tk.W, padx=6, pady=4)
        v3 = tk.StringVar(value=(datos[2] if datos else ""))
        ttk.Entry(dialog, textvariable=v3, width=15).grid(row=2, column=1, sticky=tk.W, padx=6, pady=4)

        res = {"aceptado": False, "datos": None}
        def aceptar():
            res["datos"] = [v1.get(), v2.get(), v3.get()]
            res["aceptado"] = True
            dialog.destroy()

        btn_f = ttk.Frame(dialog)
        btn_f.grid(row=3, column=0, columnspan=2, pady=8)
        ttk.Button(btn_f, text="Guardar", command=aceptar).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_f, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=4)

        self.wait_window(dialog)
        return res

    def _populate_certificaciones(self):
        for item in self.cert_tree.get_children():
            self.cert_tree.delete(item)
        for c in self.cv_data.get("certifications", []):
            vals = [str(v) for v in (c if isinstance(c, (list, tuple)) else [c, "", ""])]
            while len(vals) < 3:
                vals.append("")
            self.cert_tree.insert("", tk.END, values=vals[:3])

    def _agregar_tupla(self, key, dialog_fn):
        res = dialog_fn(f"Agregar {key}")
        if res["aceptado"]:
            self.cv_data.setdefault(key, []).append(res["datos"])
            self._populate_tupla(key)
            self._set_status(f"Agregado a {key}")

    def _editar_tupla(self, key, dialog_fn):
        tree = self.edu_tree if key == "education" else self.cert_tree
        sel = tree.selection()
        if not sel:
            return
        idx = tree.index(sel[0])
        items = self.cv_data.get(key, [])
        if idx < len(items):
            res = dialog_fn(f"Editar {key}", items[idx])
            if res["aceptado"]:
                items[idx] = res["datos"]
                self._populate_tupla(key)
                self._set_status(f"Actualizado en {key}")

    def _eliminar_tupla(self, key):
        tree = self.edu_tree if key == "education" else self.cert_tree
        sel = tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirmar", f"¿Eliminar este elemento de {key}?"):
            idx = tree.index(sel[0])
            items = self.cv_data.get(key, [])
            if idx < len(items):
                items.pop(idx)
                self._populate_tupla(key)
                self._set_status(f"Eliminado de {key}")

    def _populate_tupla(self, key):
        if key == "education":
            self._populate_education()
        elif key == "certifications":
            self._populate_certificaciones()

    def _poblar_cv(self):
        cv = self.cv_data
        for key in ("nombre", "email", "telefono", "linkedin", "github", "ciudad"):
            if key in self.cv_entries:
                self.cv_entries[key].set(cv.get(key, ""))

        if "resumen" in cv:
            self.cv_resumen.delete("1.0", tk.END)
            self.cv_resumen.insert("1.0", cv.get("resumen", ""))

        soft = ", ".join(cv.get("soft_skills", []))
        self.cv_soft.delete("1.0", tk.END)
        self.cv_soft.insert("1.0", soft)

        core = ", ".join(cv.get("core_competencies", []))
        self.cv_core.delete("1.0", tk.END)
        self.cv_core.insert("1.0", core)

        idiomas = ", ".join(cv.get("idiomas", []))
        self.cv_idiomas.delete("1.0", tk.END)
        self.cv_idiomas.insert("1.0", idiomas)

        self._refrescar_skills_listbox()
        self._populate_proyectos()
        self._populate_education()
        self._populate_certificaciones()

    def _leer_cv_desde_gui(self):
        cv = dict(self.cv_data)
        for key in ("nombre", "email", "telefono", "linkedin", "github", "ciudad"):
            cv[key] = self.cv_entries[key].get()
        cv["resumen"] = self.cv_resumen.get("1.0", tk.END).strip()

        raw_soft = self.cv_soft.get("1.0", tk.END).strip()
        cv["soft_skills"] = [s.strip() for s in raw_soft.split(",") if s.strip()]

        raw_core = self.cv_core.get("1.0", tk.END).strip()
        cv["core_competencies"] = [s.strip() for s in re.split(r',\s*(?![^()]*\))', raw_core) if s.strip()]

        raw_idiomas = self.cv_idiomas.get("1.0", tk.END).strip()
        cv["idiomas"] = [s.strip() for s in raw_idiomas.split(",") if s.strip()]

        return cv

    def _guardar_cv(self):
        self.cv_data = self._leer_cv_desde_gui()
        cv_manager.guardar_cv(self.cv_data)
        self._set_status("CV guardado exitosamente")

    def _cargar_cv_desde_json(self):
        ruta = filedialog.askopenfilename(
            title="Cargar CV desde JSON",
            filetypes=[("Archivos JSON", "*.json")],
            initialdir=str(RUTA_BASE),
        )
        if ruta:
            import json
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    self.cv_data = json.load(f)
                cv_manager._completar_template(self.cv_data)
                self._poblar_cv()
                self._set_status(f"CV cargado desde {Path(ruta).name}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el CV:\n{e}")

    def _exportar_cv(self):
        self.cv_data = self._leer_cv_desde_gui()
        try:
            cv_manager.exportar_a_auto_cv_agent(self.cv_data)
            self._set_status("CV exportado a auto-cv-agent/config.py")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar:\n{e}")

    def _restaurar_cv(self):
        if messagebox.askyesno("Confirmar", "¿Recargar CV desde auto-cv-agent/config.py?"):
            self.cv_data = cv_manager.cargar_cv()
            self._poblar_cv()
            self._set_status("CV recargado desde auto-cv-agent")

    def _importar_credly(self):
        try:
            badges = credly_importer.fetch_credly_badges()
        except Exception as e:
            messagebox.showerror("Error", f"Error al conectar con Credly:\n{e}")
            return
        if not badges:
            messagebox.showinfo("Credly", "No se encontraron certificaciones en Credly.")
            return
        count = 0
        for b in badges:
            name = b["name"]
            issuer = b["issuer"]
            year = b["date"][:4] if b["date"] else ""
            existing = [c for c in self.cv_data.get("certifications", []) if c[0] == name]
            if existing:
                continue
            self.cv_data.setdefault("certifications", []).append([name, issuer, year])
            count += 1
        if count:
            self._populate_certificaciones()
            self._set_status(f"{count} certificaciones importadas desde Credly")
        else:
            messagebox.showinfo("Credly", "Todas las certificaciones ya estaban en tu CV.")

    # ─── TAB: BUSCAR OFERTAS ──────────────────────────────────────

    def _crear_tab_buscar(self):
        top = ttk.Frame(self.tab_buscar)
        top.pack(fill=tk.X, padx=6, pady=6)

        ttk.Label(top, text="Término:").grid(row=0, column=0, padx=4, pady=2, sticky=tk.W)
        self.buscar_termino = tk.StringVar(value="")
        ttk.Entry(top, textvariable=self.buscar_termino, width=25).grid(row=0, column=1, padx=4, pady=2)

        ttk.Label(top, text="Ubicación:").grid(row=0, column=2, padx=4, pady=2, sticky=tk.W)
        self.buscar_ubicacion = tk.StringVar(value="")
        ttk.Entry(top, textvariable=self.buscar_ubicacion, width=18).grid(row=0, column=3, padx=4, pady=2)

        ttk.Label(top, text="Fuente:").grid(row=0, column=4, padx=4, pady=2, sticky=tk.W)
        self.buscar_fuente = tk.StringVar(value="todas")
        ttk.Combobox(top, textvariable=self.buscar_fuente,
                     values=["todas", "jobdrop", "career-ops", "colombia"],
                     state="readonly", width=12).grid(row=0, column=5, padx=4, pady=2)

        self.buscar_remoto = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Solo remoto", variable=self.buscar_remoto).grid(row=0, column=6, padx=4, pady=2)

        ttk.Label(top, text="Resultados:").grid(row=0, column=7, padx=4, pady=2, sticky=tk.W)
        self.buscar_cantidad = tk.StringVar(value="20")
        ttk.Entry(top, textvariable=self.buscar_cantidad, width=5).grid(row=0, column=8, padx=4, pady=2)

        ttk.Label(top, text="Horas:").grid(row=0, column=9, padx=4, pady=2, sticky=tk.W)
        self.buscar_horas = tk.StringVar(value="72")
        ttk.Entry(top, textvariable=self.buscar_horas, width=5).grid(row=0, column=10, padx=4, pady=2)

        self.buscar_btn = ttk.Button(top, text="Buscar", command=self._ejecutar_busqueda)
        self.buscar_btn.grid(row=0, column=11, padx=8, pady=2)

        sep = ttk.Separator(top, orient=tk.HORIZONTAL)
        sep.grid(row=1, column=0, columnspan=12, sticky=tk.EW, padx=2, pady=4)

        ttk.Label(top, text="Nivel:").grid(row=2, column=0, padx=4, pady=2, sticky=tk.W)
        self.filtro_experiencia = tk.StringVar(value="cualquiera")
        ttk.Combobox(top, textvariable=self.filtro_experiencia,
                     values=["cualquiera", "junior", "semi-senior", "senior", "lead"],
                     state="readonly", width=12).grid(row=2, column=1, padx=4, pady=2)

        ttk.Label(top, text="Inglés mínimo:").grid(row=2, column=2, padx=4, pady=2, sticky=tk.W)
        self.filtro_ingles = tk.StringVar(value="cualquiera")
        ttk.Combobox(top, textvariable=self.filtro_ingles,
                     values=["cualquiera", "B1", "B2", "C1", "Nativo"],
                     state="readonly", width=10).grid(row=2, column=3, padx=4, pady=2)

        panes = ttk.PanedWindow(self.tab_buscar, orient=tk.VERTICAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        top_frame = ttk.Frame(panes)
        panes.add(top_frame, weight=2)

        columns = ("score", "empresa", "titulo", "ubicacion", "fuente")
        self.res_tree = ttk.Treeview(top_frame, columns=columns, show="headings", height=10)
        self.res_tree.heading("score", text="Score")
        self.res_tree.heading("empresa", text="Empresa")
        self.res_tree.heading("titulo", text="Puesto")
        self.res_tree.heading("ubicacion", text="Ubicación")
        self.res_tree.heading("fuente", text="Fuente")
        self.res_tree.column("score", width=70, anchor=tk.CENTER)
        self.res_tree.column("empresa", width=160)
        self.res_tree.column("titulo", width=250)
        self.res_tree.column("ubicacion", width=130)
        self.res_tree.column("fuente", width=100)
        self.res_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scroll_tree = ttk.Scrollbar(top_frame, orient=tk.VERTICAL, command=self.res_tree.yview)
        self.res_tree.configure(yscrollcommand=scroll_tree.set)
        scroll_tree.pack(side=tk.RIGHT, fill=tk.Y)
        self.res_tree.bind("<<TreeviewSelect>>", self._on_resultado_select)
        self.res_tree.bind("<Double-1>", self._usar_oferta_seleccionada)

        bottom_frame = ttk.Frame(panes)
        panes.add(bottom_frame, weight=1)

        self.detalle_text = tk.Text(bottom_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.detalle_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        btn_f = ttk.Frame(bottom_frame)
        btn_f.pack(fill=tk.X, padx=4, pady=2)
        self.usar_oferta_btn = ttk.Button(btn_f, text="Usar esta oferta →", command=self._usar_oferta_seleccionada, state=tk.DISABLED)
        self.usar_oferta_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Abrir URL", command=self._abrir_url_seleccionada).pack(side=tk.LEFT, padx=2)

    def _ejecutar_busqueda(self):
        if self.hilo_busqueda and self.hilo_busqueda.is_alive():
            messagebox.showinfo("Info", "Ya hay una búsqueda en curso")
            return

        try:
            cant = int(self.buscar_cantidad.get())
            horas = int(self.buscar_horas.get())
        except ValueError:
            messagebox.showerror("Error", "Resultados y Horas deben ser números")
            return

        termino = self.buscar_termino.get().strip()
        ubicacion = self.buscar_ubicacion.get().strip()
        fuente = self.buscar_fuente.get()
        solo_remoto = self.buscar_remoto.get()
        filtro_exp = self.filtro_experiencia.get().strip()
        filtro_ingles = self.filtro_ingles.get().strip()
        if filtro_exp == "cualquiera":
            filtro_exp = ""

        self.buscar_btn.config(state=tk.DISABLED, text="Buscando...")
        self._set_status("Buscando ofertas...")
        for item in self.res_tree.get_children():
            self.res_tree.delete(item)
        self.detalle_text.config(state=tk.NORMAL)
        self.detalle_text.delete("1.0", tk.END)
        self.detalle_text.config(state=tk.DISABLED)

        def buscar_thread():
            cv = self._leer_cv_desde_gui()
            try:
                resultados = buscador.buscar_todo(
                    search_term=termino,
                    location=ubicacion,
                    fuente=fuente,
                    solo_remoto=solo_remoto,
                    hours_old=horas,
                    results_wanted=cant,
                    cv=cv,
                    ubicacion_filter="remoto" if solo_remoto else "",
                    ingles_min=filtro_ingles,
                    filtro_experiencia=filtro_exp,
                )
                self.after(0, lambda: self._mostrar_resultados(resultados))
            except Exception as e:
                logger.exception("Error en búsqueda")
                self.after(0, lambda: messagebox.showerror("Error", f"Error en búsqueda:\n{e}"))
                self.after(0, lambda: self._set_status("Error en búsqueda"))
                self.after(0, lambda: self.buscar_btn.config(state=tk.NORMAL, text="Buscar"))

        self.hilo_busqueda = threading.Thread(target=buscar_thread, daemon=True)
        self.hilo_busqueda.start()

    def _mostrar_resultados(self, resultados):
        self.resultados_busqueda = resultados
        self.res_tree.delete(*self.res_tree.get_children())
        for o in resultados:
            score = o.get("score", 0)
            tag = "score_alto" if score >= 70 else ("score_medio" if score >= 40 else "score_bajo")
            self.res_tree.insert("", tk.END, values=(
                f"{score:.0f}%",
                o.get("empresa", ""),
                o.get("titulo", ""),
                o.get("ubicacion", ""),
                o.get("fuente", ""),
            ), tags=(tag,))
        self.res_tree.tag_configure("score_alto", foreground="green")
        self.res_tree.tag_configure("score_medio", foreground="#CC8800")
        self.res_tree.tag_configure("score_bajo", foreground="red")

        self.buscar_btn.config(state=tk.NORMAL, text="Buscar")
        self._set_status(f"{len(resultados)} ofertas encontradas")

    def _on_resultado_select(self, event):
        sel = self.res_tree.selection()
        if not sel:
            self.usar_oferta_btn.config(state=tk.DISABLED)
            return
        idx = self.res_tree.index(sel[0])
        if idx >= len(self.resultados_busqueda):
            return
        o = self.resultados_busqueda[idx]
        detalle = o.get("detalle_score") or {}
        self.usar_oferta_btn.config(state=tk.NORMAL)

        texto = []
        texto.append(f"Empresa: {o.get('empresa', '')}  |  Puesto: {o.get('titulo', '')}")
        texto.append(f"Ubicación: {o.get('ubicacion', '')}  |  Fuente: {o.get('fuente', '')}")
        if detalle:
            texto.append("")
            texto.append(f"Score bruto: {detalle.get('score_bruto', 0)}")
            texto.append(f"Skills: {len(detalle.get('skills_match', []))} coincidencias")
            texto.append(f"Proyectos: {len(detalle.get('proyectos_match', []))} coincidencias")
            texto.append(f"Core Competencies: {len(detalle.get('core_match', []))} coincidencias")
            texto.append(f"Multiplicador ubic: {detalle.get('multiplicador_ubicacion', 1.0)} ({detalle.get('tipo_ubicacion', '')})")
            try:
                nivel = buscador._clasificar_nivel_experiencia(o)
                if nivel:
                    texto.append(f"Nivel: {nivel}")
            except Exception:
                pass
            texto.append(f"Experiencia: {detalle.get('razon_experiencia', 'sin ajuste')}")
            if detalle.get("razon_ia"):
                texto.append(f"IA: {detalle['razon_ia']}")
        if o.get("url"):
            texto.append(f"\nURL: {o['url']}")

        self.detalle_text.config(state=tk.NORMAL)
        self.detalle_text.delete("1.0", tk.END)
        self.detalle_text.insert("1.0", "\n".join(texto))
        self.detalle_text.config(state=tk.DISABLED)

    def _generar_resumen_oferta(self, o):
        d = o.get("detalle_score") or {}
        desc = o.get("descripcion", "") or ""
        texto = desc.lower()

        resumen = []
        resumen.append(f"{'═' * 55}")
        resumen.append(f"  {o.get('titulo', '')}")
        resumen.append(f"  {o.get('empresa', '')}")
        resumen.append(f"{'═' * 55}")
        resumen.append(f"  Score:  {o.get('score', 0):.0f}%")
        if d.get("razon_experiencia"):
            resumen.append(f"  Exp:    {d['razon_experiencia']}")

        tipo_ubic = d.get("tipo_ubicacion", "")
        etiq_ubic = {"remoto": "Remoto", "hibrido": "Híbrido", "presencial_bogota": "Bogotá", "presencial_otra": "Presencial"}
        resumen.append(f"  Modo:   {etiq_ubic.get(tipo_ubic, tipo_ubic)}")

        salario = ""
        for pat in [r'(?:\$|USD)\s*[\d.,]+\s*(?:mensual|mes|anual|año|hour|hora)',
                     r'(?:salario|salary)[:\s]*[^.\n]{3,60}']:
            m = re.search(pat, desc, re.I)
            if m:
                salario = re.sub(r'^(?:salario|salary)[:\s]*', '', m.group().strip(), flags=re.I).strip()
                break
        if salario:
            resumen.append(f"  Sueldo: {salario[:55]}")

        horario = ""
        for pat in [r'(?:horario|schedule|hours?)[:\s]*[^.\n]+', r'(?:lunes|monday)[^.\n]*?(?:viernes|friday)[^.\n]*',
                     r'(?:full.time|tiempo\s*completo|medio\s*tiempo|part.time)']:
            m = re.search(pat, desc, re.I)
            if m:
                horario = m.group().strip()
                break
        if horario:
            resumen.append(f"  Horario: {horario[:50]}")

        skills_match = d.get("skills_match", [])
        if skills_match:
            resumen.append(f"  Skills coinciden: {', '.join(skills_match[:8])}")

        skills_faltantes = []
        cv_skills = set()
        if hasattr(self, 'cv_data'):
            for cat, skills_str in self.cv_data.get("skills", {}).items():
                for s in skills_str.split(","):
                    s = s.strip()
                    if s:
                        cv_skills.add(s.lower())
        for s in skills_match:
            if s.lower() not in cv_skills:
                skills_faltantes.append(s)
        if skills_faltantes:
            resumen.append(f"  ⚠ Skills no en CV: {', '.join(skills_faltantes[:5])}")

        ubi = o.get("ubicacion", "")
        if ubi:
            resumen.append(f"  Ubic:   {ubi}")

        resumen.append(f"{'═' * 55}")
        return "\n".join(resumen)

    def _usar_oferta_seleccionada(self, event=None):
        sel = self.res_tree.selection()
        if not sel:
            return
        idx = self.res_tree.index(sel[0])
        if idx >= len(self.resultados_busqueda):
            return
        o = self.resultados_busqueda[idx]
        self.texto_oferta.delete("1.0", tk.END)
        desc = o.get("descripcion", "") or ""
        resumen = self._generar_resumen_oferta(o)
        encabezado = f"OFERTA: {o.get('titulo', '')} - {o.get('empresa', '')}\n"
        encabezado += f"Ubicación: {o.get('ubicacion', '')} | URL: {o.get('url', '')}\n\n"
        self.texto_oferta.insert("1.0", resumen + "\n\n" + encabezado + desc)
        self.notebook.select(self.tab_oferta)
        self._set_status(f"Oferta cargada: {o.get('titulo', '')}")

    def _abrir_url_seleccionada(self):
        sel = self.res_tree.selection()
        if not sel:
            return
        idx = self.res_tree.index(sel[0])
        if idx >= len(self.resultados_busqueda):
            return
        url = self.resultados_busqueda[idx].get("url", "")
        if url:
            import webbrowser
            webbrowser.open(url)

    # ─── TAB: OFERTA ────────────────────────────────────────────────

    def _crear_tab_oferta(self):
        btn_f = ttk.Frame(self.tab_oferta)
        btn_f.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(btn_f, text="Cargar archivo .txt", command=self._cargar_oferta_archivo).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Guardar oferta", command=self._guardar_oferta).pack(side=tk.LEFT, padx=2)

        self.texto_oferta = tk.Text(self.tab_oferta, height=15, wrap=tk.WORD, font=("Consolas", 10))
        self.texto_oferta.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        self.adaptar_btn = ttk.Button(self.tab_oferta, text="Adaptar CV con IA", command=self._ejecutar_adaptacion)
        self.adaptar_btn.pack(pady=(0, 8))

        if not self.ollama_ok:
            self.adaptar_btn.config(state=tk.DISABLED)
            self._set_status(f"Ollama no disponible: {self.ollama_msg}")

    def _cargar_oferta_archivo(self):
        ruta = filedialog.askopenfilename(
            title="Cargar oferta desde archivo",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")],
            initialdir=str(RUTA_BASE),
        )
        if ruta:
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    contenido = f.read()
                self.texto_oferta.delete("1.0", tk.END)
                self.texto_oferta.insert("1.0", contenido)
                self._set_status(f"Oferta cargada desde {Path(ruta).name}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo leer el archivo:\n{e}")

    def _guardar_oferta(self):
        contenido = self.texto_oferta.get("1.0", tk.END).strip()
        if not contenido:
            messagebox.showwarning("Aviso", "No hay contenido para guardar")
            return
        try:
            from config import RUTA_OFERTA
            with open(RUTA_OFERTA, "w", encoding="utf-8") as f:
                f.write(contenido)
            self._set_status("Oferta guardada")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def _ejecutar_adaptacion(self):
        texto_oferta = self.texto_oferta.get("1.0", tk.END).strip()
        if not texto_oferta:
            messagebox.showwarning("Aviso", "Pega o carga una oferta primero")
            return

        # Extract offer title from first line: "OFERTA: Title - Company\n..."
        primera_linea = texto_oferta.split("\n")[0]
        nombre_oferta = primera_linea.replace("OFERTA: ", "").strip()

        if not self.ollama_ok:
            retry = messagebox.askyesno("Ollama no disponible",
                                        f"{self.ollama_msg}\n\n¿Intentar de todas formas?")
            if not retry:
                return

        self.adaptar_btn.config(state=tk.DISABLED, text="Adaptando...")
        self._set_status("Adaptando CV con IA (esto puede tomar un minuto)...")

        progress = tk.Toplevel(self)
        progress.title("Adaptando CV")
        progress.geometry("400x120")
        progress.transient(self)
        progress.grab_set()
        ttk.Label(progress, text="Adaptando CV con IA...").pack(pady=(15, 5))
        pb = ttk.Progressbar(progress, mode="indeterminate", length=300)
        pb.pack(pady=5)
        pb.start(10)
        paso_label = ttk.Label(progress, text="Iniciando...")
        paso_label.pack(pady=5)

        def actualizar_paso(msg):
            self.after(0, lambda: paso_label.config(text=msg))

        def thread_adaptar():
            try:
                cv = self._leer_cv_desde_gui()
                cv_adaptado = adaptador.adaptar_cv_completo(cv, texto_oferta, on_step=actualizar_paso)
                slug = gendoc._slug_oferta(nombre_oferta) if nombre_oferta else ""
                sufijo = f"_{slug}" if slug else ""
                ruta_word = self.output_dir / f"CV_Adaptado{sufijo}.docx"
                ruta_pdf = self.output_dir / f"CV_Adaptado{sufijo}.pdf"
                ruta_word = gendoc.generar_word(cv_adaptado, ruta=ruta_word)
                ruta_pdf = gendoc.generar_pdf(cv_adaptado, ruta_pdf=ruta_pdf)
                self.after(0, lambda: self._mostrar_vista_previa(cv_adaptado, ruta_word, ruta_pdf))
                self.after(0, progress.destroy)
                self.after(0, lambda: self._set_status("CV adaptado exitosamente"))
                self.after(0, lambda: self.notebook.select(self.tab_vista))
            except Exception as e:
                logger.exception("Error en adaptación")
                self.after(0, progress.destroy)
                self.after(0, lambda: messagebox.showerror("Error", f"Error al adaptar CV:\n{e}"))
            finally:
                self.after(0, lambda: self.adaptar_btn.config(state=tk.NORMAL, text="Adaptar CV con IA"))

        self.hilo_adaptacion = threading.Thread(target=thread_adaptar, daemon=True)
        self.hilo_adaptacion.start()

    # ─── TAB: VISTA PREVIA ───────────────────────────────────────

    def _crear_tab_vista_previa(self):
        btn_f = ttk.Frame(self.tab_vista)
        btn_f.pack(fill=tk.X, padx=6, pady=6)
        self.abrir_word_btn = ttk.Button(btn_f, text="Abrir Word", command=self._abrir_word, state=tk.DISABLED)
        self.abrir_word_btn.pack(side=tk.LEFT, padx=2)
        self.generar_pdf_btn = ttk.Button(btn_f, text="Generar PDF", command=self._generar_pdf, state=tk.DISABLED)
        self.generar_pdf_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Copiar texto", command=self._copiar_texto).pack(side=tk.LEFT, padx=2)

        self.vista_text = tk.Text(self.tab_vista, wrap=tk.WORD, font=("Consolas", 10), state=tk.DISABLED)
        self.vista_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        self._ruta_word_generado = None
        self._ruta_pdf_generado = None

    def _mostrar_vista_previa(self, cv_adaptado, ruta_word, ruta_pdf=None):
        self._ruta_word_generado = ruta_word
        self._ruta_pdf_generado = ruta_pdf
        self.abrir_word_btn.config(state=tk.NORMAL)
        self.generar_pdf_btn.config(state=tk.NORMAL if ruta_pdf else tk.DISABLED)

        lineas = []
        lineas.append(cv_adaptado.get("nombre", "").upper())
        lineas.append(f"{cv_adaptado.get('email', '')} | {cv_adaptado.get('telefono', '')}")
        lineas.append(cv_adaptado.get("linkedin", ""))
        lineas.append("─" * 60)
        lineas.append("")

        resumen = cv_adaptado.get("resumen", "").strip()
        if resumen:
            lineas.append("RESUMEN PROFESIONAL")
            lineas.append(resumen)
            lineas.append("")

        core = cv_adaptado.get("core_competencies", [])
        if core:
            lineas.append("COMPETENCIAS CLAVE")
            for c in core:
                lineas.append(f"  ▸ {c}")
            lineas.append("")

        skills = cv_adaptado.get("skills", {})
        if skills:
            lineas.append("HABILIDADES TÉCNICAS")
            for cat, skills_str in skills.items():
                lineas.append(f"  {cat}: {skills_str}")
            lineas.append("")

        exp = cv_adaptado.get("experiencia", [])
        if exp:
            lineas.append("EXPERIENCIA PROFESIONAL")
            for e in exp:
                lineas.append(f"  {e.get('puesto', '')} — {e.get('empresa', '')}")
                desc = e.get("descripcion", "")
                if desc:
                    for d_line in desc.split("\n"):
                        lineas.append(f"    • {d_line.strip()}")
            lineas.append("")

        proyectos = cv_adaptado.get("projects", [])
        if proyectos:
            lineas.append("PROYECTOS DESTACADOS")
            for p in proyectos:
                lineas.append(f"  {p.get('title', '')}  [{p.get('tag', '')}]")
                gh = p.get("github", "")
                if gh:
                    lineas.append(f"    {gh}")
                subtitle = p.get("subtitle", "")
                if subtitle:
                    lineas.append(f"    {subtitle}")
                for b in p.get("bullets", []):
                    lineas.append(f"    • {b}")
            lineas.append("")

        education = cv_adaptado.get("education", [])
        if education:
            lineas.append("FORMACIÓN ACADÉMICA")
            for e in education:
                if isinstance(e, (list, tuple)):
                    title = str(e[0]) if len(e) > 0 else ""
                    sub = str(e[1]) if len(e) > 1 else ""
                    yr = str(e[2]) if len(e) > 2 else ""
                    lineas.append(f"  {title}  —  {sub}  ({yr})")
            lineas.append("")

        certs = cv_adaptado.get("certifications", [])
        if certs:
            lineas.append("CERTIFICACIONES")
            for c in certs:
                if isinstance(c, (list, tuple)):
                    name = str(c[0]) if len(c) > 0 else ""
                    org = str(c[1]) if len(c) > 1 else ""
                    yr = str(c[2]) if len(c) > 2 else ""
                    lineas.append(f"  ▸ {name}  —  {org}  ({yr})")
            lineas.append("")

        soft = cv_adaptado.get("soft_skills", [])
        if soft:
            lineas.append("HABILIDADES BLANDAS")
            lineas.append(f"  {', '.join(soft)}")
            lineas.append("")

        idiomas = cv_adaptado.get("idiomas", [])
        if idiomas:
            lineas.append("IDIOMAS")
            lineas.append(f"  {', '.join(idiomas)}")

        self.vista_text.config(state=tk.NORMAL)
        self.vista_text.delete("1.0", tk.END)
        self.vista_text.insert("1.0", "\n".join(lineas))
        self.vista_text.config(state=tk.DISABLED)

    def _abrir_word(self):
        if self._ruta_word_generado and self._ruta_word_generado.exists():
            import subprocess
            subprocess.Popen(["xdg-open", str(self._ruta_word_generado)])
        else:
            messagebox.showwarning("Aviso", "No hay un Word generado aún")

    def _generar_pdf(self):
        if self._ruta_pdf_generado and self._ruta_pdf_generado.exists():
            subprocess.Popen(["xdg-open", str(self._ruta_pdf_generado)])
            self._set_status("PDF abierto")
            return
        cv = self._leer_cv_desde_gui()
        self._set_status("Generando PDF profesional...")
        def thread_pdf():
            try:
                ruta_pdf = gendoc.generar_pdf(cv)
                if ruta_pdf:
                    self._ruta_pdf_generado = ruta_pdf
                    self.after(0, lambda: self._set_status("PDF generado"))
                    self.after(0, lambda: subprocess.Popen(["xdg-open", str(ruta_pdf)]))
                else:
                    self.after(0, lambda: messagebox.showerror("Error", "No se pudo generar el PDF"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.after(0, lambda: self._set_status("Error al generar PDF"))
        threading.Thread(target=thread_pdf, daemon=True).start()

    def _copiar_texto(self):
        texto = self.vista_text.get("1.0", tk.END)
        if texto.strip():
            self.clipboard_clear()
            self.clipboard_append(texto)
            self._set_status("Texto copiado al portapapeles")

    # ─── TAB: APLICAR ────────────────────────────────────────────

    def _crear_tab_aplicar(self):
        ttk.Label(self.tab_aplicar, text="URL de la oferta:").pack(anchor=tk.W, padx=6, pady=(10, 2))
        self.aplicar_url = tk.StringVar(value="")
        ttk.Entry(self.tab_aplicar, textvariable=self.aplicar_url, width=90).pack(fill=tk.X, padx=6, pady=2)

        browser_frame = ttk.Frame(self.tab_aplicar)
        browser_frame.pack(fill=tk.X, padx=6, pady=2)
        ttk.Label(browser_frame, text="Navegador:").pack(side=tk.LEFT, padx=(0, 4))
        self.aplicar_browser = tk.StringVar(value="Firefox (bundled)")
        ttk.Combobox(browser_frame, textvariable=self.aplicar_browser,
                     values=list(BROWSERS.keys()),
                     state="readonly", width=22).pack(side=tk.LEFT)

        self.aplicar_status = tk.StringVar(value="")
        ttk.Label(self.tab_aplicar, textvariable=self.aplicar_status, foreground="blue").pack(anchor=tk.W, padx=6, pady=4)

        btn_f = ttk.Frame(self.tab_aplicar)
        btn_f.pack(fill=tk.X, padx=6, pady=4)
        self.asistir_btn = ttk.Button(btn_f, text="Asistir Aplicación", command=self._asistir_aplicacion)
        self.asistir_btn.pack(side=tk.LEFT, padx=2)
        self.continuar_btn = ttk.Button(btn_f, text="Continuar", command=self._continuar_aplicacion, state=tk.DISABLED)
        self.continuar_btn.pack(side=tk.LEFT, padx=2)
        self.finalizar_btn = ttk.Button(btn_f, text="Finalizar", command=self._finalizar_aplicacion, state=tk.DISABLED)
        self.finalizar_btn.pack(side=tk.LEFT, padx=2)

        self.aplicar_log = tk.Text(self.tab_aplicar, height=15, wrap=tk.WORD, state=tk.DISABLED)
        self.aplicar_log.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    def _log_aplicar(self, msg):
        self.aplicar_log.config(state=tk.NORMAL)
        self.aplicar_log.insert(tk.END, f"  {msg}\n")
        self.aplicar_log.see(tk.END)
        self.aplicar_log.config(state=tk.DISABLED)

    def _asistir_aplicacion(self):
        url = self.aplicar_url.get().strip()
        if not url:
            messagebox.showwarning("Aviso", "Ingresa la URL de la oferta")
            return

        cv_path = getattr(self, '_ruta_word_generado', None) or RUTA_CV_ADAPTADO_WORD
        cv = self._leer_cv_desde_gui()
        browser_name = self.aplicar_browser.get()

        self.asistir_btn.config(state=tk.DISABLED)
        self.continuar_btn.config(state=tk.DISABLED)
        self.finalizar_btn.config(state=tk.NORMAL)
        self.aplicar_log.config(state=tk.NORMAL)
        self.aplicar_log.delete("1.0", tk.END)
        self.aplicar_log.config(state=tk.DISABLED)

        browser_note = ""
        if browser_name == "Brave":
            browser_note = (
                "\n  🟢 BRAVE — Usando tu navegador real.\n"
                "  Tus sesiones de LinkedIn, Google, etc. están activas.\n"
                "  Para copiar tus datos rápidamente:\n"
            )
            if cv.get("nombre"):
                browser_note += f"    Nombre:    {cv['nombre']}\n"
            if cv.get("email"):
                browser_note += f"    Email:     {cv['email']}\n"
            if cv.get("telefono"):
                browser_note += f"    Teléfono:  {cv['telefono']}\n"
            if cv_path.exists():
                browser_note += f"    CV:        {cv_path}\n"
            browser_note += "\n  Presiona 'Finalizar' cuando termines.\n"

        self._set_status(f"Abriendo con {browser_name}...")
        self.aplicar_status.set(f"Abriendo {browser_name}...")

        def thread_aplicar():
            msg_buffer = []
            if browser_note:
                msg_buffer.append(browser_note)

            def step(msg):
                msg_buffer.append(msg)
                self.after(0, lambda: self._log_aplicar(msg))
                self.after(0, lambda: self.aplicar_status.set(msg[:60]))

            if browser_note:
                self.after(0, lambda: self._log_aplicar(browser_note))

            exito = aplicar.asistir_aplicacion(url, cv, str(cv_path) if cv_path.exists() else None,
                                               on_step=step, browser_name=browser_name)
            self.after(0, lambda: self._aplicacion_terminada(exito))

        threading.Thread(target=thread_aplicar, daemon=True).start()

    def _continuar_aplicacion(self):
        self._log_aplicar("⏩ Continuando...")

    def _finalizar_aplicacion(self):
        self._aplicacion_terminada(True)

    def _aplicacion_terminada(self, exito):
        self.asistir_btn.config(state=tk.NORMAL)
        self.continuar_btn.config(state=tk.DISABLED)
        self.finalizar_btn.config(state=tk.DISABLED)
        if exito:
            self._set_status("Aplicación finalizada")
            self.aplicar_status.set("Finalizado")
        else:
            self._set_status("Aplicación cancelada o con errores")
            self.aplicar_status.set("Cancelado")

    # ─── HELPERS ─────────────────────────────────────────────────

    def _verificar_ollama_inicio(self):
        ok, msg = adaptador.verificar_ollama()
        self.ollama_ok = ok
        self.ollama_msg = msg
        if not ok:
            self._set_status(f"⚠ {msg}")
            if not getattr(self, "_aviso_ollama_mostrado", False):
                self._aviso_ollama_mostrado = True
                self.after(500, lambda: messagebox.showwarning(
                    "Ollama no disponible",
                    f"{msg}\n\nPuedes editar tu CV y buscar ofertas, "
                    "pero la adaptación con IA no funcionará hasta que Ollama esté activo."
                ))
        else:
            self._set_status("Listo — Ollama disponible")

    def _set_status(self, msg):
        self.status_var.set(msg)
        logger.info("Status: %s", msg)

    def _acerca_de(self):
        messagebox.showinfo(
            "Acerca de",
            "Asistente de CV Inteligente v1.0\n\n"
            "Centro de mando para personalizar tu CV con IA local (Ollama)\n"
            "y asistir en la postulación a ofertas de empleo.\n\n"
            "Todos los datos permanecen en tu equipo."
        )

    def _on_cerrar(self):
        if messagebox.askokcancel("Salir", "¿Cerrar la aplicación?"):
            self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
