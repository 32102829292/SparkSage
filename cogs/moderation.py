"""cogs/moderation.py — AI content moderation pipeline"""
import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import json
import providers

DB_PATH = os.getenv("DATABASE_PATH", "sparksage.db")


async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute_fetchone("SELECT value FROM config WHERE key=?", (key,))
        return row["value"] if row else None


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        enabled = await get_setting("moderation_enabled")
        if enabled != "true":
            return

        mod_log_id = await get_setting("mod_log_channel_id")
        if not mod_log_id:
            return

        # Skip short messages
        if len(message.content) < 10:
            return

        system = (
            "You are a content moderator. Analyze the message for toxicity, spam, harassment, and rule violations. "
            "Respond ONLY with valid JSON in this exact format: "
            '{"flagged": false, "reason": "", "severity": "low"}'
        )
        try:
            result, _ = providers.chat(
                [{"role": "user", "content": f"Analyze: {message.content[:500]}"}],
                system
            )
            # Clean and parse JSON
            result = result.strip()
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
            data = json.loads(result)
        except Exception:
            return

        if not data.get("flagged"):
            return

        severity = data.get("severity", "low")
        reason = data.get("reason", "No reason provided")

        # Only alert on medium/high severity
        if severity == "low":
            return

        mod_channel = message.guild.get_channel(int(mod_log_id))
        if not mod_channel:
            return

        color = discord.Color.red() if severity == "high" else discord.Color.orange()
        embed = discord.Embed(
            title=f"🚨 Moderation Alert — {severity.upper()}",
            color=color,
            timestamp=message.created_at
        )
        embed.add_field(name="User", value=f"{message.author.mention} ({message.author})", inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Message", value=message.content[:500], inline=False)
        embed.add_field(name="Jump to Message", value=f"[Click here]({message.jump_url})", inline=False)
        embed.set_footer(text="⚠️ For human review only — no automatic action taken")

        await mod_channel.send(embed=embed)

    mod_group = app_commands.Group(name="moderation", description="Moderation settings")

    @mod_group.command(name="setup", description="[Admin] Configure AI moderation")
    @app_commands.describe(log_channel="Channel for moderation alerts")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mod_setup(self, interaction: discord.Interaction, log_channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO config (key,value) VALUES (?,?)", ("mod_log_channel_id", str(log_channel.id)))
            await db.execute("INSERT OR REPLACE INTO config (key,value) VALUES (?,?)", ("moderation_enabled", "true"))
            await db.commit()
        await interaction.response.send_message(f"✅ Moderation alerts will be sent to {log_channel.mention}.", ephemeral=True)

    @mod_group.command(name="disable", description="[Admin] Disable AI moderation")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mod_disable(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO config (key,value) VALUES (?,?)", ("moderation_enabled", "false"))
            await db.commit()
        await interaction.response.send_message("✅ Moderation disabled.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))