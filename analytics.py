"""Modelos de vista para cada página del dashboard."""

from __future__ import annotations

import html
import math

import pandas as pd

import data_service as ds

COLORS = ["#2563eb", "#f59e0b", "#0ea5e9", "#dc2626", "#7c3aed", "#ea580c", "#0891b2", "#e044a7", "#06b6d4", "#94a3b8"]
BIN_COLORS = {"0-30": "#2563eb", "31-60": "#f59e0b", "61-90": "#ea580c", ">91": "#dc2626", "NO DISPONIBLE": "#94a3b8"}
REGIMEN_COLORS = {"Mensajeria Expresa": "#2563eb", "Transporte de carga": "#0ea5e9", "NO DISPONIBLE": "#94a3b8"}
DIV_COLORS = {
    "LOGISTICA": "#2563eb",
    "COMPENSACIONES BOGOTA": "#0ea5e9",
    "COMPENSACIONES": "#f59e0b",
    "OTROS PROCESOS": "#94a3b8",
    "CROSS DOCKING CONFIRMACIONES": "#7c3aed",
    "ATENCION CLIENTE": "#ea580c",
    "CONFIRMACIONES MERC. PREMIER": "#0891b2",
    "ADMINISTRACION DE INFORMACION": "#e044a7",
    "SERVIENTREGA URBANO": "#06b6d4",
    "RECOLECCION DISTRIBUCION": "#dc2626",
}


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------
def fnum(value, decimals: int = 0) -> str:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(x):
        return "—"
    out = f"{x:,.{decimals}f}"
    return out.replace(",", "\u00a0").replace(".", ",").replace("\u00a0", ".")


def fpct(value, decimals: int = 1) -> str:
    return f"{fnum(value, decimals)}%"


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _s(df: pd.DataFrame, col: str) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())


def _pct(a, b) -> float:
    return (float(a) * 100.0 / float(b)) if b else 0.0


def _group(df: pd.DataFrame, keys, metrics: dict) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=list(keys) + list(metrics))
    return df.groupby(keys, dropna=False).agg(**{k: (v, "sum") for k, v in metrics.items()}).reset_index()


def _rows(df: pd.DataFrame, columns) -> list[list]:
    return df[columns].values.tolist() if not df.empty else []


def _kpi(label, value, sub="", tone="") -> dict:
    return {"label": label, "value": value, "sub": sub, "tone": tone}


def _insight(icon, text) -> dict:
    return {"icon": icon, "text": text}


def _summary(filters) -> str:
    return ds.filter_summary(filters)


def _month_label(y, m, specific_year) -> str:
    m = int(m)
    if specific_year:
        return ds.MONTHS_SHORT[m]
    return f"{ds.MONTHS_SHORT[m]} {str(int(y))[-2:]}"


def _piezas_datasets(pie_rows: pd.DataFrame, specific_year=False):
    cats = ds.PIEZAS_BINS
    regs = sorted(pie_rows["rf"].dropna().unique().tolist()) if not pie_rows.empty else []
    totals = {cat: float(pie_rows.loc[pie_rows["n"] == cat, "guias"].sum()) for cat in cats}
    datasets = []
    for idx, reg in enumerate(regs):
        counts = []
        data = []
        sub = pie_rows[pie_rows["rf"] == reg]
        for cat in cats:
            count = float(sub.loc[sub["n"] == cat, "guias"].sum())
            counts.append(count)
            data.append((count * 100.0 / totals[cat]) if totals[cat] else 0.0)
        datasets.append(
            {
                "label": reg,
                "data": data,
                "counts": counts,
                "color": REGIMEN_COLORS.get(reg, COLORS[idx % len(COLORS)]),
            }
        )
    return {
        "labels": cats,
        "datasets": datasets,
        "totals": [totals[c] for c in cats],
        "totalOnePiece": totals.get("1", 0.0),
    }


