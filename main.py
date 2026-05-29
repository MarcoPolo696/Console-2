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
        description=f"{m
