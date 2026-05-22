import discord
from discord import app_commands
from discord.ext import tasks, commands
import aiohttp
import re
import json
import os
import random
import string
import io
from datetime import datetime, timedelta
from mcstatus import JavaServer
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# ========================= CONFIG & ENV =========================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("❌ ERROR: No token found! Please make sure your DISCORD_TOKEN is set in your environment variables.")
    exit()

DATA_FILE = "bot_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "notification_channel": None,
        "nitro_gen_channel": None,
        "youtube_channels": [],
        "tiktok_users": [],
        "last_yt_videos": {},
        "last_tiktok": {},
        "current_ingame_status": "No status set yet.",
        "favorite_servers": [],
        "economy": {},
        "shop_items": {
            "vip": {"name": "VIP Role", "price": 5000, "description": "Permanent VIP role"}
        }
    }

data = load_data()

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ===================== KEEPALIVE SERVER =====================
app = Flask('')

@app.route('/')
def home():
    return "🟢 Bot is alive and running!"

def run():
    # Runs the webserver on port 8080
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ========================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=["!", "."], intents=intents)

# Remove the default help command so we can create our own custom /help
bot.remove_command("help")

# ===================== HELPERS =====================
async def get_latest_youtube(channel_id: str):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200: return None
            text = await resp.text()
            video_id = re.search(r'<yt:videoId>(.*?)</yt:videoId>', text)
            title = re.search(r'<title>(.*?)</title>', text, re.DOTALL)
            if video_id:
                return {"video_id": video_id.group(1), "title": title.group(1).strip() if title else "New Video"}
    return None

async def get_latest_tiktok(username: str):
    url = f"https://www.tiktok.com/@{username}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200: return None
            text = await resp.text()
            match = re.search(r'"id":"(\d+)"', text)
            if match:
                return {"video_id": match.group(1), "url": f"https://www.tiktok.com/@{username}/video/{match.group(1)}"}
    return None

def get_balance(user_id):
    return data["economy"].setdefault(str(user_id), {"balance": 100, "last_daily": None})

def save_balance(user_id, balance_data):
    data["economy"][str(user_id)] = balance_data
    save_data()

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
            await channel.send(f"📱 **New TikTok from @{user}!**\n{latest['url']}")

@tasks.loop(seconds=20)
async def auto_nitro_gen():
    if not data.get("nitro_gen_channel"): return
    channel = bot.get_channel(data["nitro_gen_channel"])
    if not channel: return
    
    code = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    
    embed = discord.Embed(
        title="🎁 Auto Nitro Generator", 
        description=f"https://discord.gift/{code}", 
        color=0xff73fa
    )
    await channel.send(embed=embed)

# ===================== ALL ORIGINAL + ADDED COMMANDS =====================

