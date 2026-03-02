from __future__ import annotations

import os
import json
import aiosqlite

DATABASE_PATH = os.getenv("DATABASE_PATH", "sparksage.db")

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DATABASE_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def init_db():
    db = await get_db()
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT    NOT NULL,
            role       TEXT    NOT NULL,
            content    TEXT    NOT NULL,
            provider   TEXT,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_conv_channel ON conversations(channel_id);

        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS wizard_state (
            id           INTEGER PRIMARY KEY CHECK (id = 1),
            completed    INTEGER NOT NULL DEFAULT 0,
            current_step INTEGER NOT NULL DEFAULT 0,
            data         TEXT    NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS analytics (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type     TEXT NOT NULL,
            guild_id       TEXT,
            channel_id     TEXT,
            user_id        TEXT,
            provider       TEXT,
            command        TEXT,
            input_tokens   INTEGER DEFAULT 0,
            output_tokens  INTEGER DEFAULT 0,
            estimated_cost REAL    DEFAULT 0.0,
            latency_ms     INTEGER DEFAULT 0,
            created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS faqs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id       TEXT NOT NULL DEFAULT 'global',
            question       TEXT NOT NULL,
            answer         TEXT NOT NULL,
            match_keywords TEXT NOT NULL,
            times_used     INTEGER DEFAULT 0,
            created_by     TEXT,
            created_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS command_permissions (
            command_name TEXT NOT NULL,
            guild_id     TEXT NOT NULL,
            role_id      TEXT NOT NULL,
            PRIMARY KEY (command_name, guild_id, role_id)
        );

        CREATE TABLE IF NOT EXISTS custom_commands (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id     TEXT NOT NULL DEFAULT 'global',
            name         TEXT NOT NULL,
            response     TEXT NOT NULL,
            description  TEXT NOT NULL DEFAULT 'A custom command',
            enabled      INTEGER NOT NULL DEFAULT 1,
            times_used   INTEGER NOT NULL DEFAULT 0,
            created_by   TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(guild_id, name)
        );

        -- Channel Prompts table
        CREATE TABLE IF NOT EXISTS channel_prompts (
            channel_id TEXT PRIMARY KEY,
            guild_id TEXT NOT NULL,
            system_prompt TEXT NOT NULL
        );

        -- Channel Providers table
        CREATE TABLE IF NOT EXISTS channel_providers (
            channel_id TEXT PRIMARY KEY,
            guild_id TEXT NOT NULL,
            provider TEXT NOT NULL
        );

        INSERT OR IGNORE INTO wizard_state (id) VALUES (1);
        """
    )
    await db.commit()


async def get_config(key: str, default: str | None = None) -> str | None:
    db = await get_db()
    cursor = await db.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else default


async def get_all_config() -> dict[str, str]:
    db = await get_db()
    cursor = await db.execute("SELECT key, value FROM config")
    rows = await cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}


async def set_config(key: str, value: str):
    db = await get_db()
    await db.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    await db.commit()


async def set_config_bulk(data: dict[str, str]):
    db = await get_db()
    await db.executemany(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        list(data.items()),
    )
    await db.commit()


async def sync_env_to_db():
    import config as cfg
    env_keys = {
        "DISCORD_TOKEN": cfg.DISCORD_TOKEN or "",
        "AI_PROVIDER": cfg.AI_PROVIDER,
        "GEMINI_API_KEY": cfg.GEMINI_API_KEY or "",
        "GEMINI_MODEL": cfg.GEMINI_MODEL,
        "GROQ_API_KEY": cfg.GROQ_API_KEY or "",
        "GROQ_MODEL": cfg.GROQ_MODEL,
        "OPENROUTER_API_KEY": cfg.OPENROUTER_API_KEY or "",
        "OPENROUTER_MODEL": cfg.OPENROUTER_MODEL,
        "ANTHROPIC_API_KEY": cfg.ANTHROPIC_API_KEY or "",
        "ANTHROPIC_MODEL": cfg.ANTHROPIC_MODEL,
        "OPENAI_API_KEY": cfg.OPENAI_API_KEY or "",
        "OPENAI_MODEL": cfg.OPENAI_MODEL,
        "BOT_PREFIX": cfg.BOT_PREFIX,
        "MAX_TOKENS": str(cfg.MAX_TOKENS),
        "SYSTEM_PROMPT": cfg.SYSTEM_PROMPT,
    }
    db = await get_db()
    for key, value in env_keys.items():
        await db.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (key, value))
    await db.commit()


async def sync_db_to_env():
    from dotenv import dotenv_values, set_key
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    existing = dotenv_values(env_path)
    all_config = await get_all_config()
    for key, value in all_config.items():
        if value and value.strip():
            set_key(env_path, key, value)
        elif key not in existing:
            set_key(env_path, key, value)


async def add_message(channel_id: str, role: str, content: str, provider: str | None = None):
    db = await get_db()
    await db.execute(
        "INSERT INTO conversations (channel_id, role, content, provider) VALUES (?, ?, ?, ?)",
        (channel_id, role, content, provider),
    )
    await db.commit()


async def get_messages(channel_id: str, limit: int = 20) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT role, content, provider, created_at FROM conversations WHERE channel_id = ? ORDER BY id DESC LIMIT ?",
        (channel_id, limit),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in reversed(rows)]


async def clear_messages(channel_id: str):
    db = await get_db()
    await db.execute("DELETE FROM conversations WHERE channel_id = ?", (channel_id,))
    await db.commit()


async def list_channels() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT channel_id, COUNT(*) as message_count, MAX(created_at) as last_active
        FROM conversations
        GROUP BY channel_id
        ORDER BY last_active DESC
        """
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_wizard_state() -> dict:
    db = await get_db()
    cursor = await db.execute("SELECT completed, current_step, data FROM wizard_state WHERE id = 1")
    row = await cursor.fetchone()
    return {
        "completed": bool(row["completed"]),
        "current_step": row["current_step"],
        "data": json.loads(row["data"]),
    }


async def set_wizard_state(completed: bool | None = None, current_step: int | None = None, data: dict | None = None):
    db = await get_db()
    updates = []
    params = []
    if completed is not None:
        updates.append("completed = ?")
        params.append(int(completed))
    if current_step is not None:
        updates.append("current_step = ?")
        params.append(current_step)
    if data is not None:
        updates.append("data = ?")
        params.append(json.dumps(data))
    if updates:
        await db.execute(f"UPDATE wizard_state SET {', '.join(updates)} WHERE id = 1", params)
        await db.commit()


async def create_session(token: str, user_id: str, expires_at: str):
    db = await get_db()
    await db.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at),
    )
    await db.commit()


