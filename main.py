import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from dotenv import load_dotenv
from keep_alive import keep_alive
import os
import json
import asyncio

# =========================
# LOAD TOKEN
# =========================
load_dotenv()
TOKEN = os.getenv("TOKEN")

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.all()

bot = commands.Bot(command_prefix="$", intents=intents)

# =========================
# DATABASE FILES
# =========================
WHITELIST_FILE = "whitelist.json"
ORDERS_FILE = "orders.json"

# =========================
# LOAD/SAVE FUNCTIONS
# =========================
def load_data(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f)

    with open(file, "r") as f:
        return json.load(f)


def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)


whitelist = load_data(WHITELIST_FILE, [])
orders = load_data(ORDERS_FILE, [])

# =========================
# DEFAULT STATUS
# =========================
DEFAULT_ACTIVITY = discord.Activity(
    type=discord.ActivityType.watching,
    name="Managing Servers"
)

# =========================
# EVENTS
# =========================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    await bot.change_presence(
        status=discord.Status.online,
        activity=DEFAULT_ACTIVITY
    )

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(e)

# =========================
# HELP PANEL
        description=f"{member.m
