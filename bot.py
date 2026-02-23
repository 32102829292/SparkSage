from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import config
import providers
import db as database
import logging
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('sparksage')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents)

MAX_HISTORY = 20


async def get_history(channel_id: int) -> list[dict]:
    """Get conversation history for a channel from the database."""
    try:
        messages = await database.get_messages(str(channel_id), limit=MAX_HISTORY)
        return [{"role": m["role"], "content": m["content"]} for m in messages]
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return []


async def ask_ai(channel_id: int, user_name: str, message: str) -> tuple[str, str]:
    """Send a message to AI and return (response, provider_name)."""
    # Store user message in DB
    await database.add_message(str(channel_id), "user", f"{user_name}: {message}")

    history = await get_history(channel_id)

    try:
        response, provider_name = providers.chat(history, config.SYSTEM_PROMPT)
        # Store assistant response in DB
        await database.add_message(str(channel_id), "assistant", response, provider=provider_name)
        return response, provider_name
    except RuntimeError as e:
        error_msg = f"Sorry, all AI providers failed:\n{e}"
        logger.error(error_msg)
        return error_msg, "none"


def get_bot_status() -> dict:
    """Return bot status info for the dashboard API."""
    try:
        if bot.is_ready():
            return {
                "online": True,
                "username": str(bot.user),
                "latency_ms": round(bot.latency * 1000, 1),
                "guild_count": len(bot.guilds),
                "guilds": [{"id": str(g.id), "name": g.name, "member_count": g.member_count} for g in bot.guilds],
            }
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
    
    return {"online": False, "username": None, "latency_ms": None, "guild_count": 0, "guilds": []}


# --- Events ---


@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord."""
    logger.info(f"Bot is starting up...")
    
    # Initialize database when bot is ready
    try:
        await database.init_db()
        await database.sync_env_to_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    # Load cogs
    cogs = [
        "cogs.faq",
        "cogs.review",
        "cogs.onboarding",
        "cogs.permissions",
        "cogs.translate",
        "cogs.analytics",
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f"Loaded cog: {cog}")
        except Exception as e:
            logger.warning(f"Failed to load cog {cog}: {e}")

    available = providers.get_available_providers()
    primary = config.AI_PROVIDER
    provider_info = config.PROVIDERS.get(primary, {})

    logger.info(f"SparkSage is online as {bot.user}")
    logger.info(f"Connected to {len(bot.guilds)} guild(s)")
    logger.info(f"Primary provider: {provider_info.get('name', primary)} ({provider_info.get('model', '?')})")
    logger.info(f"Fallback chain: {' -> '.join(available)}")

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{config.BOT_PREFIX}help | {len(bot.guilds)} servers"
        )
    )


@bot.event
async def on_message(message: discord.Message):
    """Handle incoming messages."""
    if message.author == bot.user:
        return

    # Respond when mentioned
    if bot.user in message.mentions:
        clean_content = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
        if not clean_content:
            clean_content = "Hello! How can I help you today?"

        async with message.channel.typing():
            response, provider_name = await ask_ai(
                message.channel.id, message.author.display_name, clean_content
            )

        # Split long responses (Discord 2000 char limit)
        for i in range(0, len(response), 2000):
            await message.reply(response[i:i + 2000])

    await bot.process_commands(message)


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Called when the bot joins a new guild."""
    logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
    
    # Update bot status with new server count
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{config.BOT_PREFIX}help | {len(bot.guilds)} servers"
        )
    )


@bot.event
async def on_guild_remove(guild: discord.Guild):
    """Called when the bot leaves a guild."""
    logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
    
    # Update bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{config.BOT_PREFIX}help | {len(bot.guilds)} servers"
        )
    )


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    """Handle command errors."""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("I don't have the required permissions to do that.")
    else:
        logger.error(f"Command error: {error}")
        await ctx.send(f"An error occurred: {error}")


# --- Slash Commands ---


@bot.tree.command(name="ask", description="Ask SparkSage a question")
@app_commands.describe(question="Your question for SparkSage")
async def ask(interaction: discord.Interaction, question: str):
    """Ask the AI a question."""
    await interaction.response.defer()
    
    try:
        response, provider_name = await ask_ai(
            interaction.channel_id, interaction.user.display_name, question
        )
        
        provider_label = config.PROVIDERS.get(provider_name, {}).get("name", provider_name)
        footer = f"\n-# Powered by {provider_label}"

        # Split long responses
        for i in range(0, len(response), 1900):
            chunk = response[i:i + 1900]
            if i + 1900 >= len(response):
                chunk += footer
            await interaction.followup.send(chunk)
            
    except Exception as e:
        logger.error(f"Error in ask command: {e}")
        await interaction.followup.send("Sorry, an error occurred while processing your question.")


