import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from flask import Flask, request, session, render_template_string, redirect, url_for
from threading import Thread
import os
import json
import time

# =========================
# LOAD ENV & CONFIGURATION
# =========================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
START_TIME = time.time()

PRODUCTS = {
    "mcfa": {"name": "MCFA Account", "type": "digital", "price": 5},
    "nitro": {"name": "Discord Nitro", "type": "gift", "price": 10},
    "minecraft": {"name": "Minecraft Account", "type": "game", "price": 7},
    "custom": {"name": "Custom Service", "type": "service", "price": 3}
}

# =========================
# DATA STORAGE & JSON HELPERS
# =========================
def load_data(file_name, default_data):
    if os.path.exists(file_name):
        with open(file_name, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default_data
    return default_data

def save_data(file_name, data):
    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)

ORDERS = load_data("orders.json", [])
ACCOUNTS = load_data("accounts.json", {})
WHITELISTED_IDS = load_data("whitelist.json", [])
ECONOMY = load_data("economy.json", {})
DAILY_COOLDOWNS = load_data("cooldowns.json", {})

# =========================
# PERMISSION SYSTEM
# =========================
OWNER_IDS = [1192047136192352256]

def is_owner(user_id):
    return user_id in OWNER_IDS

def is_whitelisted(user_id):
    return user_id in OWNER_IDS or user_id in WHITELISTED_IDS

# =========================
# WEBSITE (FLASK APP)
# =========================
app = Flask(__name__)
app.secret_key = "super_secret_key_change_this_in_production"

BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Store Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white flex flex-col min-h-screen">
    <nav class="bg-gray-800 p-4 shadow-lg">
        <div class="container mx-auto flex justify-between">
            <a href="/" class="text-xl font-bold text-blue-400">BotStore</a>
            <div>
                {% if 'username' in session %}
                    <a href="/dashboard" class="mr-4 hover:text-blue-300">Dashboard</a>
                    <a href="/logout" class="bg-red-600 px-4 py-2 rounded hover:bg-red-500 transition">Logout</a>
                {% else %}
                    <a href="/login" class="bg-blue-600 px-4 py-2 rounded hover:bg-blue-500 transition">Login</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <main class="container mx-auto mt-10 p-4 flex-grow">
        {% block content %}{% endblock %}
    </main>
    <footer class="bg-gray-800 text-center p-4 mt-auto">
        <p class="text-gray-400">© 2026 StoreBot Inc.</p>
    </footer>
</body>
</html>
"""

HOME_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="text-center">
    <h1 class="text-4xl font-bold mb-4">Welcome to our Store!</h1>
    <p class="text-gray-400 mb-8">Login to manage your account. Accounts are invite-only via Discord.</p>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {% for key, product in products.items() %}
        <div class="bg-gray-800 p-6 rounded-lg shadow border border-gray-700 hover:border-blue-500 transition">
            <h2 class="text-2xl font-bold text-blue-400 mb-2">{{ product.name }}</h2>
            <p class="text-gray-300 mb-4">Type: {{ product.type|title }}</p>
            <p class="text-xl font-semibold">${{ product.price }}</p>
        </div>
        {% endfor %}
    </div>
</div>
""")

LOGIN_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="max-w-md mx-auto bg-gray-800 p-8 rounded-lg shadow-lg border border-gray-700">
    <h1 class="text-3xl font-bold mb-6 text-center">Account Login</h1>
    {% if error %}
        <p class="bg-red-600 text-white p-3 rounded mb-4">{{ error }}</p>
    {% endif %}
    <form method="POST" action="/login">
        <div class="mb-4">
            <label class="block text-gray-400 mb-2">Username</label>
            <input type="text" name="username" class="w-full p-3 rounded bg-gray-700 border border-gray-600 text-white focus:outline-none focus:border-blue-500" required>
        </div>
        <div class="mb-6">
            <label class="block text-gray-400 mb-2">Password</label>
            <input type="password" name="password" class="w-full p-3 rounded bg-gray-700 border border-gray-600 text-white focus:outline-none focus:border-blue-500" required>
        </div>
        <button type="submit" class="w-full bg-blue-600 text-white font-bold py-3 rounded hover:bg-blue-500 transition">Login</button>
    </form>