# ---------------------------------------------------------------------------
# Estado general / cabecera
# ---------------------------------------------------------------------------
def header_stats(state, filters) -> dict:
    base = ds.apply_filters(state["base"], filters)
    tareas = ds.apply_filters(state["tareas"], filters)
    return {
        "guias": fnum(_s(base, "guias")),
        "piezas": fnum(_s(base, "piezas")),
        "comp": fnum(_s(base, "comp_apply")),
        "rez": fnum(_s(base, "rezago")),
        "pendientes": fnum(_s(tareas, "tar_pend")),
    }


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------
def principal(state, filters) -> dict:
    rows = ds.apply_filters(state["base"], filters)
    g = _s(rows, "guias")
    pz = _s(rows, "piezas")
    comp = _s(rows, "comp_apply")
    rez = _s(rows, "rezago")
    peso = _s(rows, "peso")

    bodegas = _group(rows, ["b"], {"guias": "guias", "piezas": "piezas", "szu": "szu"})
    bodegas = bodegas.sort_values("guias", ascending=False).head(12)
    max_bodega = max([1.0] + bodegas["guias"].tolist()) if not bodegas.empty else 1.0
    bodega_rows = []
    for _, r in bodegas.iterrows():
        bodega_rows.append(
            [
                f'<span class="rank-dot"></span>{esc(r["b"])}<div class="mini-bar"><i style="width:{_pct(r["guias"], max_bodega):.1f}%"></i></div>',
                fnum(r["piezas"]),
                fnum(r["guias"]),
                fnum(r["szu"]),
            ]
        )

    comp_rows = rows[rows["b"].str.upper().str.contains("COMPENSA", na=False)]
    regional_comp = _group(comp_rows, ["r"], {"comp_bodega": "comp_bodega"}).sort_values("comp_bodega", ascending=False)
    max_region = max([1.0] + regional_comp["comp_bodega"].tolist()) if not regional_comp.empty else 1.0
    regional_rows = [
        [esc(r["r"]), fnum(r["comp_bodega"]), f'<div class="mini-bar"><i style="width:{_pct(r["comp_bodega"], max_region):.1f}%"></i></div>']
        for _, r in regional_comp.iterrows()
    ]

    pie_rows = ds.apply_filters(state["piezas"], filters)
    pie_data = _piezas_datasets(pie_rows)

    by_regional = _group(rows, ["r"], {"guias": "guias"}).sort_values("guias", ascending=False)
    top_regional = by_regional.iloc[0]["r"] if not by_regional.empty else "—"
    top_regional_pct = _pct(by_regional.iloc[0]["guias"], g) if not by_regional.empty else 0.0
    pct_one = _pct(pie_data["totalOnePiece"], g)
    pct_comp = _pct(comp, g)

    return {
        "page": "principal",
        "title": "PRINCIPAL",
        "subtitle": "Visión general de compensaciones, rezagos y salidas de zona urbana",
        "chip": _summary(filters),
        "kpis": [
            _kpi("Guías totales", fnum(g), f"{fnum(pz)} piezas", "accent"),
            _kpi("En compensación", fnum(comp), f"{fpct(pct_comp)} del total"),
            _kpi("En rezago", fnum(rez), f"{fpct(_pct(rez, g))} del total", "yellow"),
            _kpi("Peso físico", fnum(peso / 1000, 1) + " t", "Peso envíos registrados", "blue"),
        ],
        "tables": {
            "bodegas": {"headers": ["BODEGA", "PIEZAS", "GUÍAS", "SALIDA ZONA URBANA"], "rows": bodega_rows, "aligns": ["", "num", "num", "num"], "cls": "tall"},
            "regionales": {"headers": ["REGIONAL", "ENVÍOS", "PESO RELATIVO"], "rows": regional_rows, "aligns": ["", "num", ""], "cls": "short"},
        },
        "insights": [
            _insight("1", f"<b>{esc(top_regional)}</b> concentra <b>{fpct(top_regional_pct)}</b> de las guías registradas en el tablero."),
            _insight("2", f"El <b>{fpct(pct_one)}</b> de las guías se mueve con una sola pieza. La operación está dominada por envíos unitarios."),
            _insight("3", f"<b>{fnum(comp)}</b> guías pasaron por compensaciones y <b>{fnum(rez)}</b> por rezagos; juntas representan <b>{fpct(_pct(comp + rez, g))}</b> del total."),
            _insight("4", f"Se registran <b>{fnum(peso / 1000, 1)} toneladas</b> de peso físico y <b>{fnum(pz)} piezas</b> en el periodo consultado."),
        ],
        "charts": {"piezas": pie_data},
    }


