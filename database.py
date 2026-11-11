"""Acceso a SQLite: usuarios, áreas, dashboards y permisos."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DASHBOARD_DB", os.path.join(BASE_DIR, "dashboard.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'user',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    password_changed_at TEXT
);

CREATE TABLE IF NOT EXISTS areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT NOT NULL DEFAULT 'layers',
    color TEXT NOT NULL DEFAULT '#2563eb',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS dashboards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT NOT NULL DEFAULT 'chart',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_ready INTEGER NOT NULL DEFAULT 0,
    UNIQUE (area_id, slug)
);

CREATE TABLE IF NOT EXISTS user_areas (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, area_id)
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    first_run = not os.path.exists(DB_PATH)
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()

        cur = conn.execute("SELECT COUNT(*) AS n FROM users")
        if cur.fetchone()["n"] == 0:
            now = datetime.now().isoformat(timespec="seconds")
            admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
            conn.execute(
                """INSERT INTO users (username, password_hash, full_name, role, is_active, created_at, password_changed_at)
                   VALUES (?, ?, ?, 'admin', 1, ?, ?)""",
                ("admin", generate_password_hash(admin_password), "Administrador", now, now),
            )
            conn.commit()
            if first_run:
                print(f"[db] Usuario administrador creado: admin / {admin_password}")

        cur = conn.execute("SELECT COUNT(*) AS n FROM areas")
        if cur.fetchone()["n"] == 0:
            seed = [
                ("area-1", "AREA 1", "Operación, logística y seguimiento nacional.", "home", "#2563eb", 1),
                ("area-2", "AREA 2", "Área de análisis pendiente de nombrar.", "layers", "#0ea5e9", 2),
                ("area-3", "AREA 3", "Área de análisis pendiente de nombrar.", "chart", "#7c3aed", 3),
            ]
            conn.executemany(
                "INSERT INTO areas (slug, name, description, icon, color, sort_order) VALUES (?,?,?,?,?,?)",
                seed,
            )
            conn.commit()

            area_ids = {r["slug"]: r["id"] for r in conn.execute("SELECT id, slug FROM areas")}
            dashboards = [
                (area_ids["area-1"], "compensaciones-rezagos", "Compensaciones y rezagos",
                 "Compensaciones, rezagos, confirmaciones y tareas del modelo MBCORE.", "chart", 1, 1, 1),
                (area_ids["area-1"], "dashboard-2", "Dashboard 2",
                 "Espacio reservado para un nuevo tablero del área.", "sitemap", 2, 1, 0),
                (area_ids["area-2"], "dashboard-1", "Dashboard 1",
                 "Espacio reservado para un nuevo tablero del área.", "chart", 1, 1, 0),
                (area_ids["area-2"], "dashboard-2", "Dashboard 2",
                 "Espacio reservado para un nuevo tablero del área.", "table", 2, 1, 0),
                (area_ids["area-3"], "dashboard-1", "Dashboard 1",
                 "Espacio reservado para un nuevo tablero del área.", "layers", 1, 1, 0),
                (area_ids["area-3"], "dashboard-2", "Dashboard 2",
                 "Espacio reservado para un nuevo tablero del área.", "users", 2, 1, 0),
            ]
            conn.executemany(
                """INSERT INTO dashboards
                   (area_id, slug, name, description, icon, sort_order, is_active, is_ready)
                   VALUES (?,?,?,?,?,?,?,?)""",
                dashboards,
            )
            conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------
def get_user_by_username(username: str):
    conn = get_conn()
    try:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
    finally:
        conn.close()


def get_user(user_id: int):
    conn = get_conn()
    try:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()


def list_users() -> list[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM users ORDER BY role = 'admin' DESC, username"
        ).fetchall()
    finally:
        conn.close()


def create_user(username: str, password: str, full_name: str, role: str = "user") -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO users (username, password_hash, full_name, role, is_active, created_at, password_changed_at)
               VALUES (?,?,?,?,1,?,?)""",
            (username.strip().lower(), generate_password_hash(password), full_name.strip(), role, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def update_password(user_id: int, password: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE users SET password_hash = ?, password_changed_at = ? WHERE id = ?",
            (generate_password_hash(password), now, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def toggle_user(user_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute("UPDATE users SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Áreas y dashboards
# ---------------------------------------------------------------------------
def list_areas_for_user(user_id: int, role: str) -> list[sqlite3.Row]:
    conn = get_conn()
    try:
        if role == "admin":
            return conn.execute(
                "SELECT * FROM areas WHERE is_active = 1 ORDER BY sort_order, name"
            ).fetchall()
        assigned = conn.execute(
            "SELECT COUNT(*) AS n FROM user_areas WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
        if assigned == 0:
            return conn.execute(
                "SELECT * FROM areas WHERE is_active = 1 ORDER BY sort_order, name"
            ).fetchall()
        return conn.execute(
            """SELECT a.* FROM areas a
               JOIN user_areas ua ON ua.area_id = a.id
               WHERE ua.user_id = ? AND a.is_active = 1
               ORDER BY a.sort_order, a.name""",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def get_area(area_id: int):
    conn = get_conn()
    try:
        return conn.execute("SELECT * FROM areas WHERE id = ? AND is_active = 1", (area_id,)).fetchone()
    finally:
        conn.close()


def list_areas() -> list[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            """SELECT a.*, (SELECT COUNT(*) FROM dashboards d WHERE d.area_id = a.id AND d.is_active = 1) AS total_dashboards
               FROM areas a ORDER BY a.sort_order, a.name"""
        ).fetchall()
    finally:
        conn.close()


def list_dashboards(area_id: int) -> list[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM dashboards WHERE area_id = ? AND is_active = 1 ORDER BY sort_order, name",
            (area_id,),
        ).fetchall()
    finally:
        conn.close()


def get_dashboard(area_id: int, slug: str):
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM dashboards WHERE area_id = ? AND slug = ? AND is_active = 1",
            (area_id, slug),
        ).fetchone()
    finally:
        conn.close()


def count_dashboards(area_id: int) -> int:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM dashboards WHERE area_id = ? AND is_active = 1", (area_id,)
        ).fetchone()["n"]
    finally:
        conn.close()
