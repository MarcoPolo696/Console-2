import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os
import json
import time
import random
import string

# =========================
# LOAD ENV & CONFIGURATION
# =========================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
START_TIME = time.time()

# Products & Ranks priced in Powoncy (₱)
PRODUCTS = {
    "vip": {"name": "VIP Rank", "type": "rank", "price": 100},
    "mvp": {"name": "MVP Rank", "type": "rank", "price": 250},
    "legend": {"name": "Legend Rank", "type": "rank", "price": 500},
    "nitro": {"name": "Discord Nitro", "type": "gift", "price": 300},
    "mcfa": {"name": "MCFA Account", "type": "digital", "price": 150}
}

# =========================
# DATA STORAGE & JSON HELPERS
# =========================
def load_data(file_name, default_data):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default_data
    return default_data

def save_data(file_name, data):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

ORDERS = load_data("orders.json", [])
WHITELIST_DATA = load_data("whitelist.json", {"users": [], "servers": []})
# Migration check in case old whitelist.json was a flat list
if isinstance(WHITELIST_DATA, list):
    WHITELIST_DATA = {"users": WHITELIST_DATA, "servers": []}

ECONOMY = load_data("economy.json", {})
DAILY_COOLDOWNS = load_data("cooldowns.json", {})
CODES = load_data("codes.json", {})

# =========================
# PERMISSION SYSTEM
# =========================
OWNER_IDS = [1192047136192352256, 1334881324414271602, 1515362345705148491]

def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS

def is_whitelisted(user_id: int, guild_id: int = None) -> bool:
    if is_owner(user_id):
        return True
    if user_id in WHITELIST_DATA.get("users", []):
        return True
    if guild_id and guild_id in WHITELIST_DATA.get("servers", []):
        return True
    return False

def can_gencode(ctx) -> bool:
    if is_owner(ctx.author.id): 
        return True
    if ctx.guild and ctx.guild.id in WHITELIST_DATA.get("servers", []):
        if ctx.author.guild_permissions.administrator:
            return True
    return False

# =========================
# INTERACTIVE VIEWS
# =========================
class BlackjackView(discord.ui.View):
    def __init__(self, user_id, bet):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet = bet
        self.player_total = random.randint(12, 20)
        self.dealer_total = random.randint(14, 21)

    async def update_economy(self, won: bool):
        uid = str(self.user_id)
        if won:
            ECONOMY[uid] += self.bet * 2
        save_data("economy.json", ECONOMY)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, custom_id="bj_hit")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your game!", ephemeral=True)
        
        self.player_total += random.randint(2, 10)
        
        if self.player_total > 21:
            for child in self.children: child.disabled = True
            await interaction.response.edit_message(
                content=f"🃏 **Blackjack**\nYou hit and got **{self.player_total}**. BUST! You lost **₱{self.bet}**.",
                view=self
            )
        else:
            await interaction.response.edit_message(
                content=f"🃏 **Blackjack**\nYou hit! Your total is now **{self.player_total}**. Dealer is showing **{self.dealer_total - random.randint(2,6)}**.\nWhat will you do?",
                view=self
            )

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, custom_id="bj_stand")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your game!", ephemeral=True)
        
        for child in self.children: child.disabled = True
        
        # Dealer simple logic
        while self.dealer_total < 17:
            self.dealer_total += random.randint(2, 8)
            
        if self.dealer_total > 21 or self.player_total > self.dealer_total:
            await self.update_economy(True)
            msg = f"🃏 **Blackjack - You Won!** 🎉\nYou stood at **{self.player_total}**. Dealer got **{self.dealer_total}**.\nYou won **₱{self.bet * 2}**!"
        elif self.player_total == self.dealer_total:
            ECONOMY[str(self.user_id)] += self.bet # Refund
            save_data("economy.json", ECONOMY)
            msg = f"🃏 **Blackjack - Push (Tie)**\nYou and the dealer both got **{self.player_total}**. Your bet of **₱{self.bet}** was refunded."
        else:
            msg = f"🃏 **Blackjack - You Lost!**\nYou stood at **{self.player_total}**. Dealer got **{self.dealer_total}**.\nYou lost **₱{self.bet}**."

        await interaction.response.edit_message(content=msg, view=self)

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name="VacantMC | $help")
    )
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Sync Error: {e}")

