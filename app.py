"""Sistema de Visualización de Datos · Aplicación Flask."""

from __future__ import annotations

import io
import os
from datetime import date, datetime, timedelta
from functools import wraps

import pandas as pd
from flask import (
    Flask, Response, abort, flash, g, jsonify, redirect, render_template,
    request, session, url_for,
)
from werkzeug.security import check_password_hash

import analytics
import data_service as ds
import database as db

app = Flask(__name__)
app.json.ensure_ascii = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion-2026")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

if not os.environ.get("SECRET_KEY"):
    print("[seguridad] Define SECRET_KEY en el entorno antes de desplegar en producción.")

db.init_db()


@app.after_request
def set_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


# ---------------------------------------------------------------------------
# Sesión y permisos
# ---------------------------------------------------------------------------
@app.before_request
def load_current_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        user = db.get_user(user_id)
        if user and user["is_active"]:
            g.user = user
        else:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        if g.user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def _safe_next(target: str | None) -> str:
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("areas")


def _user_area_ids():
    return {a["id"] for a in db.list_areas_for_user(g.user["id"], g.user["role"])}


def _current_context():
    area_id = session.get("area_id")
    dashboard_slug = session.get("dashboard_slug")
    if not area_id or not dashboard_slug:
        return None, None
    if area_id not in _user_area_ids():
        session.pop("area_id", None)
        session.pop("dashboard_slug", None)
        return None, None
    area = db.get_area(area_id)
    dashboard = db.get_dashboard(area_id, dashboard_slug)
    if not area or not dashboard:
        session.pop("area_id", None)
        session.pop("dashboard_slug", None)
        return None, None
    return area, dashboard


# ---------------------------------------------------------------------------
# Navegación
# ---------------------------------------------------------------------------
NAV = [
    {
        "section": "Tablero",
        "links": [
            {"id": "principal", "label": "Principal", "icon": "home"},
            {"id": "confirmaciones", "label": "Confirmaciones", "icon": "check"},
            {"id": "vejez-comp", "label": "Vejez compensaciones", "icon": "clock"},
            {"id": "vejez-rez", "label": "Vejez rezagos", "icon": "layers"},
        ],
    },
    {
        "section": "Tareas",
        "links": [
            {"id": "tareas-estados", "label": "Tareas · estados", "icon": "tasks"},
            {"id": "tareas-comparativo", "label": "Tareas · comparativo", "icon": "chart"},
            {"id": "procesos", "label": "Procesos · dimensión", "icon": "sitemap"},
        ],
    },
    {
        "section": "Datos",
        "links": [
            {"id": "reporte", "label": "Reporte detallado", "icon": "table"},
        ],
    },
    {
        "section": "Próximos módulos",
        "links": [
            {"id": "clientes", "label": "Clientes", "icon": "users", "badge": "Pronto", "future": True},
            {"id": "geografia", "label": "Geografía", "icon": "map", "badge": "Pronto", "future": True},
            {"id": "alertas", "label": "Alertas y reglas", "icon": "bell", "badge": "Pronto", "future": True},
            {"id": "exportaciones", "label": "Exportaciones", "icon": "download", "badge": "Pronto", "future": True},
            {"id": "configuracion", "label": "Configuración", "icon": "settings", "badge": "Pronto", "future": True},
        ],
    },
]

PAGE_BUILDERS = {
    "principal": analytics.principal,
    "confirmaciones": analytics.confirmaciones,
    "vejez-comp": analytics.vejez_comp,
    "vejez-rez": analytics.vejez_rez,
    "tareas-estados": analytics.tareas_estados,
    "tareas-comparativo": analytics.tareas_comparativo,
    "procesos": analytics.procesos,
}

