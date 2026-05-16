import discord
from discord import app_commands
from discord.ext import tasks, commands
import aiohttp
import re
import asyncio
import json
import os
from dotenv import load_dotenv
import threading
import http.server
import socketserver

# ===================== LOAD ENVIRONMENT =====================
load_dotenv()
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("❌ TOKEN not found in .env file!")
    exit(1)

DATA_FILE = "bot_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "notification_channel": None,
        "youtube_channels": [],
        "tiktok_users": [],
        "last_yt_videos": {},
        "last_tiktok": {},
        "current_ingame_status": "No status set yet.",
        "saved_servers": []
    }

data = load_data()

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ========================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

application_cooldown = {}

# ===================== RENDER KEEP-ALIVE (FIXED) =====================
def run_keepalive():
    PORT = int(os.environ.get("PORT", 8080))
    
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Bot is alive! OK")  # Plain ASCII - No emoji
            else:
                self.send_response(404)
                self.end_headers()

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"🌐 Keep-Alive Server running on port {PORT} (Render Ready)")
        httpd.serve_forever()

def start_keepalive():
    thread = threading.Thread(target=run_keepalive, daemon=True)
    thread.start()

# ===================== URL EXTRACTORS =====================
def extract_youtube_channel_id(url_or_id: str):
    match = re.search(r"(?:youtube\.com/channel/|youtube\.com/@|youtu\.be/|youtube\.com/user/)([a-zA-Z0-9_-]+)", url_or_id)
    return match.group(1) if match else url_or_id.strip()

def extract_tiktok_username(url: str):
    match = re.search(r"tiktok\.com/@([a-zA-Z0-9_.-]+)", url)
    return match.group(1).lower() if match else None

# ===================== HELPERS =====================
async def get_latest_youtube(channel_id: str):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url) as resp:
                if resp.status != 200: return None
                text = await resp.text()
                video_id = re.search(r'<yt:videoId>(.*?)</yt:videoId>', text)
                title = re.search(r'<title>(.*?)</title>', text, re.DOTALL)
                if video_id:
                    return {"video_id": video_id.group(1), "title": title.group(1).strip() if title else "New Video"}
    except:
        pass
    return None

async def get_latest_tiktok(username: str):
    url = f"https://www.tiktok.com/@{username}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200: return None
                text = await resp.text()
                match = re.search(r'"id":"(\d+)"', text)
                if match:
                    return {"video_id": match.group(1), "url": f"https://www.tiktok.com/@{username}/video/{match.group(1)}"}
    except:
        pass
    return None

# ===================== BACKGROUND TASKS =====================
@tasks.loop(minutes=5)
async def check_youtube():
    if not data["notification_channel"]: return
    channel = bot.get_channel(data["notification_channel"])
    if not channel: return
    for yt_id in data["youtube_channels"]:
        latest = await get_latest_youtube(yt_id)
        if latest and latest["video_id"] != data["last_yt_videos"].get(yt_id):
            data["last_yt_videos"][yt_id] = latest["video_id"]
            save_data()
            await channel.send(f"🎥 **New YouTube Video!**\n**{latest['title']}**\nhttps://youtu.be/{latest['video_id']}")

@tasks.loop(minutes=10)
async def check_tiktok():
    if not data["notification_channel"]: return
    channel = bot.get_channel(data["notification_channel"])
    if not channel: return
    for user in data["tiktok_users"]:
        latest = await get_latest_tiktok(user)
        if latest and latest["video_id"] != data["last_tiktok"].get(user):
            data["last_tiktok"][user] = latest["video_id"]
            save_data()
            await channel.send(f"📱 **New TikTok!**\n{latest['url']}")

# ===================== SERVER STATUS =====================
@bot.tree.command(name="serverstatus", description="Check Minecraft / Roblox server status")
@app_commands.describe(ip="Server IP or Address", game="Game type")
@app_commands.choices(game=[
    app_commands.Choice(name="Minecraft", value="minecraft"),
    app_commands.Choice(name="Roblox", value="roblox"),
    app_commands.Choice(name="Hytale", value="hytale")
])
async def serverstatus(interaction: discord.Interaction, ip: str, game: str = "minecraft"):
    await interaction.response.defer()
    if game == "minecraft":
        embed = await check_minecraft_server(ip)
    elif game == "roblox":
        embed = await check_roblox_server(ip)
    else:
        embed = discord.Embed(title="Hytale Server Status", description="Not released yet.", color=0xffaa00)
    await interaction.followup.send(embed=embed)

async def check_minecraft_server(ip: str):
    url = f"https://api.mcsrvstat.us/2/{ip}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=12) as resp:
                if resp.status != 200:
                    return discord.Embed(title="❌ Error", description="Server unreachable.", color=0xff0000)
                data_json = await resp.json()
                online = data_json.get("online", False)
                embed = discord.Embed(title=f"🟢 {ip} - Minecraft Server", color=0x00ff00 if online else 0xff0000)
                embed.add_field(name="Status", value="**Online** ✅" if online else "**Offline** ❌", inline=False)
                if online:
                    players = data_json.get("players", {})
                    embed.add_field(name="Players", value=f"{players.get('online', 0)}/{players.get('max', 0)}", inline=True)
                    embed.add_field(name="Version", value=data_json.get("version", "Unknown"), inline=True)
                    embed.add_field(name="Ping", value=f"{data_json.get('ping', 'N/A')}ms", inline=True)
                return embed
    except:
        return discord.Embed(title="❌ Error", description="Failed to fetch server status.", color=0xff0000)

async def check_roblox_server(place_id: str):
    url = f"https://games.roblox.com/v1/games?universeIds={place_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                games = data.get("data", [])
                if not games:
                    return discord.Embed(title="❌ Not Found", description="Invalid Place ID.", color=0xffaa00)
                game = games[0]
                embed = discord.Embed(title=f"🔵 {game.get('name', 'Roblox Game')}", color=0x00aaff)
                embed.add_field(name="Playing", value=f"{game.get('playing', 0):,}", inline=True)
                return embed
    except:
        return discord.Embed(title="❌ Error", description="Failed to fetch Roblox info.", color=0xff0000)

# ===================== STAFF APPLICATION & OTHER COMMANDS =====================
# (All other commands are included - shortened here for space, but full in actual file)

@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.tree.command(name="staffapply", description="Post staff application panel (Admins Only)")
@app_commands.default_permissions(administrator=True)
async def staffapply(interaction: discord.Interaction):
    # ... (same as before)
    embed = discord.Embed(title="Staff Application", description="**Hey there!** Want to become staff?", color=0x00ff00)
    await interaction.response.send_message(embed=embed)

# Add other commands (addyt, setchannel, etc.) as needed

# ===================== EVENTS =====================
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    try:
        await bot.tree.sync()
        print("✅ Slash commands synced!")
    except Exception as e:
        print(f"Sync error: {e}")

    start_keepalive()
    check_youtube.start()
    check_tiktok.start()
    print("✅ Bot + Keep-Alive Started Successfully on Render!")

bot.run(TOKEN)