# ---------------------------------------------------------------------------
# Confirmaciones
# ---------------------------------------------------------------------------
def confirmaciones(state, filters) -> dict:
    rows = ds.apply_filters(state["base"], filters)
    g = _s(rows, "guias")
    sin = _s(rows, "sin_conf")
    conf = _s(rows, "conf")
    pct_sin = _pct(sin, g)

    combo = _group(rows, ["c", "rf"], {"sin_conf": "sin_conf", "guias": "guias", "conf": "conf"})
    if not combo.empty:
        combo = combo.sort_values(["c", "rf"])
    table_rows = [
        [esc(r["c"]), esc(r["rf"]), fnum(r["sin_conf"]), fnum(r["guias"]), fpct(_pct(r["sin_conf"], r["guias"]))]
        for _, r in combo.iterrows()
    ]

    regs = sorted(rows["rf"].dropna().unique().tolist()) if not rows.empty else []
    by_reg = _group(rows, ["rf"], {"conf_corp": "conf_corp", "conf_retail": "conf_retail", "conf_otros": "conf_otros"})
    reg_map = {r["rf"]: r for _, r in by_reg.iterrows()} if not by_reg.empty else {}
    series = [("conf_corp", "CORPORATIVO", "#2563eb"), ("conf_retail", "RETAIL", "#0ea5e9"), ("conf_otros", "OTROS", "#f59e0b")]
    datasets = []
    for key, label, color in series:
        datasets.append(
            {
                "label": label,
                "color": color,
                "data": [float(reg_map[reg][key]) if reg in reg_map else 0.0 for reg in regs],
            }
        )
    totals = [(label, _s(rows, key), color) for key, label, color in series]
    top_conf = sorted(totals, key=lambda x: x[1], reverse=True)[0]

    return {
        "page": "confirmaciones",
        "title": "CONFIRMACIONES",
        "subtitle": "Seguimiento de confirmaciones por régimen y canal de distribución",
        "chip": _summary(filters),
        "kpis": [
            _kpi("Guías totales", fnum(g), "Base del periodo", "accent"),
            _kpi("Confirmaciones", fnum(conf), "Piezas confirmadas"),
            _kpi("Guías sin confirmación", fnum(sin), f"{fpct(pct_sin)} del total", "yellow"),
            _kpi("Guías con confirmación", fnum(g - sin), f"{fpct(100 - pct_sin)} del total", "blue"),
        ],
        "tables": {
            "combo": {"headers": ["CANAL", "RÉGIMEN", "SIN CONFIRMACIÓN", "CANT. GUÍAS", "% PART."], "rows": table_rows, "aligns": ["", "", "num", "num", "num"], "cls": "tall"}
        },
        "insights": [
            _insight("%", f"La tasa de confirmación es <b>{fpct(100 - pct_sin)}</b>. El segmento <b>{esc(top_conf[0])}</b> aporta <b>{fnum(top_conf[1])}</b> piezas confirmadas."),
            _insight("!", f"<b>{fnum(sin)}</b> guías no tienen confirmación. Priorizar su gestión puede reducir el reproceso operativo y las compensaciones."),
        ],
        "charts": {"conf": {"labels": regs, "datasets": datasets}},
    }