FUTURE_MODULES = {
    "clientes": {
        "title": "Clientes",
        "icon": "users",
        "description": "Análisis de compensaciones, rezagos y nivel de servicio por cliente.",
        "planned": [
            "Ranking de clientes por guías, piezas y valor declarado.",
            "Tasa de compensación y rezago por cliente.",
            "Comparativo mensual y participación sobre el total nacional.",
            "Ficha individual del cliente con su detalle operativo.",
        ],
    },
    "geografia": {
        "title": "Geografía",
        "icon": "map",
        "description": "Comportamiento de la operación por regional, ciudad y bodega.",
        "planned": [
            "Mapa nacional con volumen y vejez por regional.",
            "Top ciudades origen y destino.",
            "Matriz de flujos entre regiones.",
            "Alertas por concentración de rezagos.",
        ],
    },
    "alertas": {
        "title": "Alertas y reglas",
        "icon": "bell",
        "description": "Definición de umbrales y notificaciones automáticas del tablero.",
        "planned": [
            "Reglas por días de vejez, guías sin confirmación y tareas pendientes.",
            "Suscripción de responsables por regional.",
            "Historial de alertas disparadas.",
            "Integración con correo o mensajería corporativa.",
        ],
    },
    "exportaciones": {
        "title": "Exportaciones",
        "icon": "download",
        "description": "Generación programada de archivos y envío de reportes.",
        "planned": [
            "Exportación de cada vista a Excel y PDF.",
            "Programación de envíos diarios o semanales.",
            "Plantillas de reporte configurables.",
            "Registro de exportaciones generadas.",
        ],
    },
    "configuracion": {
        "title": "Configuración",
        "icon": "settings",
        "description": "Administración de fuentes, usuarios y parámetros del dashboard.",
        "planned": [
            "Gestión de fuentes Parquet y periodos de actualización.",
            "Usuarios, roles y permisos por módulo.",
            "Parámetros de negocio: días críticos, metas y semáforos.",
            "Bitácora de cambios y auditoría.",
        ],
    },
}


# ---------------------------------------------------------------------------
# Jinja
# ---------------------------------------------------------------------------
@app.template_filter("n")
def jinja_num(value, decimals=0):
    return analytics.fnum(value, decimals)


@app.template_filter("pct")
def jinja_pct(value, decimals=1):
    return analytics.fpct(value, decimals)


@app.template_filter("fecha")
def jinja_fecha(value):
    if value is None or value == "":
        return "—"
    try:
        if isinstance(value, (datetime, date, pd.Timestamp)):
            dt = pd.Timestamp(value)
        else:
            dt = pd.to_datetime(value)
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return str(value)


@app.context_processor
def inject_globals():
    state = ds.load()
    user = g.get("user")
    initials = ""
    if user:
        base = (user["full_name"] or user["username"]).strip()
        parts = [p for p in base.split() if p]
        initials = "".join(p[0].upper() for p in parts[:2]) or user["username"][:2].upper()
    return {
        "NAV": NAV,
        "META": state["meta"],
        "MODULES": FUTURE_MODULES,
        "APP_NAME": "Sistema de Visualización de Datos",
        "CURRENT_USER": user,
        "USER_INITIALS": initials,
        "AREAS_URL": url_for("areas") if user else None,
        "CURRENT_AREA": session.get("area_name"),
        "CURRENT_AREA_ID": session.get("area_id"),
        "CURRENT_DASHBOARD": session.get("dashboard_name"),
    }


# ---------------------------------------------------------------------------
# Reporte detallado
# ---------------------------------------------------------------------------
REPORT_COLS = [
    ("GUIA", "Guía", "num", 0),
    ("FECHA_INICIO", "Fecha envío", "date", 0),
    ("r", "Regional", "", 0),
    ("b", "Bodega", "", 0),
    ("c", "Canal", "", 0),
    ("rf", "Régimen", "", 0),
    ("PRODUCTO", "Producto", "", 0),
    ("CIUDAD_DESTINO", "Ciudad destino", "", 0),
    ("CIUDAD_ULTI_MOVI", "Ciudad último mov.", "", 0),
    ("DEPARTAMENTO_DESTINO", "Depto. destino", "", 0),
    ("DEPARTAMENTO_ORIGEN", "Depto. origen", "", 0),
    ("PROCESO_ULTI_MOVI", "Proceso último mov.", "", 0),
    ("pz_comp", "Pzas. comp.", "num", 0),
    ("pz_rez", "Pzas. rezago", "num", 0),
    ("veces_rez", "Veces rezago", "num", 0),
    ("vejez_ini", "Vejez inicio", "num", 1),
    ("vejez_hoy", "Vejez hoy", "num", 1),
    ("piezas", "Núm. piezas", "num", 0),
    ("veces_comp", "Veces comp.", "num", 0),
    ("NOMBRE_CLIENTE", "Nombre cliente", "", 0),
]