</div>
""")

DASHBOARD_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
    <div class="md:col-span-1 bg-gray-800 p-6 rounded-lg shadow border border-gray-700">
        <h1 class="text-2xl font-bold mb-2">Welcome, <span class="text-blue-400">{{ session['username'] }}</span>!</h1>
        <hr class="border-gray-600 my-4">
        <p class="text-gray-300 text-lg">💰 Balance: <strong class="text-green-400">{{ balance }} Coins</strong></p>
    </div>
    
    <div class="md:col-span-2 bg-gray-800 p-6 rounded-lg shadow border border-gray-700">
        <h2 class="text-2xl font-bold mb-4 text-blue-400">Your Active Orders</h2>
        {% if user_orders %}
            <div class="overflow-x-auto">
                <table class="w-full text-left">
                    <thead>
                        <tr class="bg-gray-700 text-gray-300">
                            <th class="p-3 rounded-tl-lg">Product</th>
                            <th class="p-3">Price</th>
                            <th class="p-3">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for order in user_orders %}
                        <tr class="border-b border-gray-700">
                            <td class="p-3">📦 {{ order.product_name }}</td>
                            <td class="p-3">${{ order.price }}</td>
                            <td class="p-3">
                                <span class="px-2 py-1 rounded text-sm {% if order.status == 'pending' %}bg-yellow-600{% else %}bg-green-600{% endif %}">
                                    {{ order.status|title }}
                                </span>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% else %}
            <p class="text-gray-400 bg-gray-700 p-4 rounded text-center">You have no active orders. Order something in Discord!</p>
        {% endif %}
    </div>
</div>
""")

@app.route('/')
def home():
    return render_template_string(HOME_HTML, products=PRODUCTS)

@app.route('/login', methods=['GET', 'POST'])
def login_route():
    if 'username' in session: return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        global ACCOUNTS
        ACCOUNTS = load_data("accounts.json", {})
        
        if user in ACCOUNTS and isinstance(ACCOUNTS[user], dict) and ACCOUNTS[user].get("password") == pw:
            session['username'] = user
            session['discord_id'] = ACCOUNTS[user].get("discord_id")
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid username or password."
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session: return redirect(url_for('login_route'))
    
    discord_id = session.get('discord_id')
    global ORDERS, ECONOMY
    ORDERS = load_data("orders.json", [])
    ECONOMY = load_data("economy.json", {})
    
    user_orders = [o for o in ORDERS if o.get('user_id') == discord_id]
    balance = ECONOMY.get(str(discord_id), 0)
    
    return render_template_string(DASHBOARD_HTML, user_orders=user_orders, balance=balance)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.watching, name="Managing Servers"))
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Sync Error: {e}")

# ========================================================================
# PREFIX COMMANDS ($)
# ========================================================================

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="📚 Command List", color=discord.Color.blue())
    embed.add_field(name="🌐 Website & Accounts", value="`$signup`, `$login`, `$website`", inline=False)
    embed.add_field(name="📦 Store System", value="`$po`, `$orders`, `$clearorder`", inline=False)
    embed.add_field(name="💰 Economy System", value="`$bal`, `$daily`, `$addcoins`", inline=False)
    embed.add_field(name="🛠️ Support & Utils", value="`$ticket`, `$ping`, `$connect`, `$userinfo`, `$serverinfo`", inline=False)
    embed.add_field(name="🛡️ Admin", value="`$w`, `$uw`, `$status`, `$shutdown`, `$kick`, `$ban`, `$clear`", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def connect(ctx, target_guild_id: int, target_channel_id: int):
    if not is_owner(ctx.author.id): 
        return await ctx.send("❌ Only the bot owner can establish server connections.")
    
    target_guild = bot.get_guild(target_guild_id)
    if not target_guild:
        return await ctx.send("❌ Connection failed: I am not in that server. Invite me there first!")
    
    target_channel = target_guild.get_channel(target_channel_id)
    if not target_channel:
        return await ctx.send(f"❌ Connection failed: Could not find that channel in **{target_guild.name}**.")
        
    try:
        await target_channel.send(f"🔗 **SYSTEM LINK:** Connection successfully established from **{ctx.guild.name}** by {ctx.author.mention}.")
        await ctx.send(f"✅ Secure cross-server connection established with **{target_guild.name}**!")
    except discord.Forbidden:
        await ctx.send("❌ Connection failed: I don't have permission to write in that remote channel.")

@bot.command()
async def ticket(ctx, *, reason: str = "General Support"):
    thread = await ctx.message.create_thread(name=f"🎫-ticket-{ctx.author.name}", auto_archive_duration=60)
    await thread.send(f"Hello {ctx.author.mention}, support will be with you shortly!\n**Reason:** {reason}")
    await ctx.send(f"✅ Ticket created: {thread.mention}")

@bot.command()
async def bal(ctx):
    user_id = str(ctx.author.id)
    balance = ECONOMY.get(user_id, 0)
    await ctx.send(f"💰 {ctx.author.name}, you have **{balance}** coins!")

@bot.command()
async def daily(ctx):
    user_id = str(ctx.author.id)
    now = time.time()
    last_claim = DAILY_COOLDOWNS.get(user_id, 0)

    if now - last_claim < 86400:
        hours_left = round((86400 - (now - last_claim)) / 3600, 1)
        return await ctx.send(f"⏳ You need to wait {hours_left} hours to claim your daily coins!")

    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + 100
    DAILY_COOLDOWNS[user_id] = now
    save_data("economy.json", ECONOMY)
    save_data("cooldowns.json", DAILY_COOLDOWNS)
    await ctx.send("✅ You claimed your daily **100 coins**!")

@bot.command()
async def addcoins(ctx, member: discord.Member, amount: int):
    if not is_whitelisted(ctx.author.id): return await ctx.send("❌ Whitelisted only")
    user_id = str(member.id)
    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + amount
    save_data("economy.json", ECONOMY)
    await ctx.send(f"✅ Added {amount} coins to {member.name}'s balance!")

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)}ms")

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member}", color=discord.Color.blurple())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined", value=str(member.joined_at.date()))
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=guild.name, color=discord.Color.green())
    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Owner", value=str(guild.owner))
    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 **{member}** was kicked. Reason: {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 **{member}** was banned. Reason: {reason}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"✅ Cleared {amount} messages")
    await msg.delete(delay=3)