# ---------------------------------------------------------------------------
# Vejez compensaciones
# ---------------------------------------------------------------------------
def vejez_comp(state, filters) -> dict:
    rows = ds.apply_filters(state["base"], filters)
    vez_rows = ds.apply_filters(state["vejez"], filters)
    total = _s(rows, "vejez_comp")
    g = _s(rows, "guias")
    c30g = _s(rows, "c30g")
    c30v = _s(rows, "c30v")
    avg = (total / g) if g else 0.0
    pct30 = _pct(c30g, g)

    by_reg = _group(rows, ["r"], {"vejez_comp": "vejez_comp"}).sort_values("vejez_comp", ascending=False)
    regs = by_reg["r"].tolist() if not by_reg.empty else []

    matrix = {}
    for _, r in vez_rows.iterrows():
        key = (r["r"], r["t"])
        matrix[key] = matrix.get(key, 0.0) + float(r["vejez_comp"])
    totals = {reg: sum(matrix.get((reg, b), 0.0) for b in ds.VEJEZ_BINS) for reg in regs}
    datasets = []
    for b in ds.VEJEZ_BINS:
        raw = [matrix.get((reg, b), 0.0) for reg in regs]
        datasets.append(
            {
                "label": b,
                "color": BIN_COLORS.get(b, "#94a3b8"),
                "data": [(_pct(v, totals[reg])) for reg, v in zip(regs, raw)],
                "raw": raw,
            }
        )

    summary = _group(rows, ["r"], {"vejez_comp": "vejez_comp", "guias": "guias", "c30g": "c30g", "c30v": "c30v"}).sort_values("vejez_comp", ascending=False)
    summary_rows = [
        [esc(r["r"]), fnum(r["guias"]), fnum(r["vejez_comp"], 1), fnum(r["vejez_comp"] / r["guias"] if r["guias"] else 0, 1) + " días", fpct(_pct(r["c30g"], r["guias"]))]
        for _, r in summary.iterrows()
    ]
    top = summary.iloc[0] if not summary.empty else None

    return {
        "page": "vejez-comp",
        "title": "VEJEZ COMPENSACIONES",
        "subtitle": "Antigüedad de las guías en la bodega de compensaciones",
        "chip": _summary(filters),
        "kpis": [
            _kpi("Días de vejez acumulados", fnum(total, 1), "Suma de duración en compensaciones", "accent"),
            _kpi("Promedio por guía", fnum(avg, 1) + " días", f"{fnum(g)} guías en el filtro"),
            _kpi("Guías con vejez > 30 días", fnum(c30g), f"{fpct(pct30)} del total", "yellow"),
            _kpi("Días en guías > 30 días", fnum(c30v, 1), "Duración acumulada crítica", "red"),
        ],
        "tables": {
            "resumen": {"headers": ["REGIONAL", "GUÍAS", "DÍAS", "PROM.", "% > 30"], "rows": summary_rows, "aligns": ["", "num", "num", "num", "num"], "cls": "tall"}
        },
        "insights": [
            _insight("!", f"Solo <b>{fnum(c30g)}</b> guías ({fpct(pct30)}) superan los 30 días de vejez, pero concentran <b>{fnum(c30v, 1)} días</b>, equivalentes al <b>{fpct(_pct(c30v, total))}</b> de la vejez total."),
            _insight("i", f"La regional con mayor vejez acumulada es <b>{esc(top['r']) if top is not None else '—'}</b>, con <b>{fnum(top['vejez_comp'] if top is not None else 0, 1)} días</b> en el periodo filtrado."),
        ],
        "charts": {"vejezComp": {"labels": regs, "datasets": datasets}},
    }


# ---------------------------------------------------------------------------
# Vejez rezagos
# ---------------------------------------------------------------------------
def vejez_rez(state, filters) -> dict:
    rows = ds.apply_filters(state["base"], filters)
    total = _s(rows, "vejez_rez")
    g = _s(rows, "guias")
    r0 = _s(rows, "r0g")
    r30 = _s(rows, "r30g")
    r30v = _s(rows, "r30v")
    rez = _s(rows, "rezago")

    line_rows = rows[rows["y"] >= 2020]
    by_month = _group(line_rows, ["y", "m"], {"vejez_rez": "vejez_rez"}).sort_values(["y", "m"])
    specific_year = filters.get("year", "all") != "all"
    labels = [_month_label(r["y"], r["m"], specific_year) for _, r in by_month.iterrows()]
    values = [float(r["vejez_rez"]) for _, r in by_month.iterrows()]

    canales = sorted(rows["c"].dropna().unique().tolist()) if not rows.empty else []
    regs = sorted(rows["rf"].dropna().unique().tolist()) if not rows.empty else []
    matrix = {}
    for _, r in rows.iterrows():
        key = (r["c"], r["rf"])
        matrix[key] = matrix.get(key, 0.0) + float(r["vejez_rez"])
    datasets = [
        {
            "label": reg,
            "color": REGIMEN_COLORS.get(reg, COLORS[i % len(COLORS)]),
            "data": [matrix.get((can, reg), 0.0) for can in canales],
        }
        for i, reg in enumerate(regs)
    ]

    by_canal = _group(rows, ["c"], {"vejez_rez": "vejez_rez"}).sort_values("vejez_rez", ascending=False)
    top_canal = by_canal.iloc[0] if not by_canal.empty else None

    return {
        "page": "vejez-rez",
        "title": "VEJEZ REZAGOS",
        "subtitle": "Comportamiento de la antigüedad de guías en rezagos",
        "chip": _summary(filters),
        "kpis": [
            _kpi("Días de vejez en rezagos", fnum(total, 1), "Duración acumulada", "accent"),
            _kpi("Guías en rezago", fnum(rez), f"{fpct(_pct(rez, g))} del total"),
            _kpi("Guías con vejez > 0", fnum(r0), f"{fpct(_pct(r0, g))} del total", "yellow"),
            _kpi("Guías con vejez > 30 días", fnum(r30), f"{fnum(r30v, 1)} días acumulados", "red"),
        ],
        "insights": [
            _insight("i", f"La vejez en rezagos es <b>{fnum(total, 1)} días</b> para <b>{fnum(rez)}</b> guías. El <b>{fpct(_pct(r30, g))}</b> de las guías supera los 30 días."),
            _insight("!", f"El canal <b>{esc(top_canal['c']) if top_canal is not None else '—'}</b> concentra <b>{fnum(top_canal['vejez_rez'] if top_canal is not None else 0, 1)} días</b> de vejez de rezagos. Revisar la operación de este canal puede liberar capacidad de bodega."),
        ],
        "charts": {
            "rezLine": {"labels": labels, "values": values},
            "rezBar": {"labels": canales, "datasets": datasets},
        },
    }