@bot.tree.command(name="help", description="List all available bot commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="📜 Bot Commands List", color=0x3498db, description="Here is a list of all commands available on this bot!")
    
    embed.add_field(name="🛠️ Utility", value="`/ping` - Check latency\n`/userinfo` - User details\n`/serverinfo` - Server details\n`/serverstatus` - Check MC server\n`/avatar` - Get user avatar", inline=False)
    embed.add_field(name="💰 Economy", value="`/balance` - Check coins\n`/daily` - Claim daily reward\n`/work` - Work for coins\n`/shop` - View shop\n`/buy` - Buy item", inline=False)
    embed.add_field(name="🎲 Fun", value="`/8ball` - Magic 8ball\n`/hug` - Hug someone\n`/coinflip` - Flip a coin\n`/roll` - Roll a dice\n`/rps` - Play Rock, Paper, Scissors", inline=False)
    embed.add_field(name="📦 Generators (Public)", value="`.stock` - Check MCFA account stock", inline=False)
    
    embed.add_field(name="🛡️ Moderation (Admin/Mods)", value="`/purge` - Delete messages\n`/kick` - Kick member\n`/ban` - Ban member\n`/timeout` - Timeout member\n`/setchannel` - Set notifications\n`/addyt` - Add YouTube\n`/addtiktok` - Add TikTok\n`/ingame` - Set in-game status\n`/status` - Set bot presence", inline=False)
    embed.add_field(name="🎁 Admin/Generator Tools", value="`.genmcfa` - Generate MCFA account(s)\n`.genrandommcfa` - Fake MCFA account\n`.setautonitro` - Auto Nitro drops\n`.addmcfa` - Add stock\n`.nitrochecker` - Check Nitro code\n`/pay` & `.pay` - Admin pay command", inline=False)
    
    embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setchannel", description="Set notification channel")
@app_commands.default_permissions(administrator=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    data["notification_channel"] = channel.id
    save_data()
    await interaction.response.send_message(f"✅ Notifications set to {channel.mention}")

@bot.tree.command(name="addyt", description="Add YouTube channel ID")
@app_commands.default_permissions(administrator=True)
async def addyt(interaction: discord.Interaction, channel_id: str):
    data["youtube_channels"].append(channel_id)
    save_data()
    await interaction.response.send_message(f"✅ Added YouTube: `{channel_id}`")

@bot.tree.command(name="addtiktok", description="Add TikTok username")
@app_commands.default_permissions(administrator=True)
async def addtiktok(interaction: discord.Interaction, username: str):
    username = username.replace("@", "").strip()
    data["tiktok_users"].append(username)
    save_data()
    await interaction.response.send_message(f"✅ Added TikTok: @{username}")

@bot.tree.command(name="ingame", description="Update in-game status")
@app_commands.default_permissions(administrator=True)
async def ingame(interaction: discord.Interaction, status: str):
    data["current_ingame_status"] = status
    if data["notification_channel"]:
        channel = bot.get_channel(data["notification_channel"])
        await channel.send(f"🎮 **In-Game Status Updated**\n{status}")
    await interaction.response.send_message("✅ In-game status updated!", ephemeral=True)

@bot.tree.command(name="status", description="Show or change bot status (Streaming Supported)")
@app_commands.default_permissions(administrator=True)
async def status(interaction: discord.Interaction, action: str = "show", activity_type: str = "watching", activity_name: str = "Servers", status_type: str = "dnd"):
    if action.lower() == "set":
        activity = None
        at = activity_type.lower()

        if at == "playing": activity = discord.Game(name=activity_name)
        elif at == "watching": activity = discord.Activity(type=discord.ActivityType.watching, name=activity_name)
        elif at == "listening": activity = discord.Activity(type=discord.ActivityType.listening, name=activity_name)
        elif at == "competing": activity = discord.Activity(type=discord.ActivityType.competing, name=activity_name)
        elif at == "streaming": activity = discord.Streaming(name=activity_name, url="https://twitch.tv/example")

        status_dict = {"online": discord.Status.online, "idle": discord.Status.idle, "dnd": discord.Status.dnd, "invisible": discord.Status.invisible}
        await bot.change_presence(status=status_dict.get(status_type.lower(), discord.Status.dnd), activity=activity)

        await interaction.response.send_message(f"✅ Status updated to {activity_type} {activity_name} | {status_type}", ephemeral=True)
        return

    embed = discord.Embed(title="🤖 Bot Status", color=0x00ff00)
    channel_mention = f"<#{data['notification_channel']}>" if data["notification_channel"] else "❌ Not Set"
    embed.add_field(name="Notification Channel", value=channel_mention, inline=False)
    embed.add_field(name="YouTube Channels", value=len(data["youtube_channels"]), inline=True)
    embed.add_field(name="TikTok Accounts", value=len(data["tiktok_users"]), inline=True)
    embed.add_field(name="In-Game Status", value=data["current_ingame_status"], inline=False)

    await interaction.response.send_message(embed=embed)

# ===================== ECONOMY & MORE =====================

@bot.tree.command(name="balance", description="Check your balance")
async def balance(interaction: discord.Interaction):
    bal = get_balance(interaction.user.id)
    await interaction.response.send_message(f"💰 **{interaction.user.name}** has **{bal['balance']}** coins.")

@bot.tree.command(name="daily", description="Claim daily reward")
async def daily(interaction: discord.Interaction):
    user = get_balance(interaction.user.id)
    now = datetime.now()

    if user.get("last_daily"):
        last = datetime.fromisoformat(user["last_daily"])
        if now - last < timedelta(days=1):
            return await interaction.response.send_message("⏳ Already claimed today!")

    reward = random.randint(100, 250)
    user["balance"] += reward
    user["last_daily"] = now.isoformat()
    save_balance(interaction.user.id, user)

    await interaction.response.send_message(f"🎉 +**{reward}** coins!")

@bot.tree.command(name="work", description="Work for coins")
async def work(interaction: discord.Interaction):
    earnings = random.randint(40, 90)
    user = get_balance(interaction.user.id)
    user["balance"] += earnings
    save_balance(interaction.user.id, user)
    await interaction.response.send_message(f"🛠️ You earned **{earnings}** coins!")

@bot.tree.command(name="serverstatus", description="Check Minecraft server")
async def serverstatus(interaction: discord.Interaction, address: str):
    await interaction.response.defer()
    try:
        server = JavaServer.lookup(address)
        status = await server.async_status()

        embed = discord.Embed(title=f"🟢 {address}", color=0x00ff00)
        embed.add_field(name="Players", value=f"{status.players.online}/{status.players.max}", inline=True)
        embed.add_field(name="Version", value=status.version.name, inline=True)

        await interaction.followup.send(embed=embed)
    except:
        await interaction.followup.send("❌ Server unreachable.")

@bot.tree.command(name="userinfo", description="User info with avatar on top")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"👤 {member}", color=0x00ff00)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id, inline=False)
    embed.add_field(name="Joined", value=member.joined_at.strftime("%b %d, %Y") if member.joined_at else "Unknown", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Server information")
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=f"📊 {g.name}", color=0x00ff88)
    embed.add_field(name="Members", value=g.member_count, inline=True)
    embed.add_field(name="Roles", value=len(g.roles), inline=True)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="purge", description="Delete messages")
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.channel.purge(limit=amount + 1)
    await interaction.response.send_message(f"🧹 Deleted **{amount}** messages!", ephemeral=True)

