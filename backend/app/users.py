"""User accounts in SQLite. No OTP (team decision): sign-up returns a long random token that the
phone keeps forever, so the user never logs in again. Only a hash of the token is stored."""
import hashlib
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "nisaarthi.db"
MAX_CONTACTS = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT NOT NULL,
  language TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  phone TEXT NOT NULL,
  position INTEGER NOT NULL
);
"""


class InvalidInput(ValueError):
    pass


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def normalize_phone(raw):
    """Indian mobile numbers: accepts +91 / 0 prefixes and spaces; returns +91XXXXXXXXXX."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise InvalidInput("phone")
    return "+91" + digits


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _clean_contacts(contacts, own_phone):
    if not contacts:
        raise InvalidInput("contacts_required")
    if len(contacts) > MAX_CONTACTS:
        raise InvalidInput("contacts_max")
    out, seen = [], set()
    for c in contacts:
        name = (c.get("name") or "").strip()
        if not name:
            raise InvalidInput("contact_name")
        phone = normalize_phone(c.get("phone"))
        if phone == own_phone:
            raise InvalidInput("contact_is_self")
        if phone in seen:
            continue
        seen.add(phone)
        out.append({"name": name[:60], "phone": phone})
    return out


def _user_dict(conn, row):
    contacts = conn.execute(
        "SELECT name, phone FROM contacts WHERE user_id = ? ORDER BY position", (row["id"],)).fetchall()
    return {"id": row["id"], "name": row["name"], "phone": row["phone"], "language": row["language"],
            "created_at": row["created_at"], "contacts": [dict(c) for c in contacts]}


def create_user(conn, name, phone, language, contacts):
    name = (name or "").strip()
    if not name:
        raise InvalidInput("name")
    phone = normalize_phone(phone)
    contacts = _clean_contacts(contacts, phone)
    user_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    with conn:
        conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                     (user_id, name[:60], phone, language or "en", _hash(token),
                      datetime.now(timezone.utc).isoformat()))
        conn.executemany("INSERT INTO contacts (user_id, name, phone, position) VALUES (?, ?, ?, ?)",
                         [(user_id, c["name"], c["phone"], i) for i, c in enumerate(contacts)])
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user_dict(conn, row), token


def user_for_token(conn, token):
    if not token:
        return None
    row = conn.execute("SELECT * FROM users WHERE token_hash = ?", (_hash(token),)).fetchone()
    return _user_dict(conn, row) if row else None


def update_profile(conn, user_id, name=None, language=None):
    with conn:
        if name is not None:
            if not name.strip():
                raise InvalidInput("name")
            conn.execute("UPDATE users SET name = ? WHERE id = ?", (name.strip()[:60], user_id))
        if language is not None:
            conn.execute("UPDATE users SET language = ? WHERE id = ?", (language, user_id))
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user_dict(conn, row)


def replace_contacts(conn, user_id, contacts):
    own = conn.execute("SELECT phone FROM users WHERE id = ?", (user_id,)).fetchone()["phone"]
    contacts = _clean_contacts(contacts, own)
    with conn:
        conn.execute("DELETE FROM contacts WHERE user_id = ?", (user_id,))
        conn.executemany("INSERT INTO contacts (user_id, name, phone, position) VALUES (?, ?, ?, ?)",
                         [(user_id, c["name"], c["phone"], i) for i, c in enumerate(contacts)])
    return contacts