# ---------------------------------------------------------------------------
# Tareas · estados
# ---------------------------------------------------------------------------
def tareas_estados(state, filters) -> dict:
    trows = ds.apply_filters(state["tareas"], filters)
    tn = _s(trows, "tar_num")
    tp = _s(trows, "tar_pend")
    tc = _s(trows, "tar_cerr")
    trs = _s(trows, "tar_resp_sum")
    trc = _s(trows, "tar_resp_cnt")
    avg = trs / trc if trc else 0.0

    divs = _group(trows, ["d"], {"tar_num": "tar_num"}).sort_values("tar_num", ascending=False)
    top_divs = divs["d"].head(5).tolist() if not divs.empty else []
    all_divs = top_divs if "OTROS PROCESOS" in top_divs else top_divs + ["OTROS PROCESOS"]
    is_other = lambda d: d not in top_divs

    if filters.get("year", "all") != "all":
        bucket_labels = ds.MONTHS_SHORT[1:]
        buckets = list(range(1, 13))
        bucket_key = lambda r: int(r["m"])
    else:
        years = sorted({int(v) for v in trows["y"].unique() if int(v) >= 2020})
        bucket_labels = [str(y) for y in years]
        buckets = years
        bucket_key = lambda r: int(r["y"])

    matrix = {}
    for _, r in trows.iterrows():
        div = "OTROS PROCESOS" if is_other(r["d"]) else r["d"]
        key = (div, bucket_key(r))
        cur = matrix.get(key, [0.0, 0.0])
        cur[0] += float(r["tar_resp_sum"])
        cur[1] += float(r["tar_resp_cnt"])
        matrix[key] = cur
    datasets = []
    for i, div in enumerate(all_divs):
        data = []
        for b in buckets:
            s, c = matrix.get((div, b), [0.0, 0.0])
            data.append((s / c) if c else None)
        datasets.append({"label": div, "color": DIV_COLORS.get(div, COLORS[i % len(COLORS)]), "data": data})

    pend = _group(trows, ["r"], {"tar_pend": "tar_pend"}).sort_values("tar_pend", ascending=False)
    table = _group(trows, ["r", "d"], {"tar_num": "tar_num", "tar_pend": "tar_pend", "tar_resp_sum": "tar_resp_sum", "tar_resp_cnt": "tar_resp_cnt"})
    table = table.sort_values("tar_num", ascending=False).head(14)
    table_rows = [
        [esc(r["r"]), esc(r["d"]), fnum(r["tar_num"]), fnum(r["tar_pend"]), fnum(r["tar_resp_sum"] / r["tar_resp_cnt"] if r["tar_resp_cnt"] else 0, 1) + " h"]
        for _, r in table.iterrows()
    ]

    return {
        "page": "tareas-estados",
        "title": "TAREAS · ESTADOS",
        "subtitle": "Volumen, pendientes y tiempo de respuesta de las tareas operativas",
        "chip": _summary(filters),
        "kpis": [
            _kpi("Tareas totales", fnum(tn), "Tareas registradas", "accent"),
            _kpi("Tareas pendientes", fnum(tp), f"{fpct(_pct(tp, tn))} del total", "yellow"),
            _kpi("Tareas cerradas", fnum(tc), f"{fpct(_pct(tc, tn))} del total"),
            _kpi("Tiempo promedio respuesta", fnum(avg, 1) + " h", "Tareas con respuesta", "blue"),
        ],
        "tables": {
            "resumen": {"headers": ["REGIONAL", "PROCESO", "CANT. TAREAS", "PENDIENTES", "PROM. RESPUESTA"], "rows": table_rows, "aligns": ["", "", "num", "num", "num"], "cls": "tall"}
        },
        "notes": "Los estados de tarea provienen del catálogo: 0 = CERRADA y 1 = PENDIENTE.",
        "charts": {
            "tareasMes": {"labels": bucket_labels, "datasets": datasets},
            "tareasPie": {"labels": pend["r"].tolist() if not pend.empty else [], "values": [float(v) for v in pend["tar_pend"].tolist()] if not pend.empty else []},
        },
    }