# ========================================================================
# PREFIX COMMANDS ($)
# ========================================================================

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="✨ VacantMC Network Bot | Command Panel",
        description="Here is the list of available commands. Currency is set in Powoncy (₱).",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="🛒 Rank & Store System",
        value="`$po <product> [email]` - Order a product or rank\n"
              "`$claimrank <product>` - Claim/buy a rank directly using ₱\n"
              "`$orders` - View all active orders (Whitelisted)\n"
              "`$clearorder <all|product|user_id>` - Clear orders",
        inline=False
    )
    embed.add_field(
        name="💰 Economy & Games (Powoncy ₱)",
        value="`$bal` - Check your ₱ balance\n"
              "`$daily` - Claim your daily ₱ reward\n"
              "`$work` - Work for a random amount of ₱\n"
              "`$rob <user>` - Try to steal ₱ from someone\n"
              "`$cf <bet> <heads|tails>` - Coin flip\n"
              "`$bj <bet>` - Play Blackjack\n"
              "`$slots <bet>` - Spin the slot machine\n"
              "`$mines <bet> <mines_count>` - Play risk mines\n"
              "`$addcoins <user> <amount>` - Add ₱ to user (Whitelisted)",
        inline=False
    )
    embed.add_field(
        name="🎟️ Redeem Codes",
        value="`$redeem <code>` - Claim a generated code\n"
              "`$gencode <amount> <uses> [code]` - Gen code (Whitelisted Server Admins)",
        inline=False
    )
    embed.add_field(
        name="🛡️ Admin & Whitelist",
        value="`$whitelist <user|server_id>` - Whitelist a user or server\n"
              "`$unwhitelist <user|server_id>` - Unwhitelist a user/server\n"
              "`$presence <playing|watching|listening> <text>` - Update activity\n"
              "`$status` - Check bot status\n"
              "`$shutdown` - Turn off the bot (Owner)\n"
              "`$kick / $ban / $clear` - Moderation tools",
        inline=False
    )
    embed.set_footer(text="VacantMC System • Currency: ₱ (Powoncy)")
    await ctx.send(embed=embed)

# --- ECONOMY & GAMES ---

@bot.command(name="work")
async def work(ctx):
    user_id = str(ctx.author.id)
    earned = random.randint(20, 150)
    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + earned
    save_data("economy.json", ECONOMY)
    await ctx.send(f"💼 You worked hard and earned **₱{earned}** Powoncy!")

@bot.command(name="rob")
async def rob(ctx, target: discord.Member):
    user_id = str(ctx.author.id)
    target_id = str(target.id)
    
    if user_id == target_id: return await ctx.send("❌ You can't rob yourself!")
    
    user_bal = ECONOMY.get(user_id, 0)
    target_bal = ECONOMY.get(target_id, 0)
    
    if user_bal < 50: return await ctx.send("❌ You need at least ₱50 to attempt a robbery (as collateral).")
    if target_bal < 50: return await ctx.send("❌ They don't have enough Powoncy worth stealing!")
    
    success = random.choice([True, False])
    if success:
        stolen = int(target_bal * random.uniform(0.1, 0.3)) # Steal 10-30%
        ECONOMY[user_id] += stolen
        ECONOMY[target_id] -= stolen
        await ctx.send(f"🥷 **SUCCESS!** You robbed {target.mention} and got away with **₱{stolen}**!")
    else:
        fine = int(user_bal * random.uniform(0.1, 0.2)) # Lose 10-20%
        ECONOMY[user_id] -= fine
        await ctx.send(f"🚨 **CAUGHT!** You failed to rob {target.mention} and paid a fine of **₱{fine}**!")
    save_data("economy.json", ECONOMY)

@bot.command(name="cf", aliases=["coinflip"])
async def coinflip(ctx, bet: int, side: str):
    user_id = str(ctx.author.id)
    side = side.lower()
    if side not in ["heads", "tails", "h", "t"]: 
        return await ctx.send("❌ Choose `heads` or `tails`.")
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await ctx.send("❌ Invalid bet or insufficient funds.")
        
    ECONOMY[user_id] -= bet
    result = random.choice(["heads", "tails"])
    
    if side[0] == result[0]:
        winnings = bet * 2
        ECONOMY[user_id] += winnings
        await ctx.send(f"🪙 The coin landed on **{result.capitalize()}**! You won **₱{winnings}**!")
    else:
        await ctx.send(f"🪙 The coin landed on **{result.capitalize()}**. You lost your bet of **₱{bet}**.")
    save_data("economy.json", ECONOMY)