@bot.command()
async def w(ctx, user: discord.User):
    if not is_owner(ctx.author.id): return await ctx.send("❌ Owner only")
    if user.id not in WHITELISTED_IDS:
        WHITELISTED_IDS.append(user.id); save_data("whitelist.json", WHITELISTED_IDS)
    await ctx.send(f"✅ Added {user.mention} to whitelist")

@bot.command()
async def uw(ctx, user: discord.User):
    if not is_owner(ctx.author.id): return await ctx.send("❌ Owner only")
    if user.id in WHITELISTED_IDS:
        WHITELISTED_IDS.remove(user.id); save_data("whitelist.json", WHITELISTED_IDS)
    await ctx.send(f"🗑️ Removed {user.mention} from whitelist")

@bot.command()
async def sync(ctx):
    if not is_whitelisted(ctx.author.id): return await ctx.send("❌ Whitelisted only")
    synced = await bot.tree.sync()
    await ctx.send(f"✅ Synced {len(synced)} slash commands")

@bot.command()
async def status(ctx):
    uptime_seconds = int(time.time() - START_TIME)
    embed = discord.Embed(title="🤖 Bot Status", color=discord.Color.blue())
    embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms")
    embed.add_field(name="Uptime", value=f"{uptime_seconds} seconds")
    embed.add_field(name="Servers", value=f"{len(bot.guilds)}")
    await ctx.send(embed=embed)

@bot.command()
async def shutdown(ctx):
    if not is_owner(ctx.author.id): return await ctx.send("❌ Owner only")
    await ctx.send("🛑 Shutting down...")
    await bot.close()

@bot.command()
async def po(ctx, product: str, email: str = "none", image: str = None):
    product = product.lower()
    if product not in PRODUCTS: return await ctx.send(f"❌ Invalid product. Available: {', '.join(PRODUCTS.keys())}")
    
    item = PRODUCTS[product]
    ORDERS.append({"user_id": ctx.author.id, "product": product, "product_name": item["name"], "price": item["price"], "email": email, "image": image, "status": "pending"})
    save_data("orders.json", ORDERS)
    await ctx.send(f"✅ Order placed!\n📦 {item['name']}\n💰 Price: ${item['price']}\n📩 Email: {email}")

@bot.command()
async def orders(ctx):
    if not is_whitelisted(ctx.author.id): return await ctx.send("❌ Whitelisted only")
    if not ORDERS: return await ctx.send("No pending orders.")
    msg = "**📦 ORDER LIST**\n\n"
    for i, o in enumerate(ORDERS, 1):
        msg += f"#{i} | 📦 {o['product_name']} | 💰 ${o['price']} | 📩 {o['email']} | 📊 {o['status']}\n"
    await ctx.send(msg[:2000])