REPORT_KEYS = {c[0] for c in REPORT_COLS}


def _report_frame(state, filters, query: str):
    df = ds.apply_filters(state["reporte"], filters)
    q = (query or "").strip().lower()
    if q:
        cliente = df["NOMBRE_CLIENTE"].astype("string").str.lower().str.contains(q, na=False, regex=False)
        guia = df["GUIA"].astype("string").str.contains(q, na=False, regex=False)
        df = df[cliente | guia]
    return df


def _report_context(state, filters):
    query = request.args.get("q", "")
    sort = request.args.get("sort", "FECHA_INICIO")
    if sort not in REPORT_KEYS:
        sort = "FECHA_INICIO"
    direction = request.args.get("dir", "desc")
    if direction not in {"asc", "desc"}:
        direction = "desc"
    try:
        size = int(request.args.get("size", 25))
    except ValueError:
        size = 25
    if size not in {25, 50, 100}:
        size = 25
    try:
        page_num = int(request.args.get("page_num", 1))
    except ValueError:
        page_num = 1

    rows = _report_frame(state, filters, query)
    rows = rows.sort_values(sort, ascending=(direction == "asc"), kind="mergesort")
    total = len(rows)
    total_pages = max(1, (total + size - 1) // size)
    page_num = min(max(1, page_num), total_pages)
    start = (page_num - 1) * size
    page_rows = rows.iloc[start:start + size]

    table_rows = []
    for _, r in page_rows.iterrows():
        cells = []
        for key, label, kind, dec in REPORT_COLS:
            value = r[key]
            if key == "FECHA_INICIO":
                cells.append(analytics.esc(jinja_fecha(value)))
            elif kind == "num":
                cells.append(analytics.fnum(value, dec))
            else:
                cells.append(analytics.esc(value))
        table_rows.append(cells)

    headers = []
    for key, label, kind, dec in REPORT_COLS:
        active = key == sort
        arrow = ""
        if active:
            arrow = " ▲" if direction == "asc" else " ▼"
        headers.append({"key": key, "label": label + arrow, "kind": kind})

    def report_url(page_target: int, **overrides):
        params = {
            "year": filters["year"],
            "month": filters["month"],
            "regional": filters["regional"],
            "regimen": filters["regimen"],
            "canal": filters["canal"],
            "bodega": filters["bodega"],
            "q": query,
            "sort": sort,
            "dir": direction,
            "size": size,
            "page_num": page_target,
        }
        params.update(overrides)
        return url_for("dashboard_page", page="reporte", **params)

    pages = []
    first = max(1, page_num - 2)
    last = min(total_pages, page_num + 2)
    if first > 1:
        pages.append({"label": "1", "num": 1, "url": report_url(1), "active": False, "ellipsis": False})
        if first > 2:
            pages.append({"label": "…", "num": None, "url": None, "active": False, "ellipsis": True})
    for p in range(first, last + 1):
        pages.append({"label": str(p), "num": p, "url": report_url(p), "active": p == page_num, "ellipsis": False})
    if last < total_pages:
        if last < total_pages - 1:
            pages.append({"label": "…", "num": None, "url": None, "active": False, "ellipsis": True})
        pages.append({"label": str(total_pages), "num": total_pages, "url": report_url(total_pages), "active": False, "ellipsis": False})

    sort_urls = {}
    for key in REPORT_KEYS:
        new_dir = "asc"
        if key == sort:
            new_dir = "desc" if direction == "asc" else "asc"
        sort_urls[key] = report_url(1, sort=key, dir=new_dir)

    csv_params = {
        "year": filters["year"],
        "month": filters["month"],
        "regional": filters["regional"],
        "regimen": filters["regimen"],
        "canal": filters["canal"],
        "bodega": filters["bodega"],
        "q": query,
        "sort": sort,
        "dir": direction,
    }

    return {
        "page": "reporte",
        "title": "REPORTE COMPENSACIONES Y REZAGOS",
        "subtitle": "Detalle de guías del modelo con búsqueda, orden y descarga CSV",
        "chip": ds.filter_summary(filters),
        "kpis": [
            {"label": "Registros en selección", "value": analytics.fnum(total), "sub": f"de {analytics.fnum(state['meta']['totalGuias'])} guías en el tablero", "tone": "accent"},
            {"label": "Piezas", "value": analytics.fnum(rows["piezas"].sum()), "sub": "En la selección actual"},
            {"label": "Piezas compensación", "value": analytics.fnum(rows["pz_comp"].sum()), "sub": "Acumulado de la selección", "tone": "yellow"},
            {"label": "Piezas rezago", "value": analytics.fnum(rows["pz_rez"].sum()), "sub": "Acumulado de la selección", "tone": "blue"},
        ],
        "headers": headers,
        "rows": table_rows,
        "query": query,
        "size": size,
        "page_num": page_num,
        "total_pages": total_pages,
        "total": total,
        "pages": pages,
        "sort": sort,
        "dir": direction,
        "sort_urls": sort_urls,
        "prev_url": report_url(max(1, page_num - 1)),
        "next_url": report_url(min(total_pages, page_num + 1)),
        "csv_url": url_for("export_report", **csv_params),
        "report_url": report_url,
        "notes": "La tabla se calcula en el servidor sobre FAC.MBCORE_GUIAS. El CSV descarga la selección filtrada completa.",
        "charts": {},
        "charts_json": {},
    }


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if g.user is None:
        return redirect(url_for("login"))
    return redirect(url_for("areas"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("areas"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = db.get_user_by_username(username)
        if user and user["is_active"] and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            return redirect(_safe_next(request.form.get("next") or request.args.get("next")))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "ok")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Selección de área y dashboards
# ---------------------------------------------------------------------------
@app.route("/areas")
@login_required
def areas():
    cards = []
    for area in db.list_areas_for_user(g.user["id"], g.user["role"]):
        row = dict(area)
        row["total_dashboards"] = db.count_dashboards(area["id"])
        cards.append(row)
    return render_template("areas.html", areas=cards, page="areas", header=None, title="Selección de área")


@app.route("/areas/<int:area_id>")
@login_required
def area_dashboards(area_id):
    if area_id not in _user_area_ids():
        abort(403)
    area = db.get_area(area_id)
    if not area:
        abort(404)
    dashboards = [dict(d) for d in db.list_dashboards(area_id)]
    return render_template(
        "dashboards.html",
        area=dict(area),
        dashboards=dashboards,
        page="areas",
        header=None,
        title=area["name"],
    )


@app.route("/areas/<int:area_id>/dashboards/<slug>/open")
@login_required
def open_dashboard(area_id, slug):
    if area_id not in _user_area_ids():
        abort(403)
    area = db.get_area(area_id)
    dashboard = db.get_dashboard(area_id, slug)
    if not area or not dashboard:
        abort(404)
    if not dashboard["is_ready"]:
        flash("Este dashboard estará disponible próximamente.", "info")
        return redirect(url_for("area_dashboards", area_id=area_id))
    session["area_id"] = area_id
    session["area_name"] = area["name"]
    session["area_slug"] = area["slug"]
    session["dashboard_slug"] = dashboard["slug"]
    session["dashboard_name"] = dashboard["name"]
    return redirect(url_for("dashboard_page", page="principal"))


# ---------------------------------------------------------------------------
# Panel administrador (contraseñas y usuarios)
# ---------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin_home():
    return render_template(
        "admin.html",
        users=[dict(u) for u in db.list_users()],
        areas=[dict(a) for a in db.list_areas()],
        page="admin",
        header=None,
        title="Administración de contraseñas",
    )


@app.route("/admin/users", methods=["POST"])
@admin_required
def admin_create_user():
    username = request.form.get("username", "").strip().lower()
    full_name = request.form.get("full_name", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "user")
    if role not in {"user", "admin"}:
        role = "user"
    if not username or len(username) < 3:
        flash("El usuario debe tener al menos 3 caracteres.", "error")
    elif not password or len(password) < 6:
        flash("La contraseña debe tener al menos 6 caracteres.", "error")
    elif db.get_user_by_username(username):
        flash("El usuario ya existe.", "error")
    else:
        try:
            db.create_user(username, password, full_name or username.title(), role)
            flash(f"Usuario {username} creado correctamente.", "ok")
        except Exception:
            flash("No fue posible crear el usuario.", "error")
    return redirect(url_for("admin_home"))


@app.route("/admin/users/<int:user_id>/password", methods=["POST"])
@admin_required
def admin_change_password(user_id):
    user = db.get_user(user_id)
    password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")
    if not user:
        abort(404)
    if len(password) < 6:
        flash("La contraseña debe tener al menos 6 caracteres.", "error")
    elif password != confirm:
        flash("Las contraseñas no coinciden.", "error")
    else:
        db.update_password(user_id, password)
        flash(f"Contraseña actualizada para {user['username']}.", "ok")
    return redirect(url_for("admin_home"))


@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def admin_toggle_user(user_id):
    user = db.get_user(user_id)
    if not user:
        abort(404)
    if user_id == g.user["id"]:
        flash("No puedes desactivar tu propio usuario.", "error")
        return redirect(url_for("admin_home"))
    db.toggle_user(user_id)
    flash(f"Estado de {user['username']} actualizado.", "ok")
    return redirect(url_for("admin_home"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route("/dashboard/<page>")
@login_required
def dashboard_page(page):
    area, dashboard = _current_context()
    if area is None:
        flash("Selecciona un área y un dashboard para continuar.", "info")
        return redirect(url_for("areas"))

    state = ds.load()
    filters = ds.normalize_filters(request.args)
    base_context = {
        "area": dict(area),
        "dashboard_info": dict(dashboard),
    }

    if page in FUTURE_MODULES:
        module = FUTURE_MODULES[page]
        return render_template(
            "placeholder.html",
            page=page,
            module=module,
            title=module["title"],
            subtitle=module["description"],
            filters=filters,
            options=state["options"],
            header=analytics.header_stats(state, filters),
            **base_context,
        )

    if page == "reporte":
        context = _report_context(state, filters)
    elif page in PAGE_BUILDERS:
        context = PAGE_BUILDERS[page](state, filters)
    else:
        return redirect(url_for("dashboard_page", page="principal"))

    context["filters"] = filters
    context["options"] = state["options"]
    context["header"] = analytics.header_stats(state, filters)
    context["charts_json"] = context.get("charts", {})
    context["page_template"] = f"pages/{page}.html"
    context.update(base_context)
    return render_template("base.html", **context)


@app.route("/reporte/export.csv")
@login_required
def export_report():
    state = ds.load()
    filters = ds.normalize_filters(request.args)
    query = request.args.get("q", "")
    sort = request.args.get("sort", "FECHA_INICIO")
    if sort not in REPORT_KEYS:
        sort = "FECHA_INICIO"
    direction = request.args.get("dir", "desc")
    if direction not in {"asc", "desc"}:
        direction = "desc"

    rows = _report_frame(state, filters, query)
    rows = rows.sort_values(sort, ascending=(direction == "asc"), kind="mergesort")

    out = io.StringIO()
    headers = [c[1] for c in REPORT_COLS]
    out.write(";".join(headers) + "\r\n")
    for _, r in rows.iterrows():
        cells = []
        for key, label, kind, dec in REPORT_COLS:
            value = r[key]
            if key == "FECHA_INICIO":
                value = jinja_fecha(value)
            elif kind == "num":
                value = analytics.fnum(value, dec)
            if value is None:
                value = ""
            cells.append('"' + str(value).replace('"', '""') + '"')
        out.write(";".join(cells) + "\r\n")

    payload = "\ufeff" + out.getvalue()
    filename = "reporte_compensaciones_rezagos.csv"
    return Response(
        payload,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/api/health")
def health():
    state = ds.load()
    return jsonify(
        {
            "status": "ok",
            "guias": state["meta"]["totalGuias"],
            "tareas": state["meta"]["totalTasks"],
            "data_max": state["meta"]["dataMax"],
            "pages": list(PAGE_BUILDERS) + ["reporte"],
        }
    )


if __name__ == "__main__":
    ds.load()
    app.run(host="0.0.0.0", port=5000, debug=False)