@bot.command(name="bj", aliases=["blackjack"])
async def blackjack(ctx, bet: int):
    user_id = str(ctx.author.id)
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await ctx.send("❌ Invalid bet or insufficient funds.")
    
    ECONOMY[user_id] -= bet
    save_data("economy.json", ECONOMY)
    
    view = BlackjackView(ctx.author.id, bet)
    await ctx.send(
        f"🃏 **Blackjack**\n{ctx.author.mention}, you drew a total of **{view.player_total}**.\nDealer is showing **{view.dealer_total - random.randint(2,6)}**.\nWhat will you do?", 
        view=view
    )

@bot.command(name="slots")
async def slots(ctx, bet: int):
    user_id = str(ctx.author.id)
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await ctx.send("❌ Invalid bet or insufficient funds.")
        
    ECONOMY[user_id] -= bet
    emojis = ["🍒", "🍋", "🔔", "💎", "🎰"]
    r1, r2, r3 = random.choice(emojis), random.choice(emojis), random.choice(emojis)
    
    if r1 == r2 == r3:
        win = bet * 5
        ECONOMY[user_id] += win
        msg = f"🎰 `[ {r1} | {r2} | {r3} ]` 🎰\n**JACKPOT!** You won **₱{win}**!"
    elif r1 == r2 or r2 == r3 or r1 == r3:
        win = bet * 2
        ECONOMY[user_id] += win
        msg = f"🎰 `[ {r1} | {r2} | {r3} ]` 🎰\nSmall win! You won **₱{win}**!"
    else:
        msg = f"🎰 `[ {r1} | {r2} | {r3} ]` 🎰\nYou lost **₱{bet}**."
        
    save_data("economy.json", ECONOMY)
    await ctx.send(msg)

@bot.command(name="mines")
async def mines(ctx, bet: int, mines_count: int):
    user_id = str(ctx.author.id)
    if not (1 <= mines_count <= 24):
        return await ctx.send("❌ Mines count must be between 1 and 24.")
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await ctx.send("❌ Invalid bet or insufficient funds.")
        
    ECONOMY[user_id] -= bet
    
    # Calculate probability of safely picking 3 tiles without hitting a mine
    safe_tiles = 25 - mines_count
    if safe_tiles < 3:
        win_chance = 0.05 # Very hard
    else:
        win_chance = (safe_tiles / 25) * ((safe_tiles - 1) / 24) * ((safe_tiles - 2) / 23)
        
    if random.random() <= win_chance:
        multiplier = round(25 / safe_tiles, 2)
        winnings = int(bet * multiplier)
        ECONOMY[user_id] += winnings
        await ctx.send(f"💣 **Mines Result**\nYou successfully navigated the minefield! Cashed out at **{multiplier}x** for **₱{winnings}**!")
    else:
        await ctx.send(f"💥 **BOOM!** You hit a mine and lost your bet of **₱{bet}**.")
    save_data("economy.json", ECONOMY)

# --- REDEEM CODE SYSTEM ---

@bot.command(name="gencode")
async def gencode(ctx, amount: int, uses: int = 1, custom_code: str = None):
    if not can_gencode(ctx):
        return await ctx.send("❌ You must be a bot owner or a server administrator in a whitelisted server.")
    if amount <= 0 or uses <= 0:
        return await ctx.send("❌ Amount and uses must be positive.")
        
    code = custom_code or ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    if code in CODES:
        return await ctx.send(f"❌ Code `{code}` already exists.")
        
    CODES[code] = {
        "amount": amount,
        "uses": uses,
        "used_by": []
    }
    save_data("codes.json", CODES)
    
    embed = discord.Embed(title="🎟️ Code Generated", color=discord.Color.green())
    embed.add_field(name="Code", value=f"`{code}`", inline=True)
    embed.add_field(name="Amount", value=f"₱{amount}", inline=True)
    embed.add_field(name="Uses Left", value=f"{uses}", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="redeem")
async def redeem(ctx, code: str):
    code = code.upper()
    user_id = ctx.author.id
    
    if code not in CODES:
        return await ctx.send("❌ Invalid or expired redeem code.")
        
    code_data = CODES[code]
    if user_id in code_data["used_by"]:
        return await ctx.send("❌ You have already claimed this code.")
        
    if code_data["uses"] <= 0:
        del CODES[code]
        save_data("codes.json", CODES)
        return await ctx.send("❌ This code has reached its maximum uses and expired.")
        
    # Apply rewards
    ECONOMY[str(user_id)] = ECONOMY.get(str(user_id), 0) + code_data["amount"]
    save_data("economy.json", ECONOMY)
    
    # Update code uses
    code_data["uses"] -= 1
    code_data["used_by"].append(user_id)
    if code_data["uses"] <= 0:
        del CODES[code]
    save_data("codes.json", CODES)
    
    await ctx.send(f"🎉 Successfully redeemed code! Added **₱{code_data['amount']}** to your balance.")

