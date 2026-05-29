import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import os

# =========================
# KEEP ALIVE
# =========================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# =========================
# LOAD ENV
# =========================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# =========================
# OWNER / DEV SYSTEM
# =========================
OWNER_IDS = [1192047136192352256]
DEV_IDS = []

def is_owner_or_dev(user_id):
    return user_id in OWNER_IDS or user_id in DEV_IDS

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="$",
    intents=intents,
    help_command=None
)

# =========================
# READY EVENT
# =========================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Managing Servers"
        )
    )

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")

    except Exception as e:
        print(e)

# =========================
# PREFIX COMMANDS
# =========================
@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)}ms")

@bot.command()
async def adddev(ctx, user: discord.User):
    if ctx.author.id not in OWNER_IDS:
        return await ctx.send("❌ Owner only")

    if user.id not in DEV_IDS:
        DEV_IDS.append(user.id)

    await ctx.send(f"✅ Added {user.mention} as developer")

@bot.command()
async def removedev(ctx, user: discord.User):
    if ctx.author.id not in OWNER_IDS:
        return await ctx.send("❌ Owner only")

    if user.id in DEV_IDS:
        DEV_IDS.remove(user.id)

    await ctx.send(f"🗑️ Removed {user.mention} from developers")

@bot.command()
async def sync(ctx, guild_id: int = None):
    if not is_owner_or_dev(ctx.author.id):
        return await ctx.send("❌ Owner or Dev only")

    try:
        if guild_id:
            guild = discord.Object(id=guild_id)
            synced = await bot.tree.sync(guild=guild)

        else:
            synced = await bot.tree.sync()

        embed = discord.Embed(
            title="✅ Slash Commands Synced",
            description=f"Synced {len(synced)} commands",
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)

    msg = await ctx.send(f"✅ Cleared {amount} messages")
    await msg.delete(delay=3)

# =========================
# SLASH COMMANDS
# =========================
@bot.tree.command(name="ping", description="Shows latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🏓 Pong! {round(bot.latency * 1000)}ms"
    )

@bot.tree.command(name="presence", description="Change bot presence")
async def presence(
    interaction: discord.Interaction,
    activity_type: str,
    text: str
):
    if not is_owner_or_dev(interaction.user.id):
        return await interaction.response.send_message(
            "❌ Owner or Dev only",
            ephemeral=True
        )

    activity_type = activity_type.lower()

    if activity_type == "playing":
        activity = discord.Game(name=text)

    elif activity_type == "watching":
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=text
        )

    elif activity_type == "listening":
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=text
        )

    elif activity_type == "streaming":
        activity = discord.Streaming(
            name=text,
            url="https://twitch.tv/discord"
        )

    else:
        return await interaction.response.send_message(
            "❌ Invalid activity type",
            ephemeral=True
        )

    await bot.change_presence(
        status=discord.Status.online,
        activity=activity
    )

    await interaction.response.send_message(
        f"✅ Presence updated to {activity_type} {text}"
    )

@bot.tree.command(name="sync", description="Sync slash commands")
async def slash_sync(
    interaction: discord.Interaction,
    guild_id: str = None
):
    if not is_owner_or_dev(interaction.user.id):
        return await interaction.response.send_message(
            "❌ Owner or Dev only",
            ephemeral=True
        )

    try:
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            synced = await bot.tree.sync(guild=guild)

        else:
            synced = await bot.tree.sync()

        await interaction.response.send_message(
            f"✅ Synced {len(synced)} commands"
        )

    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error: {e}",
            ephemeral=True
        )

@bot.tree.command(name="kick", description="Kick a member")
@app_commands.checks.has_permissions(kick_members=True)
async def slash_kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason"
):
    await member.kick(reason=reason)

    embed = discord.Embed(
        title="👢 Member Kicked",
        description=f"{member.mention} was kicked",
        color=discord.Color.red()
    )

    embed.add_field(name="Reason", value=reason)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.checks.has_permissions(ban_members=True)
async def slash_ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason"
):
    await member.ban(reason=reason)

    embed = discord.Embed(
        title="🔨 Member Banned",
        description=f"{member.mention} was banned",
        color=discord.Color.dark_red()
    )

    embed.add_field(name="Reason", value=reason)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clear", description="Clear messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_clear(
    interaction: discord.Interaction,
    amount: int
):
    await interaction.channel.purge(limit=amount)

    await interaction.response.send_message(
        f"✅ Cleared {amount} messages",
        ephemeral=True
    )

@bot.tree.command(name="userinfo", description="Show user info")
async def userinfo(
    interaction: discord.Interaction,
    member: discord.Member
):
    embed = discord.Embed(
        title=f"{member}",
        color=discord.Color.blurple()
    )

    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined", value=str(member.joined_at.date()))

    embed.set_thumbnail(url=member.display_avatar.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Show server info")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild

    embed = discord.Embed(
        title=guild.name,
        color=discord.Color.green()
    )

    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Owner", value=str(guild.owner))

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    await interaction.response.send_message(embed=embed)

# =========================
# START BOT
# =========================
keep_alive()

if TOKEN is None:
    print("❌ DISCORD_TOKEN not found")

else:
    bot.run(TOKEN)