@bot.command()
async def clearorder(ctx, target: str):
    if not is_whitelisted(ctx.author.id): return await ctx.send("❌ Whitelisted only")
    global ORDERS
    if target.lower() == "all":
        ORDERS = []; save_data("orders.json", ORDERS)
        return await ctx.send("✅ All orders cleared")
    if target.lower() in PRODUCTS:
        ORDERS = [o for o in ORDERS if o["product"] != target.lower()]
        save_data("orders.json", ORDERS); return await ctx.send(f"✅ Cleared all {target} orders")
    try:
        ORDERS = [o for o in ORDERS if o["user_id"] != int(target)]; save_data("orders.json", ORDERS)
        await ctx.send("✅ User orders cleared")
    except ValueError:
        await ctx.send("❌ Invalid target")

@bot.command()
async def signup(ctx, username: str, password: str, target_user: discord.Member = None):
    try: await ctx.message.delete()
    except: pass 
    if not is_whitelisted(ctx.author.id): return await ctx.send("❌ Whitelisted only")
    
    target = target_user or ctx.author 
    global ACCOUNTS
    ACCOUNTS = load_data("accounts.json", {})
    if username in ACCOUNTS: return await ctx.send("❌ Username already exists.")
    
    ACCOUNTS[username] = {"password": password, "discord_id": target.id}
    save_data("accounts.json", ACCOUNTS)
    await ctx.send(f"✅ Web account `{username}` successfully created and linked to {target.mention}.")

@bot.command()
async def login(ctx, username: str, password: str):
    try: await ctx.message.delete()
    except: pass 
    global ACCOUNTS
    ACCOUNTS = load_data("accounts.json", {})
    if username not in ACCOUNTS: return await ctx.send("❌ Account not found.")
    
    if isinstance(ACCOUNTS[username], dict) and ACCOUNTS[username]["password"] == password:
        await ctx.send(f"✅ Successfully logged in as `{username}` in Discord!")
    else: await ctx.send("❌ Incorrect password.")