# --- STORE & SYSTEM COMMANDS ---

@bot.command(name="po")
async def po(ctx, product: str, email: str = "none", image: str = None):
    product_key = product.lower()
    if product_key not in PRODUCTS:
        available = ", ".join([f"`{k}`" for k in PRODUCTS.keys()])
        return await ctx.send(f"❌ Invalid product/rank. Available choices: {available}")
    
    item = PRODUCTS[product_key]
    order_entry = {
        "order_id": len(ORDERS) + 1,
        "user_id": ctx.author.id,
        "username": str(ctx.author),
        "product": product_key,
        "product_name": item["name"],
        "price": item["price"],
        "email": email,
        "image": image,
        "status": "pending"
    }
    ORDERS.append(order_entry)
    save_data("orders.json", ORDERS)
    
    embed = discord.Embed(title="📦 Order Placed Successfully", color=discord.Color.green())
    embed.add_field(name="Order ID", value=f"#{order_entry['order_id']}", inline=True)
    embed.add_field(name="Item", value=item["name"], inline=True)
    embed.add_field(name="Price", value=f"₱{item['price']}", inline=True)
    embed.add_field(name="Email/Note", value=email, inline=False)
    embed.set_footer(text="Use $claimrank <product> to pay instantly with ₱ balance!")
    await ctx.send(embed=embed)

@bot.command(name="claimrank")
async def claimrank(ctx, product: str):
    product_key = product.lower()
    if product_key not in PRODUCTS:
        available = ", ".join([f"`{k}`" for k in PRODUCTS.keys()])
        return await ctx.send(f"❌ Invalid rank/product. Choose from: {available}")
    
    item = PRODUCTS[product_key]
    user_id = str(ctx.author.id)
    user_balance = ECONOMY.get(user_id, 0)
    price = item["price"]
    
    if user_balance < price:
        return await ctx.send(f"❌ Insufficient ₱ balance! Required: **₱{price}**, Your Balance: **₱{user_balance}**.")
    
    ECONOMY[user_id] -= price
    save_data("economy.json", ECONOMY)
    
    # Mark active order as claimed/completed if exists
    for o in ORDERS:
        if o["user_id"] == ctx.author.id and o["product"] == product_key and o["status"] == "pending":
            o["status"] = "claimed"
            break
    else:
        ORDERS.append({
            "order_id": len(ORDERS) + 1,
            "user_id": ctx.author.id,
            "username": str(ctx.author),
            "product": product_key,
            "product_name": item["name"],
            "price": price,
            "email": "Instant Claim",
            "image": None,
            "status": "claimed"
        })
    save_data("orders.json", ORDERS)
    
    embed = discord.Embed(title="🎉 Rank Claimed!", color=discord.Color.gold())
    embed.description = f"Successfully purchased and claimed **{item['name']}** for **₱{price}**!"
    embed.add_field(name="Remaining Balance", value=f"₱{ECONOMY[user_id]}")
    await ctx.send(embed=embed)

@bot.command(name="orders")
async def orders(ctx):
    if not is_whitelisted(ctx.author.id, ctx.guild.id if ctx.guild else None):
        return await ctx.send("❌ Whitelisted only.")
    if not ORDERS:
        return await ctx.send("📋 No pending or recorded orders.")
    
    embed = discord.Embed(title="📦 Server Orders List", color=discord.Color.blue())
    for o in ORDERS[-10:]:  # Display last 10 orders
        status_emoji = "🟢" if o["status"] == "claimed" else "🟡"
        embed.add_field(
            name=f"#{o.get('order_id', '?')} | {o['product_name']} ({status_emoji} {o['status'].capitalize()})",
            value=f"User: <@{o['user_id']}> | Price: ₱{o['price']} | Contact: `{o.get('email', 'N/A')}`",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name="clearorder")
async def clearorder(ctx, target: str):
    if not is_whitelisted(ctx.author.id, ctx.guild.id if ctx.guild else None):
        return await ctx.send("❌ Whitelisted only.")
    global ORDERS
    target_lower = target.lower()
    
    if target_lower == "all":
        ORDERS = []
        save_data("orders.json", ORDERS)
        return await ctx.send("✅ All orders have been cleared.")
    
    if target_lower in PRODUCTS:
        ORDERS = [o for o in ORDERS if o["product"] != target_lower]
        save_data("orders.json", ORDERS)
        return await ctx.send(f"✅ Cleared all orders for `{target_lower}`.")
    
    try:
        uid = int(target)
        ORDERS = [o for o in ORDERS if o["user_id"] != uid]
        save_data("orders.json", ORDERS)
        await ctx.send(f"✅ Cleared orders for user ID `{uid}`.")
    except ValueError:
        await ctx.send("❌ Invalid target. Specify `all`, a product name, or a user ID.")