# ---------------------------------------------------------------------------
# Tareas · comparativo
# ---------------------------------------------------------------------------
def tareas_comparativo(state, filters) -> dict:
    trows = ds.apply_filters(state["tareas"], filters)
    years = sorted({int(v) for v in trows["y"].unique() if int(v) > 0}) if not trows.empty else []
    if filters.get("year", "all") != "all":
        current = int(filters["year"])
    else:
        current = years[-1] if years else 0
    prev = current - 1

    cur_rows = trows[trows["y"] == current]
    prev_rows = trows[trows["y"] == prev]
    avg_cur = (_s(cur_rows, "tar_resp_sum") / _s(cur_rows, "tar_resp_cnt")) if _s(cur_rows, "tar_resp_cnt") else 0.0
    avg_prev = (_s(prev_rows, "tar_resp_sum") / _s(prev_rows, "tar_resp_cnt")) if _s(prev_rows, "tar_resp_cnt") else 0.0
    diff = ((avg_cur - avg_prev) * 100.0 / avg_prev) if avg_prev else 0.0
    tasks_cur = _s(cur_rows, "tar_num")

    def monthly(rows_in):
        out = []
        for m in range(1, 13):
            rr = rows_in[rows_in["m"] == m]
            s = _s(rr, "tar_resp_sum")
            c = _s(rr, "tar_resp_cnt")
            out.append({"m": m, "tasks": _s(rr, "tar_num"), "avg": (s / c) if c else None, "pending": _s(rr, "tar_pend")})
        return out

    cur_m = monthly(cur_rows)
    prev_m = monthly(prev_rows)
    labels = ds.MONTHS_SHORT[1:]
    diff_m = []
    for c, p in zip(cur_m, prev_m):
        if p["avg"] and c["avg"] is not None:
            diff_m.append((c["avg"] - p["avg"]) * 100.0 / p["avg"])
        else:
            diff_m.append(None)

    base_filters = dict(filters)
    base_filters["year"] = current
    regional_base = ds.apply_filters(state["base"], base_filters)
    by_region = _group(regional_base, ["r"], {"guias": "guias"}).sort_values("guias", ascending=False)
    region_labels = by_region["r"].tolist() if not by_region.empty else []
    avg_map = {}
    for _, r in _group(cur_rows, ["r"], {"tar_resp_sum": "tar_resp_sum", "tar_resp_cnt": "tar_resp_cnt"}).iterrows():
        avg_map[r["r"]] = (r["tar_resp_sum"] / r["tar_resp_cnt"]) if r["tar_resp_cnt"] else None
    region_guias = dict(zip(by_region["r"], by_region["guias"])) if not by_region.empty else {}

    process = _group(cur_rows, ["d"], {"tar_num": "tar_num", "tar_pend": "tar_pend", "tar_resp_sum": "tar_resp_sum", "tar_resp_cnt": "tar_resp_cnt"})
    process["avg"] = process.apply(lambda r: r["tar_resp_sum"] / r["tar_resp_cnt"] if r["tar_resp_cnt"] else 0.0, axis=1)
    process = process.sort_values("tar_num", ascending=False).head(10)
    process_rows = [[esc(r["d"]), fnum(r["tar_num"]), fnum(r["tar_pend"]), fnum(r["avg"], 1) + " h"] for _, r in process.iterrows()]

    return {
        "page": "tareas-comparativo",
        "title": "TAREAS · COMPARATIVO",
        "subtitle": f"Comparativo de tiempo de respuesta {prev} vs {current}",
        "chip": _summary(filters),
        "kpis": [
            _kpi(f"Promedio {current}", fnum(avg_cur, 1) + " h", f"{fnum(tasks_cur)} tareas", "accent"),
            _kpi(f"Promedio {prev}", fnum(avg_prev, 1) + " h", "Mismo periodo del año anterior"),
            _kpi("Variación", ("+" if diff >= 0 else "") + fpct(diff), "Mejora vs. año anterior" if diff <= 0 else "Aumento vs. año anterior", "blue" if diff <= 0 else "red"),
            _kpi(f"Tareas pendientes {current}", fnum(_s(cur_rows, "tar_pend")), "Al cierre del periodo", "yellow"),
        ],
        "tables": {
            "procesos": {"headers": ["PROCESO", "TAREAS", "PEND.", "PROM."], "rows": process_rows, "aligns": ["", "num", "num", "num"], "cls": "short"}
        },
        "charts": {
            "compMes": {
                "labels": labels,
                "tasks": [x["tasks"] for x in cur_m],
                "avg": [x["avg"] for x in cur_m],
            },
            "compAnual": {
                "labels": labels,
                "prev": [x["avg"] for x in prev_m],
                "cur": [x["avg"] for x in cur_m],
                "diff": diff_m,
            },
            "compRegional": {
                "labels": region_labels,
                "guias": [region_guias.get(r, 0.0) for r in region_labels],
                "avg": [avg_map.get(r) for r in region_labels],
            },
        },
    }


