import os
import socket
from flask import Flask, request, jsonify
import psycopg2

app = Flask(__name__)
PORT = int(os.getenv("PORT", "5000"))

# ====== Postgres (Supabase Transaction Pooler - IPv4) ======
PGHOST = os.getenv("PGHOST", "").strip()
PGPORT = int(os.getenv("PGPORT", "6543"))
PGDATABASE = os.getenv("PGDATABASE", "postgres").strip()
PGUSER = os.getenv("PGUSER", "").strip()
PGPASSWORD = os.getenv("PGPASSWORD", "").strip()
PGSSLMODE = os.getenv("PGSSLMODE", "require").strip()

DEFAULT_COMMAND = os.getenv("DEFAULT_COMMAND", "CLOSE").strip().upper()

if not (PGHOST and PGUSER and PGPASSWORD):
    raise RuntimeError("Faltan variables: PGHOST, PGUSER, PGPASSWORD (y opcional PGPORT/PGDATABASE/PGSSLMODE).")

def resolve_ipv4(host: str) -> str:
    # Fuerza resolución IPv4 (AF_INET)
    infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
    return infos[0][4][0]

def db():
    ip4 = resolve_ipv4(PGHOST)
    return psycopg2.connect(
        host=PGHOST,       # nombre (opcional pero útil)
        hostaddr=ip4,      # IPv4 forzado
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD,
        sslmode=PGSSLMODE,
        connect_timeout=5,
    )

def get_latest_command():
    with db() as conn, conn.cursor() as cur:
        cur.execute("""
            select command
            from public.door_command_log
            order by created_at desc
            limit 1
        """)
        row = cur.fetchone()
        return row[0] if row else DEFAULT_COMMAND

def insert_command(cmd: str):
    with db() as conn, conn.cursor() as cur:
        cur.execute("insert into public.door_command_log (command) values (%s)", (cmd,))

def insert_status(state: str, ts_ms):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into public.door_status_log (state, ts_ms) values (%s, %s)",
            (state, ts_ms),
        )

def get_last_status():
    with db() as conn, conn.cursor() as cur:
        cur.execute("""
            select state, ts_ms, created_at
            from public.door_status_log
            order by created_at desc
            limit 1
        """)
        row = cur.fetchone()
        if not row:
            return None
        return {"state": row[0], "ts_ms": row[1], "created_at": row[2].isoformat()}

# ====== ROUTES ======
@app.get("/")
def root():
    return "server activo", 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.get("/door/command")
def get_command():
    return get_latest_command(), 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.post("/door/command")
def set_command():
    data = request.get_json(silent=True) or {}
    cmd = str(data.get("command", "")).strip().upper()
    if cmd not in ("OPEN", "CLOSE"):
        return jsonify(error="command must be OPEN or CLOSE"), 400

    insert_command(cmd)
    return jsonify(ok=True, command=cmd)

@app.post("/door/status")
def post_status():
    data = request.get_json(silent=True) or {}
    state = str(data.get("state", "")).strip().upper()
    ts_ms = data.get("ts_ms", None)

    if state not in ("UNLOCKED", "LOCKED"):
        return jsonify(error="state must be UNLOCKED or LOCKED"), 400

    if ts_ms is not None:
        try:
            ts_ms = int(ts_ms)
        except Exception:
            return jsonify(error="ts_ms must be int"), 400

    insert_status(state, ts_ms)
    return jsonify(ok=True)

@app.get("/door/status")
def get_status():
    return jsonify(command=get_latest_command(), last_status=get_last_status())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
