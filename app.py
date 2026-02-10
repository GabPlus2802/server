import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# ====== ENV ======
# Render suele inyectar PORT automáticamente
PORT = int(os.getenv("PORT", "5000"))

# Token simple para proteger POST /door/command (recomendado)
API_TOKEN = os.getenv("", "")  # si lo dejas vacío, NO exige token

# Estado en memoria (mínimo)
command = os.getenv("DEFAULT_COMMAND", "CLOSE").strip().upper()  # OPEN/CLOSE
last_status = None


def require_token():
    if not API_TOKEN:
        return True  # sin token configurado -> sin protección
    token = request.headers.get("X-API-KEY", "")
    return token == API_TOKEN


@app.get("/door/command")
def get_command():
    # Respuesta texto plano para el ESP32
    return command, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.post("/door/command")
def set_command():
    if not require_token():
        return jsonify(error="unauthorized"), 401

    data = request.get_json(silent=True) or {}
    c = str(data.get("command", "")).strip().upper()
    if c not in ("OPEN", "CLOSE"):
        return jsonify(error="command must be OPEN or CLOSE"), 400

    global command
    command = c
    return jsonify(ok=True, command=command)


@app.post("/door/status")
def post_status():
    # el ESP32 envía: {"state":"UNLOCKED"|"LOCKED","ts_ms":123}
    global last_status
    last_status = request.get_json(silent=True) or {}
    return jsonify(ok=True)


@app.get("/door/status")
def get_status():
    return jsonify(command=command, last_status=last_status)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
