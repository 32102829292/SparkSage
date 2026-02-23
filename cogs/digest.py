"""cogs/digest.py — Daily digest scheduler"""
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import aiosqlite
import os
import providers
from datetime import datetime, timedelta

DB_PATH = os.getenv("DATABASE_PATH", "sparksage.db")


async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute_fetchone("SELECT value FROM config WHERE key=?", (key,))
        return row["value"] if row else None


class Digest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_digest.start()

    def cog_unload(self):
        self.daily_digest.cancel()

    @tasks.loop(hours=24)
    async def daily_digest(self):
        enabled = await get_setting("digest_enabled")
        if enabled != "true":
            return

        channel_id = await get_setting("digest_channel_id")
        if not channel_id:
            return

        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            return

        # Get messages from past 24h
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                "SELECT role, content FROM messages WHERE created_at >= ? ORDER BY created_at",
                (cutoff,)
            )

        if not rows:
            return

        conversation = "\n".join(f"{r['role'].upper()}: {r['content'][:200]}" for r in rows[:50])
        system = "You are a helpful summarizer. Create a concise daily digest of the AI assistant conversations. Use bullet points. Highlight key topics discussed."
        user_msg = f"Summarize these conversations from the past 24 hours:\n\n{conversation}"

        try:
            summary, provider_name = providers.chat([{"role": "user", "content": user_msg}], system)
        except Exception as e:
            summary = f"Could not generate digest: {e}"

        embed = discord.Embed(
            title=f"📰 Daily Digest — {datetime.utcnow().strftime('%B %d, %Y')}",
            description=summary[:4000],
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="SparkSage Daily Digest")
        await channel.send(embed=embed)

    @daily_digest.before_loop
    async def before_digest(self):
        await self.bot.wait_until_ready()

    digest_group = app_commands.Group(name="digest", description="Daily digest settings")

    @digest_group.command(name="setup", description="[Admin] Configure daily digest")
    @app_commands.describe(channel="Channel to post daily digest")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def digest_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO config (key,value) VALUES (?,?)", ("digest_channel_id", str(channel.id)))
            await db.execute("INSERT OR REPLACE INTO config (key,value) VALUES (?,?)", ("digest_enabled", "true"))
            await db.commit()
        await interaction.response.send_message(f"✅ Daily digest will be posted to {channel.mention} every 24 hours.", ephemeral=True)

    @digest_group.command(name="now", description="[Admin] Post a digest right now")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def digest_now(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await self.daily_digest()
        await interaction.followup.send("✅ Digest posted!", ephemeral=True)

    @digest_group.command(name="disable", description="[Admin] Disable daily digest")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def digest_disable(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO config (key,value) VALUES (?,?)", ("digest_enabled", "false"))
            await db.commit()
        await interaction.response.send_message("✅ Daily digest disabled.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Digest(bot))