"""Capa de datos del dashboard.

Lee los archivos Parquet del directorio ``dataset`` y construye cubos
agregados que permiten responder los filtros del tablero sin recorrer las
tablas completas en cada petición.

Fuentes:
    - FAC.MBCORE_GUIAS.parquet
    - FAC.ATENCION_CLIENTE_ESTADO_TAREAS.parquet
    - DIM.PROCESO_TAREAS.parquet
    - Mapa de estados de tarea (0=CERRADA, 1=PENDIENTE), definido en este módulo.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

GUIAS_FILE = os.path.join(DATASET_DIR, "FAC.MBCORE_GUIAS.parquet")
TAREAS_FILE = os.path.join(DATASET_DIR, "FAC.ATENCION_CLIENTE_ESTADO_TAREAS.parquet")
PROCESOS_FILE = os.path.join(DATASET_DIR, "DIM.PROCESO_TAREAS.parquet")

# Cuarta tabla del modelo: catálogo de estados de tarea.
ESTADOS_TAREA = pd.DataFrame(
    {
        "ID_EST_TAREA": [0, 1],
        "ESTADO_TAREA": ["CERRADA", "PENDIENTE"],
    }
)

MONTHS = [
    "", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
]
MONTHS_SHORT = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

VEJEZ_BINS = ["0-30", "31-60", "61-90", ">91", "NO DISPONIBLE"]
PIEZAS_BINS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11+"]

_lock = threading.Lock()
_state: dict | None = None


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _norm_text(series: pd.Series, default="NO DISPONIBLE") -> pd.Series:
    out = series.astype("string").str.strip()
    return out.fillna(default).replace({"": default, "nan": default, "None": default})


def _norm_regimen(series: pd.Series) -> pd.Series:
    out = _norm_text(series)
    return out.replace(
        {
            "TRANSPORTE CARGA": "Transporte de carga",
            "Transporte De Carga": "Transporte de carga",
            "MENSAJERIA EXPRESA": "Mensajeria Expresa",
        }
    )


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _bin_vejez(value: float) -> str:
    if pd.isna(value):
        return "NO DISPONIBLE"
    if value <= 30:
        return "0-30"
    if value <= 60:
        return "31-60"
    if value <= 90:
        return "61-90"
    return ">91"


def _bin_piezas(value) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "NO DISPONIBLE"
    if n <= 0:
        return "NO DISPONIBLE"
    if n >= 11:
        return "11+"
    return str(n)


# ---------------------------------------------------------------------------
# Construcción de cubos
# ---------------------------------------------------------------------------
def _build_guias() -> pd.DataFrame:
    cols = [
        "GUIA", "FECHA_INICIO", "NUMERO_PIEZAS", "PRODUCTO", "CIUDAD_DESTINO",
        "CIUDAD_ULTI_MOVI", "DEPARTAMENTO_DESTINO", "DEPARTAMENTO_ORIGEN",
        "PROCESO_ULTI_MOVI", "NOMBRE_CLIENTE", "REGIONAL_UBICACION", "REGIMEN",
        "CANAL", "BODEGA_UBICACION", "CANT_CONFIRMACION",
        "DURACION_COMPENSACIONES", "DURACION_REZAGOS",
        "Numero_veces_compensaicones", "Numero_veces_rezagos",
        "Numero_piezas_rezagos", "Numero_piezas_compensacion",
        "VEJEZ_DESDE_INICIO", "VEJEZ A HOY", "SE_CANT_SZU",
        "TAR_NUM_TAREAS", "TAR_NUM_TAREAS_CERRADA", "TAR_NUM_TAREAS_PENDIENTE",
        "TAR_PROM_TIEMPO_RESPUESTA", "PESO_FISICO_R",
    ]
    g = pd.read_parquet(GUIAS_FILE, columns=cols)

    g["FECHA_INICIO"] = pd.to_datetime(g["FECHA_INICIO"], errors="coerce")
    g["y"] = g["FECHA_INICIO"].dt.year.fillna(0).astype(int)
    g["m"] = g["FECHA_INICIO"].dt.month.fillna(0).astype(int)
    g["r"] = _norm_text(g["REGIONAL_UBICACION"])
    g["rf"] = _norm_regimen(g["REGIMEN"])
    g["c"] = _norm_text(g["CANAL"])
    g["b"] = _norm_text(g["BODEGA_UBICACION"])
    g["REGIMEN_FINAL"] = g["rf"]

    g["guias"] = 1
    g["piezas"] = _num(g["NUMERO_PIEZAS"])
    g["peso"] = _num(g["PESO_FISICO_R"])
    g["szu"] = _num(g["SE_CANT_SZU"])
    g["pz_comp"] = _num(g["Numero_piezas_compensacion"])
    g["pz_rez"] = _num(g["Numero_piezas_rezagos"])
    g["veces_comp"] = _num(g["Numero_veces_compensaicones"])
    g["veces_rez"] = _num(g["Numero_veces_rezagos"])
    g["vejez_ini"] = _num(g["VEJEZ_DESDE_INICIO"])
    g["vejez_hoy"] = _num(g["VEJEZ A HOY"])

    g["conf"] = _num(g["CANT_CONFIRMACION"])
    g["sin_conf"] = (g["conf"] <= 0).astype(int)
    g["conf_corp"] = np.where(g["c"] == "CORPORATIVO", g["conf"], 0)
    g["conf_retail"] = np.where(g["c"] == "RETAIL", g["conf"], 0)
    g["conf_otros"] = np.where(g["c"] == "OTROS", g["conf"], 0)

    g["comp_apply"] = (g["pz_comp"] > 0).astype(int)
    g["comp_bodega"] = g["b"].str.upper().str.contains("COMPENSA", na=False).astype(int)
    g["rezago"] = (g["pz_rez"] > 0).astype(int)

    g["vejez_comp"] = _num(g["DURACION_COMPENSACIONES"])
    g["vejez_rez"] = _num(g["DURACION_REZAGOS"])
    g["c30g"] = (g["vejez_comp"] > 30).astype(int)
    g["c30v"] = np.where(g["vejez_comp"] > 30, g["vejez_comp"], 0.0)
    g["r0g"] = (g["vejez_rez"] > 0).astype(int)
    g["r30g"] = (g["vejez_rez"] > 30).astype(int)
    g["r30v"] = np.where(g["vejez_rez"] > 30, g["vejez_rez"], 0.0)

    g["tar_num"] = _num(g["TAR_NUM_TAREAS"])
    g["tar_pend"] = _num(g["TAR_NUM_TAREAS_PENDIENTE"])
    g["tar_cerr"] = _num(g["TAR_NUM_TAREAS_CERRADA"])
    g["tar_resp_sum"] = _num(g["TAR_PROM_TIEMPO_RESPUESTA"]) * _num(g["TAR_NUM_TAREAS_CERRADA"])
    g["tar_resp_cnt"] = _num(g["TAR_NUM_TAREAS_CERRADA"])

    g["n"] = g["NUMERO_PIEZAS"].map(_bin_piezas)
    g["t"] = g["vejez_comp"].map(_bin_vejez)

    return g


def _cube(g: pd.DataFrame, keys: list[str], metrics: dict[str, str]) -> pd.DataFrame:
    out = g.groupby(keys, dropna=False).agg(**metrics).reset_index()
    return out


def _source_signature() -> dict[str, float]:
    """Firma de los archivos fuente para invalidar la caché si cambian."""
    files = [GUIAS_FILE, TAREAS_FILE, PROCESOS_FILE]
    return {os.path.basename(p): os.path.getmtime(p) for p in files if os.path.exists(p)}


def build_all(force: bool = False) -> None:
    """Construye y persiste todos los cubos agregados."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    meta_path = os.path.join(CACHE_DIR, "meta.json")
    expected = ["guias.parquet", "base.parquet", "piezas.parquet", "vejez.parquet", "tareas.parquet", "procesos.parquet"]
    if not force and os.path.exists(meta_path) and all(os.path.exists(os.path.join(CACHE_DIR, f)) for f in expected):
        try:
            with open(meta_path, encoding="utf-8") as fh:
                cached_meta = json.load(fh)
        except (OSError, ValueError):
            cached_meta = {}
        if cached_meta.get("sources") == _source_signature():
            return

    print("[data] Construyendo cubos desde Parquet...")
    g = _build_guias()

    base_metrics = {
        "guias": ("guias", "sum"),
        "piezas": ("piezas", "sum"),
        "peso": ("peso", "sum"),
        "szu": ("szu", "sum"),
        "comp_apply": ("comp_apply", "sum"),
        "comp_bodega": ("comp_bodega", "sum"),
        "rezago": ("rezago", "sum"),
        "sin_conf": ("sin_conf", "sum"),
        "conf": ("conf", "sum"),
        "conf_corp": ("conf_corp", "sum"),
        "conf_retail": ("conf_retail", "sum"),
        "conf_otros": ("conf_otros", "sum"),
        "vejez_comp": ("vejez_comp", "sum"),
        "vejez_rez": ("vejez_rez", "sum"),
        "c30g": ("c30g", "sum"),
        "c30v": ("c30v", "sum"),
        "r0g": ("r0g", "sum"),
        "r30g": ("r30g", "sum"),
        "r30v": ("r30v", "sum"),
        "pz_comp": ("pz_comp", "sum"),
        "pz_rez": ("pz_rez", "sum"),
        "veces_comp": ("veces_comp", "sum"),
        "veces_rez": ("veces_rez", "sum"),
        "vejez_ini": ("vejez_ini", "sum"),
        "vejez_hoy": ("vejez_hoy", "sum"),
        "tar_num": ("tar_num", "sum"),
        "tar_pend": ("tar_pend", "sum"),
        "tar_cerr": ("tar_cerr", "sum"),
        "tar_resp_sum": ("tar_resp_sum", "sum"),
        "tar_resp_cnt": ("tar_resp_cnt", "sum"),
    }
    base = _cube(g, ["y", "m", "r", "rf", "c", "b"], base_metrics)
    base.to_parquet(os.path.join(CACHE_DIR, "base.parquet"), index=False)

    piezas = _cube(
        g,
        ["y", "m", "r", "rf", "c", "b", "n"],
        {"guias": ("guias", "sum"), "piezas": ("piezas", "sum"), "peso": ("peso", "sum")},
    )
    piezas.to_parquet(os.path.join(CACHE_DIR, "piezas.parquet"), index=False)

    vejez = _cube(
        g,
        ["y", "m", "r", "rf", "c", "b", "t"],
        {"vejez_comp": ("vejez_comp", "sum"), "guias": ("guias", "sum"), "piezas": ("piezas", "sum")},
    )
    vejez.to_parquet(os.path.join(CACHE_DIR, "vejez.parquet"), index=False)

    # Tabla de guías preparada para el reporte detallado.
    report_cols = [
        "GUIA", "FECHA_INICIO", "y", "m", "r", "rf", "c", "b", "PRODUCTO",
        "CIUDAD_DESTINO", "CIUDAD_ULTI_MOVI", "DEPARTAMENTO_DESTINO",
        "DEPARTAMENTO_ORIGEN", "PROCESO_ULTI_MOVI", "NOMBRE_CLIENTE",
        "pz_comp", "pz_rez", "veces_rez", "vejez_ini", "vejez_hoy", "piezas",
        "veces_comp",
    ]
    report = g[report_cols].copy()
    report.to_parquet(os.path.join(CACHE_DIR, "guias.parquet"), index=False)

    # --- Tareas (FAC) + catálogo de estados (cuarta tabla) ---
    t = pd.read_parquet(
        TAREAS_FILE,
        columns=[
            "AÑO", "MES", "NUMERO_GUIA", "NOMBRE_DIVISION", "ID_EST_TAREA",
            "TIEMPO_RESPUESTA", "NUM_TAREAS", "NUM_TAREAS_CON_RESPUESTA",
        ],
    )
    t = t.rename(columns={"AÑO": "y", "MES": "m", "NOMBRE_DIVISION": "d"})
    t["y"] = _num(t["y"]).astype(int)
    t["m"] = _num(t["m"]).astype(int)
    t["d"] = _norm_text(t["d"])
    t = t.merge(ESTADOS_TAREA, on="ID_EST_TAREA", how="left")
    t["ESTADO_TAREA"] = t["ESTADO_TAREA"].fillna("NO DISPONIBLE")

    dims = g[["GUIA", "r", "rf", "c", "b"]].drop_duplicates(subset=["GUIA"])
    t = t.merge(dims, left_on="NUMERO_GUIA", right_on="GUIA", how="left")
    for col in ["r", "rf", "c", "b"]:
        t[col] = t[col].fillna("NO DISPONIBLE")

    t["tar_num"] = _num(t["NUM_TAREAS"])
    t["tar_pend"] = np.where(t["ESTADO_TAREA"] == "PENDIENTE", t["tar_num"], 0.0)
    t["tar_cerr"] = np.where(t["ESTADO_TAREA"] == "CERRADA", t["tar_num"], 0.0)
    respuestas = _num(t["NUM_TAREAS_CON_RESPUESTA"])
    t["tar_resp_sum"] = np.where(respuestas > 0, _num(t["TIEMPO_RESPUESTA"]) / 3600.0 * respuestas, 0.0)
    t["tar_resp_cnt"] = np.where(respuestas > 0, respuestas, 0.0)

    tareas = _cube(
        t,
        ["y", "m", "r", "rf", "c", "b", "d"],
        {
            "tar_num": ("tar_num", "sum"),
            "tar_pend": ("tar_pend", "sum"),
            "tar_cerr": ("tar_cerr", "sum"),
            "tar_resp_sum": ("tar_resp_sum", "sum"),
            "tar_resp_cnt": ("tar_resp_cnt", "sum"),
        },
    )
    tareas.to_parquet(os.path.join(CACHE_DIR, "tareas.parquet"), index=False)

    # --- Dimensión de procesos ---
    d = pd.read_parquet(PROCESOS_FILE, columns=["NUMERO_GUIA", "NOMBRE_DIVISION"])
    d["NOMBRE_DIVISION"] = _norm_text(d["NOMBRE_DIVISION"])
    procesos = (
        d.groupby("NOMBRE_DIVISION", as_index=False)
        .agg(registros=("NUMERO_GUIA", "size"), guias=("NUMERO_GUIA", "nunique"))
        .sort_values("registros", ascending=False)
    )
    procesos.to_parquet(os.path.join(CACHE_DIR, "procesos.parquet"), index=False)

    meta = {
        "title": "SISTEMA DE VISUALIZACIÓN DE DATOS",
        "source": "DASHBOARD COMPENSACIONES Y REZAGOS NACIONAL.pbix",
        "lastUpdate": datetime.now().isoformat(timespec="seconds"),
        "dataMin": str(g["FECHA_INICIO"].min()),
        "dataMax": str(g["FECHA_INICIO"].max()),
        "totalGuias": int(len(g)),
        "totalPiezas": float(g["piezas"].sum()),
        "totalComp": float(g["comp_apply"].sum()),
        "totalRezago": float(g["rezago"].sum()),
        "totalTasks": float(t["tar_num"].sum()),
        "totalPending": float(t["tar_pend"].sum()),
        "totalConf": float(g["conf"].sum()),
        "sinConf": int(g["sin_conf"].sum()),
        "years": sorted(int(x) for x in g["y"].unique() if x > 0),
        "sources": _source_signature(),
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    print("[data] Cubos generados en", CACHE_DIR)


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
def load(force: bool = False) -> dict:
    global _state
    with _lock:
        if _state is not None and not force:
            return _state
        build_all(force=force)
        with open(os.path.join(CACHE_DIR, "meta.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
        _state = {
            "meta": meta,
            "base": pd.read_parquet(os.path.join(CACHE_DIR, "base.parquet")),
            "piezas": pd.read_parquet(os.path.join(CACHE_DIR, "piezas.parquet")),
            "vejez": pd.read_parquet(os.path.join(CACHE_DIR, "vejez.parquet")),
            "tareas": pd.read_parquet(os.path.join(CACHE_DIR, "tareas.parquet")),
            "procesos": pd.read_parquet(os.path.join(CACHE_DIR, "procesos.parquet")),
            "reporte": pd.read_parquet(os.path.join(CACHE_DIR, "guias.parquet")),
            "estados": ESTADOS_TAREA,
        }
        _state["options"] = _build_options(_state)
        return _state


def _build_options(state: dict) -> dict:
    report = state["reporte"]
    tareas = state["tareas"]
    base = state["base"]

    years = sorted({int(v) for v in report["y"].dropna().unique() if int(v) > 0} | {int(v) for v in tareas["y"].dropna().unique() if int(v) > 0})
    regionals = sorted(set(report["r"].dropna().unique()) | {"NO DISPONIBLE"})
    regimens = sorted(set(report["rf"].dropna().unique()))
    canals = sorted(set(report["c"].dropna().unique()))

    bod = (
        base.groupby("b", as_index=False)["guias"].sum()
        .sort_values("guias", ascending=False)
        .head(80)["b"]
        .tolist()
    )
    if "NO DISPONIBLE" not in bod:
        bod.append("NO DISPONIBLE")

    return {
        "years": years,
        "months": [{"v": i, "l": MONTHS[i]} for i in range(1, 13)],
        "regionals": regionals,
        "regimens": regimens,
        "canals": canals,
        "bodegas": sorted(bod),
    }


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
FILTER_KEYS = ("year", "month", "regional", "regimen", "canal", "bodega")


def normalize_filters(args) -> dict:
    def pick(name: str) -> str:
        value = (args.get(name) or "all").strip()
        return value if value else "all"

    return {key: pick(key) for key in FILTER_KEYS}


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    out = df
    if filters.get("year", "all") != "all":
        out = out[out["y"] == int(filters["year"])]
    if filters.get("month", "all") != "all":
        out = out[out["m"] == int(filters["month"])]
    if filters.get("regional", "all") != "all":
        out = out[out["r"] == filters["regional"]]
    if filters.get("regimen", "all") != "all":
        out = out[out["rf"] == filters["regimen"]]
    if filters.get("canal", "all") != "all":
        out = out[out["c"] == filters["canal"]]
    if filters.get("bodega", "all") != "all":
        out = out[out["b"] == filters["bodega"]]
    return out


def filter_summary(filters: dict) -> str:
    parts = []
    if filters.get("year", "all") != "all":
        parts.append("Año " + str(filters["year"]))
    if filters.get("month", "all") != "all":
        parts.append(MONTHS[int(filters["month"])])
    for key in ("regional", "regimen", "canal", "bodega"):
        if filters.get(key, "all") != "all":
            parts.append(filters[key])
    return " · ".join(parts) if parts else "Todos los registros"