@bot.command(name="bal")
async def bal(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_id = str(target.id)
    balance = ECONOMY.get(user_id, 0)
    await ctx.send(f"💰 {target.mention} has **₱{balance}** Powoncy!")

@bot.command(name="daily")
async def daily(ctx):
    user_id = str(ctx.author.id)
    now = time.time()
    last_claim = DAILY_COOLDOWNS.get(user_id, 0)

    if now - last_claim < 86400:
        hours_left = round((86400 - (now - last_claim)) / 3600, 1)
        return await ctx.send(f"⏳ You need to wait **{hours_left} hours** to claim your daily Powoncy!")

    reward = 100
    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + reward
    DAILY_COOLDOWNS[user_id] = now
    save_data("economy.json", ECONOMY)
    save_data("cooldowns.json", DAILY_COOLDOWNS)
    await ctx.send(f"✅ You claimed your daily reward of **₱{reward}** Powoncy!")

@bot.command(name="addcoins")
async def addcoins(ctx, member: discord.Member, amount: int):
    if not is_whitelisted(ctx.author.id, ctx.guild.id if ctx.guild else None):
        return await ctx.send("❌ Whitelisted only.")
    user_id = str(member.id)
    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + amount
    save_data("economy.json", ECONOMY)
    await ctx.send(f"✅ Added **₱{amount}** to {member.mention}'s balance! New balance: **₱{ECONOMY[user_id]}**.")

@bot.command(name="whitelist", aliases=["w"])
async def whitelist(ctx, target: str):
    if not is_owner(ctx.author.id):
        return await ctx.send("❌ Bot Owner only.")
    
    target_id = None
    if ctx.message.mentions:
        target_id = ctx.message.mentions[0].id
        is_server = False
    else:
        try:
            target_id = int(target)
            is_server = bot.get_guild(target_id) is not None
        except ValueError:
            return await ctx.send("❌ Invalid User mention, User ID, or Server ID.")
    
    if is_server:
        if target_id not in WHITELIST_DATA["servers"]:
            WHITELIST_DATA["servers"].append(target_id)
            save_data("whitelist.json", WHITELIST_DATA)
        await ctx.send(f"✅ Server ID `{target_id}` added to server whitelist!")
    else:
        if target_id not in WHITELIST_DATA["users"]:
            WHITELIST_DATA["users"].append(target_id)
            save_data("whitelist.json", WHITELIST_DATA)
        await ctx.send(f"✅ User <@{target_id}> (`{target_id}`) added to user whitelist!")

@bot.command(name="unwhitelist", aliases=["uw"])
async def unwhitelist(ctx, target: str):
    if not is_owner(ctx.author.id):
        return await ctx.send("❌ Bot Owner only.")
    
    target_id = None
    if ctx.message.mentions:
        target_id = ctx.message.mentions[0].id
    else:
        try:
            target_id = int(target)
        except ValueError:
            return await ctx.send("❌ Invalid User mention, User ID, or Server ID.")
    
    removed = False
    if target_id in WHITELIST_DATA["users"]:
        WHITELIST_DATA["users"].remove(target_id)
        removed = True
    if target_id in WHITELIST_DATA["servers"]:
        WHITELIST_DATA["servers"].remove(target_id)
        removed = True
        
    if removed:
        save_data("whitelist.json", WHITELIST_DATA)
        await ctx.send(f"🗑️ Successfully removed `{target_id}` from whitelist.")
    else:
        await ctx.send(f"⚠️ Target `{target_id}` was not in the whitelist.")

@bot.command(name="presence")
async def presence(ctx, activity_type: str, *, status_text: str):
    if not is_owner(ctx.author.id):
        return await ctx.send("❌ Owner only.")
    
    activity_type = activity_type.lower()
    types = {
        "playing": discord.ActivityType.playing,
        "watching": discord.ActivityType.watching,
        "listening": discord.ActivityType.listening,
        "competing": discord.ActivityType.competing
    }
    
    selected_type = types.get(activity_type, discord.ActivityType.watching)
    await bot.change_presence(activity=discord.Activity(type=selected_type, name=status_text))
    await ctx.send(f"✅ Updated presence activity to **{activity_type.capitalize()} {status_text}**")

@bot.command(name="status")
async def status(ctx):
    uptime_seconds = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    embed = discord.Embed(title="🤖 System Diagnostic & Status", color=discord.Color.blue())
    embed.add_field(name="Ping", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    embed.add_field(name="Uptime", value=f"`{hours}h {minutes}m {seconds}s`", inline=True)
    embed.add_field(name="Servers Connected", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="Whitelisted Users", value=f"`{len(WHITELIST_DATA.get('users', []))}`", inline=True)
    embed.add_field(name="Whitelisted Servers", value=f"`{len(WHITELIST_DATA.get('servers', []))}`", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="connect")
async def connect(ctx, target_guild_id: int, target_channel_id: int):
    if not is_owner(ctx.author.id): 
        return await ctx.send("❌ Only the bot owner can establish server connections.")
    
    target_guild = bot.get_guild(target_guild_id)
    if not target_guild:
        return await ctx.send("❌ Connection failed: I am not in that server.")
    
    target_channel = target_guild.get_channel(target_channel_id)
    if not target_channel:
        return await ctx.send(f"❌ Connection failed: Could not find that channel in **{target_guild.name}**.")
        
    try:
        await target_channel.send(f"🔗 **SYSTEM LINK:** Connection established from **{ctx.guild.name}** by {ctx.author.mention}.")
        await ctx.send(f"✅ Connection established with **{target_guild.name}**!")
    except discord.Forbidden:
        await ctx.send("❌ Connection failed: Missing permissions in remote channel.")

@bot.command(name="ticket")
async def ticket(ctx, *, reason: str = "General Support"):
    if not isinstance(ctx.channel, discord.TextChannel):
        return await ctx.send("❌ Tickets can only be created in public text channels.")
    thread = await ctx.channel.create_thread(name=f"🎫-ticket-{ctx.author.name}", auto_archive_duration=60)
    await thread.send(f"Hello {ctx.author.mention}, support will be with you shortly!\n**Reason:** {reason}")
    await ctx.send(f"✅ Ticket thread created: {thread.mention}")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command(name="userinfo")
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"User Info - {member}", color=discord.Color.blurple())
    embed.add_field(name="ID", value=f"`{member.id}`")
    embed.add_field(name="Joined Server", value=str(member.joined_at.date()) if member.joined_at else "N/A")
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="serverinfo")
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"Server Info - {guild.name}", color=discord.Color.green())
    embed.add_field(name="Server ID", value=f"`{guild.id}`")
    embed.add_field(name="Members", value=f"`{guild.member_count}`")
    embed.add_field(name="Owner", value=str(guild.owner))
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 **{member}** was kicked. Reason: {reason}")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 **{member}** was banned. Reason: {reason}")