@bot.tree.command(name="8ball", description="Magic 8ball")
async def eightball(interaction: discord.Interaction, question: str):
    answers = ["Yes!", "No!", "Maybe...", "Definitely!", "Ask again later."]
    await interaction.response.send_message(f"🎱 **{question}**\n**Answer:** {random.choice(answers)}")

@bot.tree.command(name="hug", description="Hug someone")
async def hug(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f"{interaction.user.mention} hugged {member.mention} 🤗")

@bot.tree.command(name="pay", description="Pay coins to another user")
@app_commands.default_permissions(administrator=True)
async def pay_slash(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        return await interaction.response.send_message("❌ Amount must be greater than 0.")
    
    sender = get_balance(interaction.user.id)
    if sender["balance"] < amount:
        return await interaction.response.send_message("❌ You don't have enough coins!")
        
    receiver = get_balance(member.id)
    sender["balance"] -= amount
    receiver["balance"] += amount
    
    save_balance(interaction.user.id, sender)
    save_balance(member.id, receiver)
    await interaction.response.send_message(f"💸 You successfully paid **{amount}** coins to {member.mention}!")

@bot.tree.command(name="shop", description="View the shop")
async def shop(interaction: discord.Interaction):
    embed = discord.Embed(title="🛒 Server Shop", color=0xffd700)
    if not data.get("shop_items"):
        embed.description = "The shop is currently empty!"
    else:
        for item_id, item_info in data["shop_items"].items():
            embed.add_field(name=f"**{item_info['name']}** [{item_id}] - {item_info['price']} coins", value=item_info['description'], inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buy", description="Buy an item from the shop")
async def buy(interaction: discord.Interaction, item_id: str):
    item_id = item_id.lower()
    if item_id not in data["shop_items"]:
        return await interaction.response.send_message("❌ Item not found in the shop. Use `/shop` to view available items.")
        
    item = data["shop_items"][item_id]
    user = get_balance(interaction.user.id)
    
    if user["balance"] < item["price"]:
        return await interaction.response.send_message(f"❌ You don't have enough! You need **{item['price']}** coins to buy **{item['name']}**.")
        
    user["balance"] -= item["price"]
    save_balance(interaction.user.id, user)
    await interaction.response.send_message(f"🛍️ You successfully purchased **{item['name']}** for {item['price']} coins!")

@bot.tree.command(name="ping", description="Check the bot's latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency is `{latency}ms`.")

@bot.tree.command(name="coinflip", description="Flip a coin")
async def coinflip(interaction: discord.Interaction):
    result = random.choice(["Heads", "Tails"])
    await interaction.response.send_message(f"🪙 The coin landed on: **{result}**!")

@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 {member.mention} was kicked. Reason: `{reason}`")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I do not have permission to kick this member.", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 {member.mention} was banned. Reason: `{reason}`")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I do not have permission to ban this member.", ephemeral=True)

@bot.tree.command(name="avatar", description="Get a user's avatar")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"{member.name}'s Avatar", color=0x00ff00)
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="roll", description="Roll a custom sided dice")
async def roll(interaction: discord.Interaction, sides: int = 6):
    if sides < 2:
        return await interaction.response.send_message("❌ A dice needs at least 2 sides!")
    result = random.randint(1, sides)
    await interaction.response.send_message(f"🎲 You rolled a **{result}** (1-{sides})!")