async def validate_session(token: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT user_id, expires_at FROM sessions WHERE token = ? AND expires_at > datetime('now')",
        (token,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_session(token: str):
    db = await get_db()
    await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
    await db.commit()


async def get_faqs(guild_id: str | None = None) -> list[dict]:
    db = await get_db()
    if guild_id:
        cursor = await db.execute("SELECT * FROM faqs WHERE guild_id = ? ORDER BY id DESC", (guild_id,))
    else:
        cursor = await db.execute("SELECT * FROM faqs ORDER BY id DESC")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def create_faq(question: str, answer: str, match_keywords: str, guild_id: str = "global", created_by: str | None = None) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO faqs (guild_id, question, answer, match_keywords, created_by) VALUES (?, ?, ?, ?, ?)",
        (guild_id, question, answer, match_keywords, created_by),
    )
    await db.commit()
    return cursor.lastrowid


async def delete_faq(faq_id: int):
    db = await get_db()
    await db.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))
    await db.commit()


async def increment_faq_usage(faq_id: int):
    db = await get_db()
    await db.execute("UPDATE faqs SET times_used = times_used + 1 WHERE id = ?", (faq_id,))
    await db.commit()


async def get_permissions() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT command_name, guild_id, role_id FROM command_permissions")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def add_permission(command_name: str, guild_id: str, role_id: str):
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO command_permissions (command_name, guild_id, role_id) VALUES (?, ?, ?)",
        (command_name, guild_id, role_id),
    )
    await db.commit()


async def remove_permission(command_name: str, guild_id: str, role_id: str):
    db = await get_db()
    await db.execute(
        "DELETE FROM command_permissions WHERE command_name = ? AND guild_id = ? AND role_id = ?",
        (command_name, guild_id, role_id),
    )
    await db.commit()


async def get_command_roles(command_name: str, guild_id: str) -> list[str]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT role_id FROM command_permissions WHERE command_name = ? AND guild_id = ?",
        (command_name, guild_id),
    )
    rows = await cursor.fetchall()
    return [row["role_id"] for row in rows]


async def get_custom_commands(guild_id: str | None = None) -> list[dict]:
    db = await get_db()
    if guild_id:
        cursor = await db.execute(
            "SELECT * FROM custom_commands WHERE guild_id = ? ORDER BY name ASC", (guild_id,)
        )
    else:
        cursor = await db.execute("SELECT * FROM custom_commands ORDER BY name ASC")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_custom_command(name: str, guild_id: str = "global") -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM custom_commands WHERE name = ? AND guild_id = ? AND enabled = 1",
        (name, guild_id),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_custom_command(name: str, response: str, description: str = "A custom command", guild_id: str = "global", created_by: str | None = None) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO custom_commands (guild_id, name, response, description, created_by) VALUES (?, ?, ?, ?, ?)",
        (guild_id, name.lower().strip(), response, description, created_by),
    )
    await db.commit()
    return cursor.lastrowid


async def update_custom_command(command_id: int, response: str, description: str) -> bool:
    db = await get_db()
    await db.execute(
        "UPDATE custom_commands SET response = ?, description = ? WHERE id = ?",
        (response, description, command_id),
    )
    await db.commit()
    return True


async def toggle_custom_command(command_id: int, enabled: bool):
    db = await get_db()
    await db.execute(
        "UPDATE custom_commands SET enabled = ? WHERE id = ?",
        (int(enabled), command_id),
    )
    await db.commit()