@bot.tree.command(name="clear", description="Clear SparkSage's conversation memory for this channel")
async def clear(interaction: discord.Interaction):
    """Clear conversation history for the current channel."""
    try:
        await database.clear_messages(str(interaction.channel_id))
        await interaction.response.send_message("✅ Conversation history cleared!")
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        await interaction.response.send_message("❌ Failed to clear conversation history.")


@bot.tree.command(name="summarize", description="Summarize the recent conversation in this channel")
async def summarize(interaction: discord.Interaction):
    """Summarize the recent conversation."""
    await interaction.response.defer()
    
    try:
        history = await get_history(interaction.channel_id)
        if not history:
            await interaction.followup.send("No conversation history to summarize.")
            return

        # Create a summary prompt
        conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        summary_prompt = f"Please summarize the key points from this conversation in a concise bullet-point format:\n\n{conversation_text}"
        
        response, provider_name = await ask_ai(
            interaction.channel_id, "System", summary_prompt
        )
        
        await interaction.followup.send(f"**📊 Conversation Summary:**\n{response}")
        
    except Exception as e:
        logger.error(f"Error in summarize command: {e}")
        await interaction.followup.send("Sorry, an error occurred while summarizing.")


@bot.tree.command(name="provider", description="Show which AI provider SparkSage is currently using")
async def provider(interaction: discord.Interaction):
    """Show current AI provider information."""
    primary = config.AI_PROVIDER
    provider_info = config.PROVIDERS.get(primary, {})
    available = providers.get_available_providers()

    embed = discord.Embed(
        title="🤖 AI Provider Status",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Current Provider",
        value=f"**{provider_info.get('name', primary)}**\nModel: `{provider_info.get('model', '?')}`",
        inline=False
    )
    
    embed.add_field(
        name="Provider Type",
        value="🆓 Free" if provider_info.get('free') else "💰 Paid",
        inline=True
    )
    
    embed.add_field(
        name="Fallback Chain",
        value=" → ".join(available),
        inline=True
    )
    
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ping", description="Check the bot's latency")
async def ping(interaction: discord.Interaction):
    """Check bot latency."""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: `{latency}ms`",
        color=discord.Color.green() if latency < 200 else discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="stats", description="Show bot statistics")
async def stats(interaction: discord.Interaction):
    """Show bot statistics."""
    embed = discord.Embed(
        title="📊 SparkSage Statistics",
        color=discord.Color.purple()
    )
    
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    
    # Get provider info
    primary = config.AI_PROVIDER
    provider_info = config.PROVIDERS.get(primary, {})
    embed.add_field(name="Primary Provider", value=provider_info.get('name', primary), inline=True)
    
    # Get database stats
    try:
        total_messages = await database.get_total_messages()
        embed.add_field(name="Total Messages", value=str(total_messages), inline=True)
    except:
        pass
    
    await interaction.response.send_message(embed=embed)


# --- Run ---


def main():
    """Main entry point for the bot."""
    # Check for Discord token
    if not config.DISCORD_TOKEN:
        logger.error("Error: DISCORD_TOKEN not set. Copy .env.example to .env and fill in your tokens.")
        return

    # Log token info (first few chars only for security)
    token_preview = config.DISCORD_TOKEN[:10] + "..." if len(config.DISCORD_TOKEN) > 10 else "invalid"
    logger.info(f"Discord token loaded (starts with: {token_preview})")
    logger.info(f"Token length: {len(config.DISCORD_TOKEN)} characters")

    # Check for AI providers
    available = providers.get_available_providers()
    if not available:
        logger.error("Error: No AI providers configured. Add at least one API key to .env")
        logger.error("Free options: GEMINI_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY")
        return
    
    logger.info(f"Available AI providers: {', '.join(available)}")

    # Run the bot
    try:
        bot.run(config.DISCORD_TOKEN, log_handler=None)  # Let our logging handle it
    except discord.LoginFailure:
        logger.error("Failed to login: Invalid Discord token")
        logger.error("Please check your DISCORD_TOKEN in the .env file")
    except discord.PrivilegedIntentsRequired:
        logger.error("Failed to login: Privileged intents not enabled")
        logger.error("Please enable Message Content Intent in the Discord Developer Portal")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")


if __name__ == "__main__":
    main()