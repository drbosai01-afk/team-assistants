"""
Простое JSON-хранилище для MVP.
"""

import json
import secrets
from pathlib import Path
from datetime import datetime
from typing import Optional

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

USERS_FILE = DATA_DIR / "users.json"
CLIENTS_FILE = DATA_DIR / "clients.json"
HISTORY_FILE = DATA_DIR / "history.json"


def _load(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user(user_id: int) -> Optional[dict]:
    users = _load(USERS_FILE, {})
    return users.get(str(user_id))


def upsert_user(user_id: int, **fields) -> dict:
    users = _load(USERS_FILE, {})
    key = str(user_id)
    if key not in users:
        users[key] = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "client_id": None,
        }
    users[key].update(fields)
    users[key]["updated_at"] = datetime.now().isoformat()
    _save(USERS_FILE, users)
    return users[key]


def list_clients() -> list[dict]:
    return list(_load(CLIENTS_FILE, {}).values())


def get_client(client_id: str) -> Optional[dict]:
    clients = _load(CLIENTS_FILE, {})
    return clients.get(client_id)


def create_client(name: str, owner_id: int, description: str = "") -> dict:
    clients = _load(CLIENTS_FILE, {})
    client_id = secrets.token_urlsafe(8)
    clients[client_id] = {
        "id": client_id,
        "name": name,
        "description": description,
        "owner_id": owner_id,
        "created_at": datetime.now().isoformat(),
        "users": [],
    }
    _save(CLIENTS_FILE, clients)
    return clients[client_id]


def add_user_to_client(user_id: int, client_id: str) -> None:
    clients = _load(CLIENTS_FILE, {})
    if client_id in clients and user_id not in clients[client_id]["users"]:
        clients[client_id]["users"].append(user_id)
        _save(CLIENTS_FILE, clients)


def get_history(user_id: int, agent: str, limit: int = 20) -> list[dict]:
    history = _load(HISTORY_FILE, {})
    user_hist = history.get(str(user_id), {}).get(agent, [])
    return user_hist[-limit:]


def get_history_by_client(client_id: str, agent: str, limit: int = 20) -> list[dict]:
    history = _load(HISTORY_FILE, {})
    tenant_hist = history.get(f"client:{client_id}", {}).get(agent, [])
    return tenant_hist[-limit:]


def append_message(key: str, agent: str, role: str, content: str) -> None:
    history = _load(HISTORY_FILE, {})
    if key not in history:
        history[key] = {}
    if agent not in history[key]:
        history[key][agent] = []
    history[key][agent].append({
        "role": role,
        "content": content,
        "ts": datetime.now().isoformat(),
    })
    history[key][agent] = history[key][agent][-100:]
    _save(HISTORY_FILE, history)


def clear_history(key: str, agent: str) -> None:
    history = _load(HISTORY_FILE, {})
    if key in history and agent in history[key]:
        del history[key][agent]
        _save(HISTORY_FILE, history)