@bot.tree.command(name="rps", description="Play Rock, Paper, Scissors")
@app_commands.choices(choice=[
    app_commands.Choice(name="Rock", value="rock"),
    app_commands.Choice(name="Paper", value="paper"),
    app_commands.Choice(name="Scissors", value="scissors")
])
async def rps(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    bot_choice = random.choice(["rock", "paper", "scissors"])
    user_choice = choice.value
    
    if user_choice == bot_choice:
        result = "It's a tie!"
    elif (user_choice == "rock" and bot_choice == "scissors") or \
         (user_choice == "paper" and bot_choice == "rock") or \
         (user_choice == "scissors" and bot_choice == "paper"):
        result = "You win! 🎉"
    else:
        result = "I win! 🤖"
        
    await interaction.response.send_message(f"You chose **{user_choice.title()}**, I chose **{bot_choice.title()}**. {result}")

@bot.tree.command(name="timeout", description="Timeout a member temporarily")
@app_commands.default_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
    try:
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"⏱️ {member.mention} has been timed out for {minutes} minutes. Reason: `{reason}`")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I do not have permission to timeout this member. Ensure my role is higher than theirs.", ephemeral=True)


# ===================== PREFIX COMMANDS (. / !) =====================

@bot.command(name="genmcfa")
@commands.has_permissions(administrator=True)
async def genmcfa(ctx, amount: int = 1):
    if amount <= 0:
        return await ctx.send("❌ Amount must be at least 1.")
        
    file_path = "mcfa.txt"
    
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write("")

    with open(file_path, "r") as f:
        lines = [line for line in f.readlines() if line.strip()]

    if len(lines) < amount:
        return await ctx.send(f"❌ **Not enough stock!** Requested: {amount}, Available: {len(lines)}. Use `.stock` to view current supply.")

    # Pop the requested amount of accounts
    accounts_to_send = [lines.pop(0).strip() for _ in range(amount)]

    with open(file_path, "w") as f:
        f.writelines([line + "\n" for line in lines])

    try:
        if amount == 1:
            embed = discord.Embed(
                title="🎮 Your MCFA Account", 
                description=f"`{accounts_to_send[0]}`\n\n*Please ensure you secure the account.*", 
                color=0x00ff00
            )
            await ctx.author.send(embed=embed)
        else:
            accounts_string = "\n".join(accounts_to_send)
            file_obj = io.BytesIO(accounts_string.encode('utf-8'))
            discord_file = discord.File(file_obj, filename="mcfa_accounts.txt")
            
            embed = discord.Embed(
                title="🎮 Your MCFA Accounts", 
                description=f"Your **{amount}** requested MCFA accounts are attached to this message.", 
                color=0x00ff00
            )
            await ctx.author.send(embed=embed, file=discord_file)
            
        await ctx.send(f"✅ {ctx.author.mention}, successfully generated! Check your Direct Messages.")
    except discord.Forbidden:
        # Put accounts back in stock if DMs fail
        lines = [acc + "\n" for acc in accounts_to_send] + lines
        with open(file_path, "w") as f:
            f.writelines(lines)
        await ctx.send(f"❌ {ctx.author.mention}, I couldn't send you a DM! Please enable Direct Messages from server members and try again.")