@bot.command()
async def website(ctx):
    embed = discord.Embed(
        title="🌐 Official Website",
        description="Visit our website to view your balance, dashboard, and orders!\n\n🔗 **[Click here to visit our site](http://127.0.0.1:8080)**",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Note: URL depends on your hosting platform!")
    await ctx.send(embed=embed)


# ========================================================================
# SLASH COMMANDS (/)
# ========================================================================

@bot.tree.command(name="help", description="Show all commands")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(title="📚 Command List", color=discord.Color.blue())
    embed.add_field(name="🌐 Website & Accounts", value="`/signup`, `/login`, `/website`", inline=False)
    embed.add_field(name="📦 Store System", value="`/po`, `/orders`, `/clearorder`", inline=False)
    embed.add_field(name="💰 Economy System", value="`/bal`, `/daily`, `/addcoins`", inline=False)
    embed.add_field(name="🛠️ Support & Utils", value="`/ticket`, `/ping`, `/connect`, `/userinfo`, `/serverinfo`", inline=False)
    embed.add_field(name="🛡️ Admin", value="`/whitelist`, `/unwhitelist`, `/status`, `/shutdown`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="connect", description="Securely test a connection to a remote server channel")
async def slash_connect(interaction: discord.Interaction, target_guild_id: str, target_channel_id: str):
    if not is_owner(interaction.user.id): 
        return await interaction.response.send_message("❌ Only the bot owner can configure links.", ephemeral=True)
    
    try:
        g_id = int(target_guild_id)
        c_id = int(target_channel_id)
    except ValueError:
        return await interaction.response.send_message("❌ Guild and Channel IDs must be numeric digits.", ephemeral=True)

    target_guild = bot.get_guild(g_id)
    if not target_guild:
        return await interaction.response.send_message("❌ Connection failed: Bot is not a member of that guild.", ephemeral=True)
        
    target_channel = target_guild.get_channel(c_id)
    if not target_channel:
        return await interaction.response.send_message(f"❌ Connection failed: Channel not found in **{target_guild.name}**.", ephemeral=True)
        
    try:
        await target_channel.send(f"🔗 **SYSTEM LINK:** Connected securely from slash command by {interaction.user.mention}.")
        await interaction.response.send_message(f"✅ Handshake message sent successfully to **{target_guild.name}**!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Missing permissions to type in that remote channel.", ephemeral=True)

@bot.tree.command(name="ticket", description="Open a support ticket")
async def slash_ticket(interaction: discord.Interaction, reason: str = "General Support"):
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("❌ Tickets can only be made in text channels.", ephemeral=True)
    
    await interaction.response.send_message("🎫 Creating your ticket...", ephemeral=True)
    thread = await interaction.channel.create_thread(
        name=f"🎫-ticket-{interaction.user.name}",
        type=discord.ChannelType.public_thread,
        auto_archive_duration=60
    )
    await thread.send(f"Hello {interaction.user.mention}, support will be with you shortly!\n**Reason:** {reason}")

@bot.tree.command(name="bal", description="Check your coin balance")
async def slash_bal(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    balance = ECONOMY.get(user_id, 0)
    await interaction.response.send_message(f"💰 You have **{balance}** coins!", ephemeral=True)

@bot.tree.command(name="daily", description="Claim your daily coins")
async def slash_daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = time.time()
    last_claim = DAILY_COOLDOWNS.get(user_id, 0)

    if now - last_claim < 86400:
        hours_left = round((86400 - (now - last_claim)) / 3600, 1)
        return await interaction.response.send_message(f"⏳ Wait {hours_left} hours to claim again!", ephemeral=True)

    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + 100
    DAILY_COOLDOWNS[user_id] = now
    save_data("economy.json", ECONOMY)
    save_data("cooldowns.json", DAILY_COOLDOWNS)
    await interaction.response.send_message("✅ You claimed your daily **100 coins**!", ephemeral=True)

@bot.tree.command(name="addcoins", description="Add coins to a user")
async def slash_addcoins(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not is_whitelisted(interaction.user.id): return await interaction.response.send_message("❌ Whitelisted only", ephemeral=True)
    user_id = str(member.id)
    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + amount
    save_data("economy.json", ECONOMY)
    await interaction.response.send_message(f"✅ Added {amount} coins to {member.name}'s balance!", ephemeral=True)

@bot.tree.command(name="ping", description="Shows bot latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)}ms")

@bot.tree.command(name="userinfo", description="Show user info")
async def slash_userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"{member}", color=discord.Color.blurple())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined", value=str(member.joined_at.date()))
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Show server info")
async def slash_serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=guild.name, color=discord.Color.green())
    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Owner", value=str(guild.owner))
    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="kick", description="Kick a member")
@app_commands.checks.has_permissions(kick_members=True)
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 **{member}** was kicked. Reason: {reason}")

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.checks.has_permissions(ban_members=True)
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 **{member}** was banned. Reason: {reason}")

@bot.tree.command(name="clear", description="Clear messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_clear(interaction: discord.Interaction, amount: int):
    await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"✅ Cleared {amount} messages", ephemeral=True)

@bot.tree.command(name="whitelist", description="Add a user to the whitelist")
async def slash_whitelist(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction.user.id): return await interaction.response.send_message("❌ Owner only", ephemeral=True)
    if user.id not in WHITELISTED_IDS:
        WHITELISTED_IDS.append(user.id); save_data("whitelist.json", WHITELISTED_IDS)
    await interaction.response.send_message(f"✅ Added {user.mention} to whitelist", ephemeral=True)

@bot.tree.command(name="unwhitelist", description="Remove a user from the whitelist")
async def slash_unwhitelist(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction.user.id): return await interaction.response.send_message("❌ Owner only", ephemeral=True)
    if user.id in WHITELISTED_IDS:
        WHITELISTED_IDS.remove(user.id); save_data("whitelist.json", WHITELISTED_IDS)
    await interaction.response.send_message(f"🗑️ Removed {user.mention} from whitelist", ephemeral=True)

@bot.tree.command(name="sync", description="Sync slash commands")
async def slash_sync(interaction: discord.Interaction):
    if not is_whitelisted(interaction.user.id): return await interaction.response.send_message("❌ Whitelisted only", ephemeral=True)
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"✅ Synced {len(synced)} slash commands", ephemeral=True)