@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"✅ Cleared {amount} messages.")
    await msg.delete(delay=3)

@bot.command(name="sync")
async def sync(ctx):
    if not is_whitelisted(ctx.author.id, ctx.guild.id if ctx.guild else None):
        return await ctx.send("❌ Whitelisted only.")
    synced = await bot.tree.sync()
    await ctx.send(f"✅ Synced {len(synced)} slash commands.")

@bot.command(name="shutdown")
async def shutdown(ctx):
    if not is_owner(ctx.author.id):
        return await ctx.send("❌ Owner only.")
    await ctx.send("🛑 Shutting down bot...")
    await bot.close()


# ========================================================================
# SLASH COMMANDS (/)
# ========================================================================

@bot.tree.command(name="help", description="Show all available commands")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="✨ VacantMC Network Bot | Command Panel",
        description="Here is the list of available commands. Currency is set in Powoncy (₱).",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="🛒 Rank & Store System",
        value="`/po <product> [email]` - Order a rank/product\n"
              "`/claimrank <product>` - Claim/buy a rank directly using ₱\n"
              "`/orders` - View all active orders\n"
              "`/clearorder <target>` - Clear orders",
        inline=False
    )
    embed.add_field(
        name="💰 Economy & Games (Powoncy ₱)",
        value="`/bal`, `/daily`, `/work`, `/rob`\n"
              "`/cf`, `/bj`, `/slots`, `/mines`",
        inline=False
    )
    embed.add_field(
        name="🎟️ Codes & Admin",
        value="`/redeem <code>`, `/gencode`\n"
              "`/whitelist <target>`, `/unwhitelist <target>`\n"
              "`/presence <activity_type> <text>`, `/status`, `/shutdown`",
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="gencode", description="Generate a redeem code (Whitelisted Server Admin Only)")
async def slash_gencode(interaction: discord.Interaction, amount: int, uses: int = 1, custom_code: str = None):
    # Simulated Context check
    class MockCtx:
        author = interaction.user
        guild = interaction.guild
    
    if not can_gencode(MockCtx):
        return await interaction.response.send_message("❌ You must be a bot owner or a server administrator in a whitelisted server.", ephemeral=True)
    if amount <= 0 or uses <= 0:
        return await interaction.response.send_message("❌ Amount and uses must be positive.", ephemeral=True)
        
    code = custom_code or ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    if code in CODES:
        return await interaction.response.send_message(f"❌ Code `{code}` already exists.", ephemeral=True)
        
    CODES[code] = {"amount": amount, "uses": uses, "used_by": []}
    save_data("codes.json", CODES)
    await interaction.response.send_message(f"🎟️ **Code Generated:** `{code}` | **Amount:** ₱{amount} | **Uses:** {uses}", ephemeral=True)