@bot.command(name="genrandommcfa")
@commands.has_permissions(administrator=True)
async def genrandommcfa(ctx):
    """Generates a random formatted MCFA without needing the text file."""
    domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
    email = f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}@{random.choice(domains)}"
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    try:
        embed = discord.Embed(
            title="🎮 Randomly Generated MCFA", 
            description=f"`{email}:{password}`\n\n*Note: This is a randomly generated format without a text file stock.*", 
            color=0x00ff00
        )
        await ctx.author.send(embed=embed)
        await ctx.send(f"✅ {ctx.author.mention}, successfully generated a random fake account! Check your DMs.")
    except discord.Forbidden:
        await ctx.send(f"❌ {ctx.author.mention}, DMs are disabled!")

@bot.command(name="setautonitro")
@commands.has_permissions(administrator=True)
async def setautonitro(ctx, channel: discord.TextChannel = None):
    if channel is None:
        data["nitro_gen_channel"] = None
        save_data()
        await ctx.send("🛑 Auto Nitro Generator **disabled**.")
    else:
        data["nitro_gen_channel"] = channel.id
        save_data()
        await ctx.send(f"✅ Auto Nitro Generator set to {channel.mention} (Generates codes 24/7 every 20 seconds).")

@bot.command(name="stock")
async def stock(ctx):
    file_path = "mcfa.txt"
    stock_count = 0
    
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            stock_count = len([line for line in f.readlines() if line.strip()])
    
    embed_color = 0x00ff00 if stock_count > 0 else 0xff0000
    embed = discord.Embed(title="📦 Generator Stock", color=embed_color)
    embed.add_field(name="Minecraft Full Access (MCFA)", value=f"**{stock_count}** accounts available", inline=False)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    
    await ctx.send(embed=embed)

@bot.command(name="addmcfa", aliases=["addstock"])
@commands.has_permissions(administrator=True)
async def addmcfa(ctx, *, accounts: str):
    file_path = "mcfa.txt"
    # Splits by lines or spaces to allow bulk adding
    new_accounts = accounts.split()
    
    with open(file_path, "a") as f:
        for acc in new_accounts:
            if acc.strip():
                f.write(acc.strip() + "\n")
                
    await ctx.send(f"✅ Successfully added **{len(new_accounts)}** accounts to the stock!")

@bot.command(name="pay")
@commands.has_permissions(administrator=True)
async def pay_prefix(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        return await ctx.send("❌ Amount must be greater than 0.")
    
    sender = get_balance(ctx.author.id)
    if sender["balance"] < amount:
        return await ctx.send("❌ You don't have enough coins!")
        
    receiver = get_balance(member.id)
    sender["balance"] -= amount
    receiver["balance"] += amount
    
    save_balance(ctx.author.id, sender)
    save_balance(member.id, receiver)
    await ctx.send(f"💸 You successfully paid **{amount}** coins to {member.mention}!")

@bot.command(name="nitrochecker", aliases=["checknitro"])
@commands.has_permissions(administrator=True)
async def nitrochecker(ctx, code: str):
    clean_code = code.replace("https://discord.gift/", "").replace("discord.gift/", "").replace("http://discord.gift/", "").strip()
    url = f"https://discordapp.com/api/v9/entitlements/gift-codes/{clean_code}?with_application=false&with_subscription_plan=true"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                plan_name = data.get("subscription_plan", {}).get("name", "Nitro")
                await ctx.send(f"✅ **Valid Code!**\n**Plan:** {plan_name}\n**Code:** `{clean_code}`")
            elif resp.status == 429:
                await ctx.send("⚠️ **Rate Limited!** Discord's API is blocking the requests. Please try again later.")
            else:
                await ctx.send(f"❌ **Invalid or Claimed Code:** `{clean_code}`")


# ===================== EVENTS =====================
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    try:
        await bot.tree.sync()
        print("✅ Slash commands synced")
    except Exception as e:
        print(f"Sync error: {e}")

    await bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.watching, name="Servers"))
    check_youtube.start()
    check_tiktok.start()
    auto_nitro_gen.start()

# Start the keep_alive server before running the bot
keep_alive()
bot.run(TOKEN)