async def delete_custom_command(command_id: int):
    db = await get_db()
    await db.execute("DELETE FROM custom_commands WHERE id = ?", (command_id,))
    await db.commit()


async def increment_custom_command_usage(command_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE custom_commands SET times_used = times_used + 1 WHERE id = ?", (command_id,)
    )
    await db.commit()


# ===== Channel Prompts Functions =====

async def get_channel_prompt(channel_id: str) -> str | None:
    """Get custom prompt for a specific channel"""
    db = await get_db()
    cursor = await db.execute(
        "SELECT system_prompt FROM channel_prompts WHERE channel_id = ?",
        (channel_id,)
    )
    row = await cursor.fetchone()
    return row["system_prompt"] if row else None


async def set_channel_prompt(channel_id: str, guild_id: str, prompt: str):
    """Set or update a channel prompt"""
    db = await get_db()
    await db.execute(
        """INSERT OR REPLACE INTO channel_prompts (channel_id, guild_id, system_prompt) 
           VALUES (?, ?, ?)""",
        (channel_id, guild_id, prompt)
    )
    await db.commit()


async def delete_channel_prompt(channel_id: str):
    """Remove custom prompt from a channel"""
    db = await get_db()
    await db.execute("DELETE FROM channel_prompts WHERE channel_id = ?", (channel_id,))
    await db.commit()


async def get_guild_channel_prompts(guild_id: str) -> list[dict]:
    """Get all custom prompts for a guild"""
    db = await get_db()
    cursor = await db.execute(
        "SELECT channel_id, system_prompt FROM channel_prompts WHERE guild_id = ?",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    return [{"channel_id": row["channel_id"], "system_prompt": row["system_prompt"]} for row in rows]


# ===== Channel Providers Functions =====

async def get_channel_provider(channel_id: str) -> str | None:
    """Get provider override for a specific channel"""
    db = await get_db()
    cursor = await db.execute(
        "SELECT provider FROM channel_providers WHERE channel_id = ?",
        (channel_id,)
    )
    row = await cursor.fetchone()
    return row["provider"] if row else None


async def set_channel_provider(channel_id: str, guild_id: str, provider: str):
    """Set or update a channel provider override"""
    db = await get_db()
    await db.execute(
        """INSERT OR REPLACE INTO channel_providers (channel_id, guild_id, provider) 
           VALUES (?, ?, ?)""",
        (channel_id, guild_id, provider)
    )
    await db.commit()


async def delete_channel_provider(channel_id: str):
    """Remove provider override from a channel"""
    db = await get_db()
    await db.execute("DELETE FROM channel_providers WHERE channel_id = ?", (channel_id,))
    await db.commit()


async def get_guild_channel_providers(guild_id: str) -> list[dict]:
    """Get all provider overrides for a guild"""
    db = await get_db()
    cursor = await db.execute(
        "SELECT channel_id, provider FROM channel_providers WHERE guild_id = ?",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    return [{"channel_id": row["channel_id"], "provider": row["provider"]} for row in rows]


# ===== Analytics Functions =====

async def get_cost_summary(period: str = "30d") -> dict:
    db = await get_db()
    if period == "7d":
        since = "datetime('now', '-7 days')"
    elif period == "all":
        since = "datetime('1970-01-01')"
    else:
        since = "datetime('now', '-30 days')"

    cursor = await db.execute(
        f"""
        SELECT
            COALESCE(SUM(estimated_cost), 0) as total_cost,
            COALESCE(SUM(input_tokens), 0) as total_input_tokens,
            COALESCE(SUM(output_tokens), 0) as total_output_tokens
        FROM analytics WHERE created_at >= {since}
        """
    )
    totals = dict(await cursor.fetchone())

    cursor = await db.execute(
        f"""
        SELECT provider as name,
               COALESCE(SUM(estimated_cost), 0) as cost,
               COALESCE(SUM(input_tokens), 0) as input_tokens,
               COALESCE(SUM(output_tokens), 0) as output_tokens
        FROM analytics
        WHERE created_at >= {since} AND provider IS NOT NULL
        GROUP BY provider ORDER BY cost DESC
        """
    )
    by_provider = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute(
        f"""
        SELECT DATE(created_at) as date, COALESCE(SUM(estimated_cost), 0) as cost
        FROM analytics WHERE created_at >= {since}
        GROUP BY DATE(created_at) ORDER BY date ASC
        """
    )
    daily = [dict(r) for r in await cursor.fetchall()]
    projected = (totals["total_cost"] / max(len(daily), 1)) * 30 if daily else 0

    return {
        "total_cost": totals["total_cost"],
        "projected_monthly": projected,
        "total_input_tokens": totals["total_input_tokens"],
        "total_output_tokens": totals["total_output_tokens"],
        "by_provider": by_provider,
        "daily": daily,
    }


async def get_total_messages() -> int:
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) as count FROM conversations")
    row = await cursor.fetchone()
    return row["count"] if row else 0


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None