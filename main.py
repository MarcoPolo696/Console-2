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
import time

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

# ===================== BACKUP KEEP-ALIVE (Thread) =====================
def run_keepalive():
    PORT = 8080
    Handler = http.server.SimpleHTTPRequestHandler
    
    class KeepAliveHandler(Handler):
        def do_GET(self):
            if self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"Bot is alive! ✅")
            else:
                self.send_response(404)
                self.end_headers()

    with socketserver.TCPServer(("", PORT), KeepAliveHandler) as httpd:
        print(f"🌐 Backup Keep-Alive Server running on port {PORT}")
        httpd.serve_forever()

# Start keepalive in background thread
def start_keepalive():
    keepalive_thread = threading.Thread(target=run_keepalive, daemon=True)
    keepalive_thread.start()

# ===================== (Rest of your code - same as before) =====================

# ... [All your previous functions: extract_youtube, get_latest_youtube, check_youtube, etc.]

# ===================== SERVER STATUS (same) =====================
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
        embed = discord.Embed(title="Hytale", description="Not released yet.", color=0xffaa00)
    await interaction.followup.send(embed=embed)

# (Include all other commands and the full Staff Application System here - same as previous full code)

# ===================== EVENTS =====================
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    try:
        await bot.tree.sync()
        print("✅ Slash commands synced!")
    except Exception as e:
        print(f"Sync error: {e}")

    start_keepalive()           # ← Backup Keep-Alive
    check_youtube.start()
    check_tiktok.start()
    print("✅ Bot started with Backup Keep-Alive!")

bot.run(TOKEN)