@bot.tree.command(name="redeem", description="Redeem a Powoncy code")
async def slash_redeem(interaction: discord.Interaction, code: str):
    code = code.upper()
    user_id = interaction.user.id
    
    if code not in CODES:
        return await interaction.response.send_message("❌ Invalid or expired redeem code.", ephemeral=True)
        
    code_data = CODES[code]
    if user_id in code_data["used_by"]:
        return await interaction.response.send_message("❌ You have already claimed this code.", ephemeral=True)
        
    if code_data["uses"] <= 0:
        del CODES[code]
        save_data("codes.json", CODES)
        return await interaction.response.send_message("❌ This code has reached its maximum uses and expired.", ephemeral=True)
        
    ECONOMY[str(user_id)] = ECONOMY.get(str(user_id), 0) + code_data["amount"]
    code_data["uses"] -= 1
    code_data["used_by"].append(user_id)
    if code_data["uses"] <= 0: del CODES[code]
    save_data("economy.json", ECONOMY)
    save_data("codes.json", CODES)
    
    await interaction.response.send_message(f"🎉 Successfully redeemed code! Added **₱{code_data['amount']}** to your balance.", ephemeral=True)

@bot.tree.command(name="work", description="Work for some Powoncy ₱")
async def slash_work(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    earned = random.randint(20, 150)
    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + earned
    save_data("economy.json", ECONOMY)
    await interaction.response.send_message(f"💼 You worked hard and earned **₱{earned}** Powoncy!")

@bot.tree.command(name="bj", description="Play Blackjack")
async def slash_bj(interaction: discord.Interaction, bet: int):
    user_id = str(interaction.user.id)
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await interaction.response.send_message("❌ Invalid bet or insufficient funds.", ephemeral=True)
    
    ECONOMY[user_id] -= bet
    save_data("economy.json", ECONOMY)
    
    view = BlackjackView(interaction.user.id, bet)
    await interaction.response.send_message(
        f"🃏 **Blackjack**\n{interaction.user.mention}, you drew a total of **{view.player_total}**.\nDealer is showing **{view.dealer_total - random.randint(2,6)}**.\nWhat will you do?", 
        view=view
    )

@bot.tree.command(name="po", description="Order a rank or store product")
async def slash_po(interaction: discord.Interaction, product: str, email: str = "none"):
    product_key = product.lower()
    if product_key not in PRODUCTS:
        return await interaction.response.send_message(f"❌ Invalid product. Choose from: {list(PRODUCTS.keys())}", ephemeral=True)
    
    item = PRODUCTS[product_key]
    order_entry = {
        "order_id": len(ORDERS) + 1,
        "user_id": interaction.user.id,
        "username": str(interaction.user),
        "product": product_key,
        "product_name": item["name"],
        "price": item["price"],
        "email": email,
        "image": None,
        "status": "pending"
    }
    ORDERS.append(order_entry)
    save_data("orders.json", ORDERS)
    await interaction.response.send_message(f"✅ Order placed for **{item['name']}** (₱{item['price']})!", ephemeral=True)

@bot.tree.command(name="claimrank", description="Claim or buy a rank instantly using ₱ Powoncy")
async def slash_claimrank(interaction: discord.Interaction, product: str):
    product_key = product.lower()
    if product_key not in PRODUCTS:
        return await interaction.response.send_message(f"❌ Invalid rank. Available: {list(PRODUCTS.keys())}", ephemeral=True)
    
    item = PRODUCTS[product_key]
    user_id = str(interaction.user.id)
    balance = ECONOMY.get(user_id, 0)
    price = item["price"]
    
    if balance < price:
        return await interaction.response.send_message(f"❌ Insufficient ₱ balance! Required: ₱{price}, You have: ₱{balance}", ephemeral=True)
    
    ECONOMY[user_id] -= price
    
    ORDERS.append({
        "order_id": len(ORDERS) + 1,
        "user_id": interaction.user.id,
        "username": str(interaction.user),
        "product": product_key,
        "product_name": item["name"],
        "price": price,
        "email": "Slash Instant Claim",
        "image": None,
        "status": "claimed"
    })
    save_data("economy.json", ECONOMY)
    save_data("orders.json", ORDERS)
    await interaction.response.send_message(f"🎉 Successfully claimed **{item['name']}** for **₱{price}**!", ephemeral=True)

@bot.tree.command(name="bal", description="Check your ₱ Powoncy balance")
async def slash_bal(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    balance = ECONOMY.get(user_id, 0)
    await interaction.response.send_message(f"💰 You have **₱{balance}** Powoncy!", ephemeral=True)

@bot.tree.command(name="daily", description="Claim daily Powoncy ₱")
async def slash_daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = time.time()
    last_claim = DAILY_COOLDOWNS.get(user_id, 0)

    if now - last_claim < 86400:
        hours_left = round((86400 - (now - last_claim)) / 3600, 1)
        return await interaction.response.send_message(f"⏳ Wait **{hours_left} hours** to claim again!", ephemeral=True)

    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + 100
    DAILY_COOLDOWNS[user_id] = now
    save_data("economy.json", ECONOMY)
    save_data("cooldowns.json", DAILY_COOLDOWNS)
    await interaction.response.send_message("✅ Claimed daily **₱100** Powoncy!", ephemeral=True)

@bot.tree.command(name="whitelist", description="Whitelist a user or server ID")
async def slash_whitelist(interaction: discord.Interaction, target_id: str):
    if not is_owner(interaction.user.id):
        return await interaction.response.send_message("❌ Owner only", ephemeral=True)
    
    try:
        tid = int(target_id)
    except ValueError:
        return await interaction.response.send_message("❌ Must be a numeric User or Server ID.", ephemeral=True)
    
    is_server = bot.get_guild(tid) is not None
    if is_server:
        if tid not in WHITELIST_DATA["servers"]:
            WHITELIST_DATA["servers"].append(tid)
            save_data("whitelist.json", WHITELIST_DATA)
        await interaction.response.send_message(f"✅ Whitelisted server ID `{tid}`", ephemeral=True)
    else:
        if tid not in WHITELIST_DATA["users"]:
            WHITELIST_DATA["users"].append(tid)
            save_data("whitelist.json", WHITELIST_DATA)
        await interaction.response.send_message(f"✅ Whitelisted user ID `{tid}`", ephemeral=True)

@bot.tree.command(name="unwhitelist", description="Remove a user or server ID from whitelist")
async def slash_unwhitelist(interaction: discord.Interaction, target_id: str):
    if not is_owner(interaction.user.id):
        return await interaction.response.send_message("❌ Owner only", ephemeral=True)
    
    try:
        tid = int(target_id)
    except ValueError:
        return await interaction.response.send_message("❌ Must be a numeric ID.", ephemeral=True)
    
    removed = False
    if tid in WHITELIST_DATA["users"]:
        WHITELIST_DATA["users"].remove(tid)
        removed = True
    if tid in WHITELIST_DATA["servers"]:
        WHITELIST_DATA["servers"].remove(tid)
        removed = True
        
    if removed:
        save_data("whitelist.json", WHITELIST_DATA)
        await interaction.response.send_message(f"🗑️ Removed `{tid}` from whitelist.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ `{tid}` was not found in whitelist.", ephemeral=True)

@bot.tree.command(name="status", description="Check bot status and ping")
async def slash_status(interaction: discord.Interaction):
    uptime_seconds = int(time.time() - START_TIME)
    embed = discord.Embed(title="🤖 Bot Status", color=discord.Color.blue())
    embed.add_field(name="Ping", value=f"`{round(bot.latency * 1000)}ms`")
    embed.add_field(name="Uptime", value=f"`{uptime_seconds}s`")
    embed.add_field(name="Servers", value=f"`{len(bot.guilds)}`")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="shutdown", description="Shut down the bot")
async def slash_shutdown(interaction: discord.Interaction):
    if not is_owner(interaction.user.id):
        return await interaction.response.send_message("❌ Owner only", ephemeral=True)
    await interaction.response.send_message("🛑 Shutting down...", ephemeral=True)
    await bot.close()

# =========================
# START BOT
# =========================
if __name__ == "__main__":
    if TOKEN is None:
        print("❌ DISCORD_TOKEN not found in .env file.")
    else:
        bot.run(TOKEN)