@bot.tree.command(name="status", description="Check bot status and uptime")
async def slash_status(interaction: discord.Interaction):
    uptime_seconds = int(time.time() - START_TIME)
    embed = discord.Embed(title="🤖 Bot Status", color=discord.Color.blue())
    embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms")
    embed.add_field(name="Uptime", value=f"{uptime_seconds} seconds")
    embed.add_field(name="Servers", value=f"{len(bot.guilds)}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="shutdown", description="Shut down the bot")
async def slash_shutdown(interaction: discord.Interaction):
    if not is_owner(interaction.user.id): return await interaction.response.send_message("❌ Owner only", ephemeral=True)
    await interaction.response.send_message("🛑 Shutting down...", ephemeral=True)
    await bot.close()

@bot.tree.command(name="po", description="Place a product order")
async def slash_po(interaction: discord.Interaction, product: str, email: str = "none", image: str = None):
    product = product.lower()
    if product not in PRODUCTS: return await interaction.response.send_message(f"❌ Invalid product: {list(PRODUCTS.keys())}", ephemeral=True)
    item = PRODUCTS[product]
    ORDERS.append({"user_id": interaction.user.id, "product": product, "product_name": item["name"], "price": item["price"], "email": email, "image": image, "status": "pending"})
    save_data("orders.json", ORDERS)
    await interaction.response.send_message(f"✅ Order placed: {item['name']} (${item['price']})", ephemeral=True)

@bot.tree.command(name="orders", description="View all orders")
async def slash_orders(interaction: discord.Interaction):
    if not is_whitelisted(interaction.user.id): return await interaction.response.send_message("❌ Whitelisted only", ephemeral=True)
    if not ORDERS: return await interaction.response.send_message("No pending orders.", ephemeral=True)
    msg = "**📦 ORDER LIST**\n\n"
    for i, o in enumerate(ORDERS, 1):
        msg += f"#{i} | 📦 {o['product_name']} | 💰 ${o['price']} | 📩 {o['email']} | 📊 {o['status']}\n"
    await interaction.response.send_message(msg[:2000], ephemeral=True)

@bot.tree.command(name="clearorder", description="Clear orders by target")
async def slash_clearorder(interaction: discord.Interaction, target: str):
    if not is_whitelisted(interaction.user.id): return await interaction.response.send_message("❌ Whitelisted only", ephemeral=True)
    global ORDERS
    if target.lower() == "all":
        ORDERS = []; save_data("orders.json", ORDERS)
        return await interaction.response.send_message("✅ All orders cleared", ephemeral=True)
    if target.lower() in PRODUCTS:
        ORDERS = [o for o in ORDERS if o["product"] != target.lower()]
        save_data("orders.json", ORDERS); return await interaction.response.send_message(f"✅ Cleared all {target} orders", ephemeral=True)
    try:
        ORDERS = [o for o in ORDERS if o["user_id"] != int(target)]; save_data("orders.json", ORDERS)
        await interaction.response.send_message("✅ User orders cleared", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("❌ Invalid target", ephemeral=True)

@bot.tree.command(name="signup", description="Create a new website account")
async def slash_signup(interaction: discord.Interaction, username: str, password: str, target_user: discord.Member = None):
    if not is_whitelisted(interaction.user.id): return await interaction.response.send_message("❌ Whitelisted only", ephemeral=True)
    
    target = target_user or interaction.user
    global ACCOUNTS
    ACCOUNTS = load_data("accounts.json", {})
    if username in ACCOUNTS: return await interaction.response.send_message("❌ Username already exists.", ephemeral=True)
    
    ACCOUNTS[username] = {"password": password, "discord_id": target.id}
    save_data("accounts.json", ACCOUNTS)
    await interaction.response.send_message(f"✅ Account `{username}` linked to {target.mention} successfully created.", ephemeral=True)

@bot.tree.command(name="login", description="Login to your website account via Discord")
async def slash_login(interaction: discord.Interaction, username: str, password: str):
    global ACCOUNTS
    ACCOUNTS = load_data("accounts.json", {})
    if username not in ACCOUNTS: return await interaction.response.send_message("❌ Account not found.", ephemeral=True)
    
    if isinstance(ACCOUNTS[username], dict) and ACCOUNTS[username]["password"] == password: 
        await interaction.response.send_message(f"✅ Successfully logged in as `{username}`!", ephemeral=True)
    else: await interaction.response.send_message("❌ Incorrect password.", ephemeral=True)

@bot.tree.command(name="website", description="Get the link to our official website")
async def slash_website(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌐 Official Website",
        description="Visit our website to view your balance, dashboard, and orders!\n\n🔗 **[Click here to visit our site](http://127.0.0.1:8080)**",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Note: URL depends on your hosting platform!")
    await interaction.response.send_message(embed=embed)

# =========================
# START BOT & SERVER
# =========================
if __name__ == "__main__":
    keep_alive()
    if TOKEN is None:
        print("❌ DISCORD_TOKEN not found in .env file.")
    else:
        bot.run(TOKEN)
