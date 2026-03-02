from fastapi import APIRouter, Depends, HTTPException
from api.deps import get_current_user
import aiosqlite
import os
from pydantic import BaseModel
import logging
import providers
import config

logger = logging.getLogger('sparksage')
DB_PATH = os.getenv("DATABASE_PATH", "sparksage.db")

# REMOVED the prefix - it's now just an empty router
router = APIRouter()


class OnboardingSettings(BaseModel):
    enabled: bool
    channel_id: str | None = None
    template: str = ""
    use_ai: bool = True


async def get_setting(guild_id: str, key: str) -> str | None:
    """Get onboarding setting from config table"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT value FROM config WHERE key = ?",
                (f"onboarding_{key}_{guild_id}",)
            )
            row = await cursor.fetchone()
            return row["value"] if row else None
    except Exception as e:
        logger.error(f"Error getting setting {key}: {e}")
        return None


async def set_setting(guild_id: str, key: str, value: str):
    """Save onboarding setting to config table"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (f"onboarding_{key}_{guild_id}", str(value) if value is not None else "")
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Error setting {key}: {e}")
        raise


@router.get("/{guild_id}")
async def get_onboarding_settings(guild_id: str, user=Depends(get_current_user)):
    """Get onboarding settings for a guild"""
    try:
        enabled = await get_setting(guild_id, "enabled")
        channel_id = await get_setting(guild_id, "channel_id")
        template = await get_setting(guild_id, "template")
        use_ai = await get_setting(guild_id, "use_ai")
        
        return {
            "enabled": enabled == "true" if enabled is not None else False,
            "channel_id": channel_id if channel_id and channel_id != "" else None,
            "template": template if template else "",
            "use_ai": use_ai == "true" if use_ai is not None else True
        }
    except Exception as e:
        logger.error(f"Error getting onboarding settings: {e}")
        return {
            "enabled": False,
            "channel_id": None,
            "template": "",
            "use_ai": True
        }


@router.put("/{guild_id}")
async def update_onboarding_settings(
    guild_id: str, 
    settings: OnboardingSettings,
    user=Depends(get_current_user)
):
    """Update onboarding settings for a guild"""
    try:
        await set_setting(guild_id, "enabled", "true" if settings.enabled else "false")
        await set_setting(guild_id, "channel_id", settings.channel_id or "")
        await set_setting(guild_id, "template", settings.template or "")
        await set_setting(guild_id, "use_ai", "true" if settings.use_ai else "false")
        
        logger.info(f"✅ Onboarding settings saved for guild {guild_id}")
        return {"status": "success", "guild_id": guild_id}
    except Exception as e:
        logger.error(f"Error updating onboarding settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update onboarding settings")


@router.post("/{guild_id}/preview")
async def preview_onboarding_message(
    guild_id: str,
    settings: OnboardingSettings,
    user=Depends(get_current_user)
):
    """Preview what a welcome message would look like"""
    try:
        if settings.template and not settings.use_ai:
            # Use custom template
            preview = settings.template
            preview = preview.replace("{user}", "NewUser")
            preview = preview.replace("{server}", "Server Name")
            preview = preview.replace("{mention}", "@NewUser")
            preview = preview.replace("{count}", "42")
        else:
            # Use AI to generate preview
            system = "You are a friendly Discord bot. Write a short, warm welcome message for a new member. Use emojis. Keep it to 1-2 sentences."
            user_prompt = f"Welcome NewUser to 'Server Name'. The server has 42 members."
            try:
                message, _ = providers.chat([{"role": "user", "content": user_prompt}], system)
                preview = message
            except Exception as e:
                logger.error(f"AI preview failed: {e}")
                preview = "Welcome to Server Name, NewUser! 🎉 We're glad to have you here."
        
        return {"preview": preview}
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        return {"preview": "Welcome to the server! 🎉"}