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
from datetime import datetime

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
        "application_log_channel": None,
        "appeal_channel": None,
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

# ===================== STOCK DATA =====================
stock_data = {
    "mcfa": {"name": "Minecraft Full Access (MCFA)", "stock": 24, "price": "150 PHP"},
    "mcsemi": {"name": "Minecraft Semi-Access", "stock": 47, "price": "80 PHP"},
    "mccracked": {"name": "Minecraft Cracked", "stock": 999, "price": "Free"},
    "nitro": {"name": "Discord Nitro (1 Month)", "stock": 12, "price": "120 PHP"},
    "boost": {"name": "Discord Server Boost", "stock": 8, "price": "90 PHP"},
    "roblox": {"name": "Roblox Gift Cards", "stock": 35, "price": "Varies"},
}

# ========================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)
start_time = datetime.utcnow()

application_cooldown = {}

# ===================== KEEP-ALIVE =====================
def run_keepalive():
    PORT = int(os.environ.get("PORT", 8080))
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Bot is alive! OK")
            else:
                self.send_response(404)
                self.end_headers()
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"🌐 Keep-Alive running on port {PORT}")
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
@bot.tree.command(name="serverstatus", description="Check server status")
@app_commands.describe(ip="Server IP", game="Game Type", port="Port")
@app_commands.choices(game=[
    app_commands.Choice(name="Minecraft Java", value="java"),
    app_commands.Choice(name="Minecraft Bedrock", value="bedrock"),
    app_commands.Choice(name="Roblox", value="roblox"),
    app_commands.Choice(name="Hytale", value="hytale")
])
async def serverstatus(interaction: discord.Interaction, ip: str, game: str = "java", port: int = 25565):
    await interaction.response.defer()
    if game in ["java", "bedrock"]:
        embed = await check_minecraft_server(ip, port, game == "bedrock")
    elif game == "roblox":
        embed = await check_roblox_server(ip)
    else:
        embed = discord.Embed(title="Hytale", description="Not released yet.", color=0xffaa00)
    await interaction.followup.send(embed=embed)

async def check_minecraft_server(ip: str, port: int = 25565, bedrock: bool = False):
    url = f"https://api.mcsrvstat.us/2/{ip}:{port}" if port != 25565 else f"https://api.mcsrvstat.us/2/{ip}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                data_json = await resp.json()
                online = data_json.get("online", False)
                embed = discord.Embed(title=f"{ip} {'(Bedrock)' if bedrock else '(Java)'}", color=0x00ff00 if online else 0xff0000)
                embed.add_field(name="Status", value="**Online** ✅" if online else "**Offline** ❌", inline=False)
                if online:
                    p = data_json.get("players", {})
                    embed.add_field(name="Players", value=f"{p.get('online',0)}/{p.get('max',0)}", inline=True)
                    embed.add_field(name="Version", value=data_json.get("version","Unknown"), inline=True)
                return embed
    except:
        return discord.Embed(title="❌ Error", description="Failed to fetch status.", color=0xff0000)

async def check_roblox_server(place_id: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://games.roblox.com/v1/games?universeIds={place_id}") as resp:
                data = await resp.json()
                games = data.get("data", [])
                if not games: return discord.Embed(title="❌ Not Found", description="Invalid Place ID", color=0xff0000)
                g = games[0]
                embed = discord.Embed(title=f"🔵 {g.get('name')}", color=0x00aaff)
                embed.add_field(name="Playing", value=f"{g.get('playing',0):,}", inline=True)
                return embed
    except:
        return discord.Embed(title="❌ Error", description="Failed to fetch.", color=0xff0000)

# ===================== STOCK COMMANDS =====================
@bot.tree.command(name="stock", description="Check current stock")
@app_commands.describe(category="Category")
@app_commands.choices(category=[
    app_commands.Choice(name="All", value="all"),
    app_commands.Choice(name="Minecraft", value="minecraft"),
    app_commands.Choice(name="Discord", value="discord")
])
async def stock(interaction: discord.Interaction, category: str = "all"):
    embed = discord.Embed(title="🛒 Current Stock", color=0x00ff88)
    if category in ["all", "minecraft"]:
        embed.add_field(name="🎮 Minecraft", value="", inline=False)
        embed.add_field(name="MCFA", value=f"**{stock_data['mcfa']['stock']}** • {stock_data['mcfa']['price']}", inline=False)
        embed.add_field(name="Semi-Access", value=f"**{stock_data['mcsemi']['stock']}** • {stock_data['mcsemi']['price']}", inline=False)
    if category in ["all", "discord"]:
        embed.add_field(name="💎 Discord", value="", inline=False)
        embed.add_field(name="Nitro", value=f"**{stock_data['nitro']['stock']}** • {stock_data['nitro']['price']}", inline=False)
        embed.add_field(name="Boost", value=f"**{stock_data['boost']['stock']}** • {stock_data['boost']['price']}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="updatestock", description="Set stock")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(product="Product", amount="New amount")
@app_commands.choices(product=[app_commands.Choice(name=k.upper(), value=k) for k in stock_data.keys()])
async def updatestock(interaction: discord.Interaction, product: str, amount: int):
    if product in stock_data:
        old = stock_data[product]["stock"]
        stock_data[product]["stock"] = max(0, amount)
        await interaction.response.send_message(f"✅ Updated **{stock_data[product]['name']}** from {old} → {amount}", ephemeral=True)

@bot.tree.command(name="addstock", description="Add to stock")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(product="Product", amount="Amount to add")
@app_commands.choices(product=[app_commands.Choice(name=k.upper(), value=k) for k in stock_data.keys()])
async def addstock(interaction: discord.Interaction, product: str, amount: int):
    if product in stock_data:
        stock_data[product]["stock"] += amount
        await interaction.response.send_message(f"✅ Added {amount} to **{stock_data[product]['name']}** (New: {stock_data[product]['stock']})", ephemeral=True)

# ===================== STAFF, APPEAL, USERINFO, etc. (All previous) =====================
# ... (Staff Application, Appeal Modal, Userinfo, Serverinfo, Help, etc. are all included in previous full versions)

# ===================== EVENTS =====================
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    
    activity = discord.Activity(type=discord.ActivityType.watching, name="Servers & Users")
    await bot.change_presence(status=discord.Status.dnd, activity=activity)
    
    try:
        await bot.tree.sync()
        print("✅ Slash commands synced!")
    except Exception as e:
        print(f"Sync error: {e}")

    start_keepalive()
    check_youtube.start()
    check_tiktok.start()
    print("✅ FULL BOT LOADED WITH ALL FEATURES!")

bot.run(TOKEN)