# ---------------------------------------------------------------------------
# Procesos (DIM.PROCESO_TAREAS)
# ---------------------------------------------------------------------------
def procesos(state, filters) -> dict:
    proc = state["procesos"].copy()
    tareas = _group(state["tareas"], ["d"], {"tar_num": "tar_num"})
    task_map = dict(zip(tareas["d"], tareas["tar_num"])) if not tareas.empty else {}
    proc["tareas"] = proc["NOMBRE_DIVISION"].map(task_map).fillna(0.0)
    proc = proc.sort_values("registros", ascending=False)
    top = proc.head(15)

    total_reg = float(proc["registros"].sum())
    total_guias = float(proc["guias"].sum())
    table_rows = [
        [esc(r["NOMBRE_DIVISION"]), fnum(r["registros"]), fnum(r["guias"]), fnum(r["tareas"])]
        for _, r in top.iterrows()
    ]
    proc_guia = int(state["reporte"]["GUIA"].nunique())

    return {
        "page": "procesos",
        "title": "PROCESOS · DIMENSIÓN",
        "subtitle": "Cobertura de la dimensión de procesos de tareas y su relación con el tablero",
        "chip": "DIM.PROCESO_TAREAS",
        "kpis": [
            _kpi("Registros en la dimensión", fnum(total_reg), "Filas del archivo DIM", "accent"),
            _kpi("Guías únicas", fnum(total_guias), "Guías referenciadas"),
            _kpi("Divisiones de proceso", fnum(proc["NOMBRE_DIVISION"].nunique()), "Procesos distintos", "blue"),
            _kpi("Guías en el tablero", fnum(proc_guia), "Base FAC.MBCORE_GUIAS", "yellow"),
        ],
        "tables": {
            "procesos": {"headers": ["DIVISIÓN / PROCESO", "REGISTROS", "GUÍAS ÚNICAS", "TAREAS FAC"], "rows": table_rows, "aligns": ["", "num", "num", "num"], "cls": "tall"}
        },
        "notes": "La dimensión DIM.PROCESO_TAREAS permite clasificar las guías por división. El catálogo de estados (0 = CERRADA, 1 = PENDIENTE) complementa la tabla de tareas.",
        "estados": [
            {"id": int(r["ID_EST_TAREA"]), "label": r["ESTADO_TAREA"]}
            for _, r in state["estados"].iterrows()
        ],
        "charts": {
            "procesosBar": {
                "labels": top["NOMBRE_DIVISION"].tolist(),
                "values": [float(v) for v in top["registros"].tolist()],
            }
        },
    }
