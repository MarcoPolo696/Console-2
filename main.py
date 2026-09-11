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
    "vip": {"name": "VIP Rank", "type": "rank", "price": 100, "rank_order": 1},
    "mvp": {"name": "MVP Rank", "type": "rank", "price": 250, "rank_order": 2},
    "legend": {"name": "Legend Rank", "type": "rank", "price": 500, "rank_order": 3},
    "nitro": {"name": "Discord Nitro", "type": "gift", "price": 300, "rank_order": 99},
    "mcfa": {"name": "MCFA Account", "type": "digital", "price": 150, "rank_order": 99}
}

OWNER_IDS = [1192047136192352256, 1334881324414271602, 1515362345705148491]

# =========================
# DATA STORAGE & ATOMIC JSON HELPERS
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
    temp_file = f"{file_name}.tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(temp_file, file_name)
    except Exception as e:
        print(f"❌ File Save Error ({file_name}): {e}")

ORDERS = load_data("orders.json", [])
WHITELIST_DATA = load_data("whitelist.json", {"users": [], "servers": []})

if isinstance(WHITELIST_DATA, list):
    WHITELIST_DATA = {"users": WHITELIST_DATA, "servers": []}

ECONOMY = load_data("economy.json", {})
INVENTORY = load_data("inventory.json", {})
DAILY_COOLDOWNS = load_data("cooldowns.json", {})
CODES = load_data("codes.json", {})

# =========================
# PERMISSION SYSTEM
# =========================
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

def can_gencode(user_id: int, guild: discord.Guild = None) -> bool:
    if is_owner(user_id): 
        return True
    if guild and guild.id in WHITELIST_DATA.get("servers", []):
        member = guild.get_member(user_id)
        if member and member.guild_permissions.administrator:
            return True
    return False

# =========================
# INTERACTIVE VIEWS
# =========================
class BlackjackView(discord.ui.View):
    def __init__(self, user_id: int, bet: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet = bet
        self.player_total = random.randint(12, 20)
        self.dealer_total = random.randint(14, 21)
        self.message = None

    async def update_economy(self, won: bool):
        uid = str(self.user_id)
        if won:
            ECONOMY[uid] = ECONOMY.get(uid, 0) + (self.bet * 2)
        save_data("economy.json", ECONOMY)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                embed = discord.Embed(
                    title="🃏 Blackjack (Timed Out)",
                    description="Game timed out after 60 seconds of inactivity.",
                    color=discord.Color.dark_grey()
                )
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, custom_id="bj_hit")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your game!", ephemeral=True)
        
        self.player_total += random.randint(2, 10)
        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.blue())
        
        if self.player_total > 21:
            for child in self.children:
                child.disabled = True
            embed.color = discord.Color.red()
            embed.description = f"You hit and got **{self.player_total}**. BUST! You lost **₱{self.bet}**."
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
        else:
            embed.description = f"You hit! Your total is now **{self.player_total}**.\nDealer is showing **{self.dealer_total - random.randint(2,6)}**.\nWhat will you do?"
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, custom_id="bj_stand")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your game!", ephemeral=True)
        
        for child in self.children:
            child.disabled = True
        
        while self.dealer_total < 17:
            self.dealer_total += random.randint(2, 8)
            
        embed = discord.Embed(title="🃏 Blackjack Result")
        if self.dealer_total > 21 or self.player_total > self.dealer_total:
            await self.update_economy(True)
            embed.color = discord.Color.green()
            embed.description = f"**You Won!** 🎉\nYou stood at **{self.player_total}**. Dealer got **{self.dealer_total}**.\nYou won **₱{self.bet * 2}**!"
        elif self.player_total == self.dealer_total:
            uid_str = str(self.user_id)
            ECONOMY[uid_str] = ECONOMY.get(uid_str, 0) + self.bet
            save_data("economy.json", ECONOMY)
            embed.color = discord.Color.gold()
            embed.description = f"**Push (Tie)**\nYou and the dealer both got **{self.player_total}**. Your bet of **₱{self.bet}** was refunded."
        else:
            embed.color = discord.Color.red()
            embed.description = f"**You Lost!**\nYou stood at **{self.player_total}**. Dealer got **{self.dealer_total}**.\nYou lost **₱{self.bet}**."

        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

# =========================
# BOT SETUP
# =========================
class VacantBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="$", intents=intents, help_command=None)

    async def setup_hook(self):
        try:
            synced = await self.tree.sync()
            print(f"✅ Synced {len(synced)} slash commands globally")
        except Exception as e:
            print(f"❌ Slash Sync Error: {e}")

bot = VacantBot()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name="VacantMC | $help")
    )

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=discord.Embed(description=f"❌ Missing required argument: `{error.param.name}`", color=discord.Color.red()))
    elif isinstance(error, commands.BadArgument):
        await ctx.send(embed=discord.Embed(description="❌ Invalid argument provided.", color=discord.Color.red()))
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=discord.Embed(description="❌ You do not have permission to use this command.", color=discord.Color.red()))

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
        value="`$store` - View ranks in order and products\n"
              "`$po <product> [email]` - Order a product or rank\n"
              "`$claimrank <product>` - Claim/buy a rank directly using ₱\n"
              "`$orders` - View all active orders (Whitelisted)\n"
              "`$clearorder <all|product|user_id>` - Clear orders",
        inline=False
    )
    embed.add_field(
        name="💰 Economy & Games",
        value="`$bal` - Check your ₱ balance\n"
              "`$inventory` - View your owned items\n"
              "`$leaderboard` - View top 10 richest users\n"
              "`$pay <user> <amount>` - Give Powoncy to someone\n"
              "`$daily` - Claim your daily ₱ reward\n"
              "`$work` - Work for a random amount of ₱\n"
              "`$rob <user>` - Try to steal ₱ from someone\n"
              "`$cf <bet> <h|t>` - Coin flip\n"
              "`$bj <bet>` - Play Blackjack\n"
              "`$slots <bet>` - Spin the slot machine\n"
              "`$mines <bet> <mines_count>` - Play risk mines\n"
              "`$8ball <question>` - Ask the magic 8-ball\n"
              "`$addcoins <user> <amount>` - Add ₱ to user (Whitelisted)",
        inline=False
    )
    embed.add_field(
        name="🎟️ Redeem Codes",
        value="`$redeem <code>` - Claim a 4-digit code\n"
              "`$gencode <type> <amount> <uses> [code]` - Gen code (Whitelisted)",
        inline=False
    )
    embed.add_field(
        name="🛠️ Admin, Utility & Fun",
        value="`$servericon` - View server icon\n"
              "`$avatar <user>` - View user avatar\n"
              "`$poll <question>` - Create a simple reaction poll\n"
              "`$roll [sides]` - Roll a die\n"
              "`$calc <expression>` - Basic math calculator\n"
              "`$flip` - Flip a coin quick\n"
              "`$meme` - Get a random programmer joke\n"
              "`$serverboosts` - Check server boost count\n"
              "`$emojis` - List server emojis\n"
              "`$say <text>` - Make the bot say something (Whitelisted)",
        inline=False
    )
    embed.set_footer(text="VacantMC System • Currency: ₱ (Powoncy)")
    await ctx.send(embed=embed)

@bot.command(name="servericon")
async def servericon(ctx):
    if not ctx.guild.icon:
        return await ctx.send("❌ This server has no icon.")
    embed = discord.Embed(title=f"🖼️ {ctx.guild.name}'s Icon", color=discord.Color.blue())
    embed.set_image(url=ctx.guild.icon.url)
    await ctx.send(embed=embed)

@bot.command(name="avatar", aliases=["av"])
async def avatar(ctx, member: discord.Member = None):
    target = member or ctx.author
    embed = discord.Embed(title=f"🖼️ {target.name}'s Avatar", color=discord.Color.blue())
    embed.set_image(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="poll")
async def poll(ctx, *, question: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass
    embed = discord.Embed(title="📊 Server Poll", description=question, color=discord.Color.gold())
    embed.set_footer(text=f"Poll created by {ctx.author}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")

@bot.command(name="roll")
async def roll(ctx, sides: int = 6):
    if sides < 2:
        return await ctx.send("❌ A die must have at least 2 sides.")
    result = random.randint(1, sides)
    await ctx.send(f"🎲 {ctx.author.mention}, you rolled a **{result}** (1-{sides}).")

@bot.command(name="calc")
async def calc(ctx, *, expression: str):
    allowed_chars = set("0123456789+-*/(). ")
    if not all(c in allowed_chars for c in expression):
        return await ctx.send("❌ Invalid characters used. Numbers and `+ - * / ()` only.")
    try:
        result = eval(expression, {"__builtins__": None}, {})
        await ctx.send(f"🧮 Result: `{expression} = {result}`")
    except ZeroDivisionError:
        await ctx.send("❌ Division by zero is not allowed.")
    except Exception:
        await ctx.send("❌ Invalid mathematical expression.")

@bot.command(name="flip")
async def flip(ctx):
    result = random.choice(["Heads", "Tails"])
    await ctx.send(f"🪙 The coin landed on: **{result}**!")

@bot.command(name="meme")
async def meme(ctx):
    jokes = [
        ("Why do programmers prefer dark mode?", "Because light attracts bugs!"),
        ("There are 10 types of people in the world:", "Those who understand binary, and those who don't."),
        ("Why did the developer go broke?", "Because he used up all his cache!"),
        ("How do trees log into the internet?", "They log in!"),
        ("Why do Java programmers wear glasses?", "Because they don't C#! ")
    ]
    setup, punchline = random.choice(jokes)
    embed = discord.Embed(title="😂 Programmer Humor", color=discord.Color.green())
    embed.add_field(name=setup, value=punchline, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="serverboosts", aliases=["boosts"])
async def serverboosts(ctx):
    embed = discord.Embed(title=f"🚀 {ctx.guild.name} Boost Status", color=discord.Color.purple())
    embed.add_field(name="Boost Count", value=f"`{ctx.guild.premium_subscription_count}` boosts", inline=True)
    embed.add_field(name="Boost Level", value=f"Level `{ctx.guild.premium_tier}`", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="emojis")
async def emojis(ctx):
    guild_emojis = [str(e) for e in ctx.guild.emojis]
    if not guild_emojis:
        return await ctx.send("❌ This server has no custom emojis.")
    chunks = [" ".join(guild_emojis[i:i+20]) for i in range(0, len(guild_emojis), 20)]
    embed = discord.Embed(title=f"😀 Server Emojis ({len(guild_emojis)})", description=chunks[0], color=discord.Color.gold())
    await ctx.send(embed=embed)

@bot.command(name="say")
async def say(ctx, *, text: str):
    if not is_whitelisted(ctx.author.id, ctx.guild.id if ctx.guild else None):
        return await ctx.send("❌ Whitelisted only.")
    try:
        await ctx.message.delete()
    except Exception:
        pass
    await ctx.send(text)

@bot.command(name="inventory", aliases=["inv"])
async def inventory(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_id = str(target.id)
    user_inv = INVENTORY.get(user_id, {})
    
    embed = discord.Embed(title=f"🎒 {target.name}'s Inventory", color=discord.Color.blue())
    if not user_inv:
        embed.description = "This inventory is completely empty!"
    else:
        for item, count in user_inv.items():
            item_name = PRODUCTS.get(item, {}).get("name", item.upper())
            embed.add_field(name=item_name, value=f"Quantity: **x{count}**", inline=False)
            
    await ctx.send(embed=embed)

@bot.command(name="pay")
async def pay(ctx, member: discord.Member, amount: int):
    user_id = str(ctx.author.id)
    target_id = str(member.id)
    
    if amount <= 0:
        return await ctx.send(embed=discord.Embed(description="❌ You must send a valid positive amount.", color=discord.Color.red()))
    if user_id == target_id:
        return await ctx.send(embed=discord.Embed(description="❌ You can't pay yourself!", color=discord.Color.red()))
    if ECONOMY.get(user_id, 0) < amount:
        return await ctx.send(embed=discord.Embed(description="❌ You don't have enough Powoncy.", color=discord.Color.red()))
        
    ECONOMY[user_id] -= amount
    ECONOMY[target_id] = ECONOMY.get(target_id, 0) + amount
    save_data("economy.json", ECONOMY)
    
    embed = discord.Embed(description=f"💸 Successfully sent **₱{amount}** to {member.mention}!", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="leaderboard", aliases=["lb", "baltop"])
async def leaderboard(ctx):
    sorted_eco = sorted(ECONOMY.items(), key=lambda x: x[1], reverse=True)[:10]
    
    embed = discord.Embed(title="🏆 Powoncy Leaderboard - Top 10", color=discord.Color.gold())
    if not sorted_eco:
        embed.description = "No one has any Powoncy yet!"
    else:
        for index, (uid, amount) in enumerate(sorted_eco, start=1):
            embed.add_field(name=f"#{index}", value=f"<@{uid}> - **₱{amount}**", inline=False)
            
    await ctx.send(embed=embed)

@bot.command(name="8ball")
async def eightball(ctx, *, question: str):
    responses = [
        "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes - definitely.",
        "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
        "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
        "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
        "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.",
        "Very doubtful."
    ]
    embed = discord.Embed(title="🎱 Magic 8-Ball", color=discord.Color.purple())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(responses), inline=False)
    await ctx.send(embed=embed)

@bot.command(name="work")
async def work(ctx):
    user_id = str(ctx.author.id)
    earned = random.randint(20, 150)
    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + earned
    save_data("economy.json", ECONOMY)
    
    embed = discord.Embed(description=f"💼 You worked hard and earned **₱{earned}** Powoncy!", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="rob")
async def rob(ctx, target: discord.Member):
    user_id = str(ctx.author.id)
    target_id = str(target.id)
    
    if user_id == target_id: 
        return await ctx.send(embed=discord.Embed(description="❌ You can't rob yourself!", color=discord.Color.red()))
    
    user_bal = ECONOMY.get(user_id, 0)
    target_bal = ECONOMY.get(target_id, 0)
    
    if user_bal < 50: 
        return await ctx.send(embed=discord.Embed(description="❌ You need at least ₱50 to attempt a robbery (as collateral).", color=discord.Color.red()))
    if target_bal < 50: 
        return await ctx.send(embed=discord.Embed(description="❌ They don't have enough Powoncy worth stealing!", color=discord.Color.red()))
    
    success = random.choice([True, False])
    if success:
        stolen = int(target_bal * random.uniform(0.1, 0.3))
        ECONOMY[user_id] += stolen
        ECONOMY[target_id] -= stolen
        embed = discord.Embed(description=f"🥷 **SUCCESS!** You robbed {target.mention} and got away with **₱{stolen}**!", color=discord.Color.green())
    else:
        fine = int(user_bal * random.uniform(0.1, 0.2))
        ECONOMY[user_id] -= fine
        embed = discord.Embed(description=f"🚨 **CAUGHT!** You failed to rob {target.mention} and paid a fine of **₱{fine}**!", color=discord.Color.red())
        
    save_data("economy.json", ECONOMY)
    await ctx.send(embed=embed)

@bot.command(name="cf", aliases=["coinflip"])
async def coinflip(ctx, bet: int, side: str):
    user_id = str(ctx.author.id)
    side = side.lower()
    if side not in ["heads", "tails", "h", "t"]: 
        return await ctx.send(embed=discord.Embed(description="❌ Choose `heads` or `tails`.", color=discord.Color.red()))
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await ctx.send(embed=discord.Embed(description="❌ Invalid bet or insufficient funds.", color=discord.Color.red()))
        
    ECONOMY[user_id] -= bet
    result = random.choice(["heads", "tails"])
    
    embed = discord.Embed(title="🪙 Coin Flip Result")
    if side[0] == result[0]:
        winnings = bet * 2
        ECONOMY[user_id] += winnings
        embed.color = discord.Color.green()
        embed.description = f"The coin landed on **{result.capitalize()}**! You won **₱{winnings}**!"
    else:
        embed.color = discord.Color.red()
        embed.description = f"The coin landed on **{result.capitalize()}**. You lost your bet of **₱{bet}**."
        
    save_data("economy.json", ECONOMY)
    await ctx.send(embed=embed)

@bot.command(name="bj", aliases=["blackjack"])
async def blackjack(ctx, bet: int):
    user_id = str(ctx.author.id)
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await ctx.send(embed=discord.Embed(description="❌ Invalid bet or insufficient funds.", color=discord.Color.red()))
    
    ECONOMY[user_id] -= bet
    save_data("economy.json", ECONOMY)
    
    view = BlackjackView(ctx.author.id, bet)
    embed = discord.Embed(
        title="🃏 Blackjack",
        description=f"{ctx.author.mention}, you drew a total of **{view.player_total}**.\nDealer is showing **{view.dealer_total - random.randint(2,6)}**.\nWhat will you do?",
        color=discord.Color.blue()
    )
    view.message = await ctx.send(embed=embed, view=view)

@bot.command(name="slots")
async def slots(ctx, bet: int):
    user_id = str(ctx.author.id)
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await ctx.send(embed=discord.Embed(description="❌ Invalid bet or insufficient funds.", color=discord.Color.red()))
        
    ECONOMY[user_id] -= bet
    emojis = ["🍒", "🍋", "🔔", "💎", "🎰"]
    r1, r2, r3 = random.choice(emojis), random.choice(emojis), random.choice(emojis)
    
    embed = discord.Embed(title="🎰 Slots Result")
    if r1 == r2 == r3:
        win = bet * 5
        ECONOMY[user_id] += win
        embed.color = discord.Color.gold()
        embed.description = f"`[ {r1} | {r2} | {r3} ]`\n**JACKPOT!** You won **₱{win}**!"
    elif r1 == r2 or r2 == r3 or r1 == r3:
        win = bet * 2
        ECONOMY[user_id] += win
        embed.color = discord.Color.green()
        embed.description = f"`[ {r1} | {r2} | {r3} ]`\nSmall win! You won **₱{win}**!"
    else:
        embed.color = discord.Color.red()
        embed.description = f"`[ {r1} | {r2} | {r3} ]`\nYou lost **₱{bet}**."
        
    save_data("economy.json", ECONOMY)
    await ctx.send(embed=embed)

@bot.command(name="mines")
async def mines(ctx, bet: int, mines_count: int):
    user_id = str(ctx.author.id)
    if not (1 <= mines_count <= 24):
        return await ctx.send(embed=discord.Embed(description="❌ Mines count must be between 1 and 24.", color=discord.Color.red()))
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await ctx.send(embed=discord.Embed(description="❌ Invalid bet or insufficient funds.", color=discord.Color.red()))
        
    ECONOMY[user_id] -= bet
    safe_tiles = 25 - mines_count
    
    if safe_tiles < 3:
        win_chance = 0.05
    else:
        win_chance = (safe_tiles / 25) * ((safe_tiles - 1) / 24) * ((safe_tiles - 2) / 23)
        
    embed = discord.Embed(title="💣 Mines Result")
    if random.random() <= win_chance:
        multiplier = round(25 / safe_tiles, 2)
        winnings = int(bet * multiplier)
        ECONOMY[user_id] += winnings
        embed.color = discord.Color.green()
        embed.description = f"You successfully navigated the minefield!\nCashed out at **{multiplier}x** for **₱{winnings}**!"
    else:
        embed.color = discord.Color.red()
        embed.description = f"**BOOM!** You hit a mine and lost your bet of **₱{bet}**."
        
    save_data("economy.json", ECONOMY)
    await ctx.send(embed=embed)

@bot.command(name="gencode")
async def gencode(ctx, reward_type: str, quantity: int = 1, uses: int = 1, custom_code: str = None):
    if not can_gencode(ctx.author.id, ctx.guild):
        return await ctx.send("❌ You must be a bot owner or a server administrator in a whitelisted server.")
    
    valid_types = ["powoncy"] + list(PRODUCTS.keys())
    reward_type = reward_type.lower()
    
    if reward_type not in valid_types:
        return await ctx.send(f"❌ Invalid reward type. Choose from: `{', '.join(valid_types)}`")
        
    if quantity <= 0 or uses <= 0:
        return await ctx.send("❌ Quantity and uses must be positive numbers (1 or higher).")
        
    if custom_code and len(custom_code) != 4:
        return await ctx.send("❌ Custom code must be strictly 4 characters.")
        
    code = custom_code.upper() if custom_code else ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    if code in CODES:
        return await ctx.send(f"❌ Code `{code}` already exists.")
        
    CODES[code] = {
        "reward_type": reward_type,
        "amount": quantity,
        "uses": uses,
        "used_by": []
    }
    save_data("codes.json", CODES)
    
    embed = discord.Embed(title="🎟️ 4-Digit Code Generated", color=discord.Color.green())
    embed.add_field(name="Code", value=f"`{code}`", inline=True)
    embed.add_field(name="Reward", value=f"{quantity}x {reward_type.upper()}", inline=True)
    embed.add_field(name="Uses Left", value=f"{uses}", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="redeem")
async def redeem(ctx, code: str):
    code = code.upper()
    user_id = str(ctx.author.id)
    
    if len(code) != 4:
        return await ctx.send("❌ Redeem codes are strictly 4 characters long.")
    
    if code not in CODES:
        return await ctx.send("❌ Invalid or expired redeem code.")
        
    code_data = CODES[code]
    if ctx.author.id in code_data["used_by"]:
        return await ctx.send("❌ You have already claimed this code.")
        
    if code_data["uses"] <= 0:
        if code in CODES:
            del CODES[code]
            save_data("codes.json", CODES)
        return await ctx.send("❌ This code has reached its maximum uses and expired.")
        
    reward_type = code_data.get("reward_type", "powoncy")
    amount = code_data["amount"]
    
    if reward_type == "powoncy":
        ECONOMY[user_id] = ECONOMY.get(user_id, 0) + amount
        save_data("economy.json", ECONOMY)
        embed = discord.Embed(description=f"🎉 Successfully redeemed code! Added **₱{amount}** to your balance.", color=discord.Color.green())
    else:
        user_inv = INVENTORY.get(user_id, {})
        user_inv[reward_type] = user_inv.get(reward_type, 0) + amount
        INVENTORY[user_id] = user_inv
        save_data("inventory.json", INVENTORY)
        embed = discord.Embed(description=f"🎉 Code Redeemed! You received **{amount}x {reward_type.upper()}**! Check your `$inventory`.", color=discord.Color.green())
    
    code_data["uses"] -= 1
    code_data["used_by"].append(ctx.author.id)
    if code_data["uses"] <= 0:
        if code in CODES:
            del CODES[code]
        
    save_data("codes.json", CODES)
    await ctx.send(embed=embed)

@bot.command(name="store")
async def store(ctx):
    embed = discord.Embed(title="🛒 VacantMC Store & Rank Order", color=discord.Color.gold())
    
    sorted_products = sorted(PRODUCTS.items(), key=lambda x: x[1]['rank_order'])
    rank_text = ""
    other_text = ""
    
    for key, item in sorted_products:
        if item['type'] == 'rank':
            rank_text += f"**{item['rank_order']}. {item['name']}** (`{key}`) - ₱{item['price']}\n"
        else:
            other_text += f"**{item['name']}** (`{key}`) - ₱{item['price']}\n"
            
    embed.add_field(name="🏆 Rank Order Hierarchy", value=rank_text or "No ranks available.", inline=False)
    embed.add_field(name="🎁 Other Items", value=other_text or "No other items.", inline=False)
    embed.set_footer(text="Use $po <product> to order or $claimrank <product> to buy instantly.")
    await ctx.send(embed=embed)

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
    
    user_inv = INVENTORY.get(user_id, {})
    user_inv[product_key] = user_inv.get(product_key, 0) + 1
    INVENTORY[user_id] = user_inv
    save_data("inventory.json", INVENTORY)
    
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
    embed.description = f"Successfully purchased **{item['name']}** for **₱{price}**! Check your `$inventory`."
    embed.add_field(name="Remaining Balance", value=f"₱{ECONOMY[user_id]}")
    await ctx.send(embed=embed)

@bot.command(name="orders")
async def orders(ctx):
    if not is_whitelisted(ctx.author.id, ctx.guild.id if ctx.guild else None):
        return await ctx.send("❌ Whitelisted only.")
    if not ORDERS:
        return await ctx.send("📋 No pending or recorded orders.")
    
    embed = discord.Embed(title="📦 Server Orders List", color=discord.Color.blue())
    for o in ORDERS[-10:]:
        status_emoji = "🟢" if o["status"] == "claimed" else "🟡"
        embed.add_field(
            name=f"#{o.get('order_id', '?')} | {o['product_name']} ({status_emoji} {o['status'].capitalize()})",
            value=f"User: <@{o['user_id']}> | Price: ₱{o['price']} | Contact: `{o.get('email', 'N/A')}`",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name="clearorder")
async def clearorder(ctx, target: str):
    global ORDERS
    if not is_whitelisted(ctx.author.id, ctx.guild.id if ctx.guild else None):
        return await ctx.send("❌ Whitelisted only.")
    
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
    
    embed = discord.Embed(description=f"💰 {target.mention} has **₱{balance}** Powoncy!", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="daily")
async def daily(ctx):
    user_id = str(ctx.author.id)
    now = time.time()
    last_claim = DAILY_COOLDOWNS.get(user_id, 0)

    if now - last_claim < 86400:
        remaining_sec = int(86400 - (now - last_claim))
        hours, remainder = divmod(remaining_sec, 3600)
        minutes, _ = divmod(remainder, 60)
        return await ctx.send(embed=discord.Embed(description=f"⏳ You need to wait **{hours}h {minutes}m** to claim your daily Powoncy!", color=discord.Color.red()))

    reward = 100
    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + reward
    DAILY_COOLDOWNS[user_id] = now
    save_data("economy.json", ECONOMY)
    save_data("cooldowns.json", DAILY_COOLDOWNS)
    
    embed = discord.Embed(description=f"✅ You claimed your daily reward of **₱{reward}** Powoncy!", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="addcoins")
async def addcoins(ctx, member: discord.Member, amount: int):
    if not is_whitelisted(ctx.author.id, ctx.guild.id if ctx.guild else None):
        return await ctx.send("❌ Whitelisted only.")
    user_id = str(member.id)
    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + amount
    save_data("economy.json", ECONOMY)
    
    embed = discord.Embed(description=f"✅ Added **₱{amount}** to {member.mention}'s balance! New balance: **₱{ECONOMY[user_id]}**.", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="whitelist", aliases=["w"])
async def whitelist(ctx, target: str):
    if not is_owner(ctx.author.id):
        return await ctx.send("❌ Bot Owner only.")
    
    target_id = None
    is_server = False
    if ctx.message.mentions:
        target_id = ctx.message.mentions[0].id
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
# SLASH COMMANDS (/) - COMPLETE UPGRADED SYSTEM
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
        value="`/store` - View ranks and store items\n"
              "`/po <product> [email]` - Order a rank/product\n"
              "`/claimrank <product>` - Claim/buy a rank directly using ₱\n"
              "`/orders` - View active orders\n"
              "`/clearorder <target>` - Clear orders",
        inline=False
    )
    embed.add_field(
        name="💰 Economy & Games",
        value="`/bal`, `/inventory`, `/leaderboard`, `/pay`\n"
              "`/daily`, `/work`, `/rob`, `/8ball`\n"
              "`/cf`, `/bj`, `/slots`, `/mines`",
        inline=False
    )
    embed.add_field(
        name="🎟️ Codes & Admin",
        value="`/redeem <code>`, `/gencode`\n"
              "`/whitelist <target>`, `/unwhitelist <target>`\n"
              "`/status`, `/shutdown`",
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="inventory", description="Check your owned items")
async def slash_inventory(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_inv = INVENTORY.get(user_id, {})
    
    embed = discord.Embed(title=f"🎒 {interaction.user.name}'s Inventory", color=discord.Color.blue())
    if not user_inv:
        embed.description = "This inventory is completely empty!"
    else:
        for item, count in user_inv.items():
            item_name = PRODUCTS.get(item, {}).get("name", item.upper())
            embed.add_field(name=item_name, value=f"Quantity: **x{count}**", inline=False)
            
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="pay", description="Pay someone Powoncy")
async def slash_pay(interaction: discord.Interaction, member: discord.Member, amount: int):
    user_id = str(interaction.user.id)
    target_id = str(member.id)
    
    if amount <= 0: return await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
    if user_id == target_id: return await interaction.response.send_message("❌ Cannot pay yourself.", ephemeral=True)
    if ECONOMY.get(user_id, 0) < amount: return await interaction.response.send_message("❌ Not enough funds.", ephemeral=True)
        
    ECONOMY[user_id] -= amount
    ECONOMY[target_id] = ECONOMY.get(target_id, 0) + amount
    save_data("economy.json", ECONOMY)
    await interaction.response.send_message(f"💸 Successfully sent **₱{amount}** to {member.mention}!", ephemeral=True)

@bot.tree.command(name="leaderboard", description="View the top 10 richest users")
async def slash_leaderboard(interaction: discord.Interaction):
    sorted_eco = sorted(ECONOMY.items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="🏆 Powoncy Leaderboard - Top 10", color=discord.Color.gold())
    
    if not sorted_eco:
        embed.description = "No one has any Powoncy yet!"
    else:
        for index, (uid, amount) in enumerate(sorted_eco, start=1):
            embed.add_field(name=f"#{index}", value=f"<@{uid}> - **₱{amount}**", inline=False)
            
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="8ball", description="Ask the magic 8-ball a question")
async def slash_8ball(interaction: discord.Interaction, question: str):
    responses = ["It is certain.", "Without a doubt.", "Yes - definitely.", "Most likely.", "Outlook good.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.", "Better not tell you now.", "Cannot predict now.", "Don't count on it.", "My reply is no.", "Outlook not so good.", "Very doubtful."]
    embed = discord.Embed(title="🎱 Magic 8-Ball", color=discord.Color.purple())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(responses), inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="cf", description="Play Coin Flip")
async def slash_cf(interaction: discord.Interaction, bet: int, side: str):
    user_id = str(interaction.user.id)
    side = side.lower()
    if side not in ["heads", "tails", "h", "t"]:
        return await interaction.response.send_message("❌ Choose `heads` or `tails`.", ephemeral=True)
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await interaction.response.send_message("❌ Invalid bet or insufficient funds.", ephemeral=True)

    ECONOMY[user_id] -= bet
    result = random.choice(["heads", "tails"])

    embed = discord.Embed(title="🪙 Coin Flip Result")
    if side[0] == result[0]:
        winnings = bet * 2
        ECONOMY[user_id] += winnings
        embed.color = discord.Color.green()
        embed.description = f"The coin landed on **{result.capitalize()}**! You won **₱{winnings}**!"
    else:
        embed.color = discord.Color.red()
        embed.description = f"The coin landed on **{result.capitalize()}**. You lost your bet of **₱{bet}**."

    save_data("economy.json", ECONOMY)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="slots", description="Play the slot machine")
async def slash_slots(interaction: discord.Interaction, bet: int):
    user_id = str(interaction.user.id)
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await interaction.response.send_message("❌ Invalid bet or insufficient funds.", ephemeral=True)

    ECONOMY[user_id] -= bet
    emojis = ["🍒", "🍋", "🔔", "💎", "🎰"]
    r1, r2, r3 = random.choice(emojis), random.choice(emojis), random.choice(emojis)

    embed = discord.Embed(title="🎰 Slots Result")
    if r1 == r2 == r3:
        win = bet * 5
        ECONOMY[user_id] += win
        embed.color = discord.Color.gold()
        embed.description = f"`[ {r1} | {r2} | {r3} ]`\n**JACKPOT!** You won **₱{win}**!"
    elif r1 == r2 or r2 == r3 or r1 == r3:
        win = bet * 2
        ECONOMY[user_id] += win
        embed.color = discord.Color.green()
        embed.description = f"`[ {r1} | {r2} | {r3} ]`\nSmall win! You won **₱{win}**!"
    else:
        embed.color = discord.Color.red()
        embed.description = f"`[ {r1} | {r2} | {r3} ]`\nYou lost **₱{bet}**."

    save_data("economy.json", ECONOMY)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="mines", description="Play risk mines")
async def slash_mines(interaction: discord.Interaction, bet: int, mines_count: int):
    user_id = str(interaction.user.id)
    if not (1 <= mines_count <= 24):
        return await interaction.response.send_message("❌ Mines count must be between 1 and 24.", ephemeral=True)
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await interaction.response.send_message("❌ Invalid bet or insufficient funds.", ephemeral=True)

    ECONOMY[user_id] -= bet
    safe_tiles = 25 - mines_count
    win_chance = 0.05 if safe_tiles < 3 else (safe_tiles / 25) * ((safe_tiles - 1) / 24) * ((safe_tiles - 2) / 23)

    embed = discord.Embed(title="💣 Mines Result")
    if random.random() <= win_chance:
        multiplier = round(25 / safe_tiles, 2)
        winnings = int(bet * multiplier)
        ECONOMY[user_id] += winnings
        embed.color = discord.Color.green()
        embed.description = f"You successfully navigated the minefield!\nCashed out at **{multiplier}x** for **₱{winnings}**!"
    else:
        embed.color = discord.Color.red()
        embed.description = f"**BOOM!** You hit a mine and lost your bet of **₱{bet}**."

    save_data("economy.json", ECONOMY)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rob", description="Try to rob Powoncy from another user")
async def slash_rob(interaction: discord.Interaction, target: discord.Member):
    user_id = str(interaction.user.id)
    target_id = str(target.id)

    if user_id == target_id:
        return await interaction.response.send_message("❌ You can't rob yourself!", ephemeral=True)

    user_bal = ECONOMY.get(user_id, 0)
    target_bal = ECONOMY.get(target_id, 0)

    if user_bal < 50:
        return await interaction.response.send_message("❌ You need at least ₱50 as collateral.", ephemeral=True)
    if target_bal < 50:
        return await interaction.response.send_message("❌ They don't have enough Powoncy!", ephemeral=True)

    if random.choice([True, False]):
        stolen = int(target_bal * random.uniform(0.1, 0.3))
        ECONOMY[user_id] += stolen
        ECONOMY[target_id] -= stolen
        embed = discord.Embed(description=f"🥷 **SUCCESS!** You robbed {target.mention} and got **₱{stolen}**!", color=discord.Color.green())
    else:
        fine = int(user_bal * random.uniform(0.1, 0.2))
        ECONOMY[user_id] -= fine
        embed = discord.Embed(description=f"🚨 **CAUGHT!** You failed to rob {target.mention} and paid **₱{fine}** fine!", color=discord.Color.red())

    save_data("economy.json", ECONOMY)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="store", description="View the VacantMC Store and Rank Hierarchy")
async def slash_store(interaction: discord.Interaction):
    embed = discord.Embed(title="🛒 VacantMC Store & Rank Order", color=discord.Color.gold())
    
    sorted_products = sorted(PRODUCTS.items(), key=lambda x: x[1]['rank_order'])
    rank_text = ""
    other_text = ""
    
    for key, item in sorted_products:
        if item['type'] == 'rank':
            rank_text += f"**{item['rank_order']}. {item['name']}** (`{key}`) - ₱{item['price']}\n"
        else:
            other_text += f"**{item['name']}** (`{key}`) - ₱{item['price']}\n"
            
    embed.add_field(name="🏆 Rank Order Hierarchy", value=rank_text or "No ranks available.", inline=False)
    embed.add_field(name="🎁 Other Items", value=other_text or "No other items.", inline=False)
    embed.set_footer(text="Use /po <product> to order or /claimrank <product> to buy instantly.")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="gencode", description="Generate a 4-digit redeem code (Admin Only)")
@app_commands.describe(reward_type="Choose reward (powoncy, vip, mvp, legend, nitro, mcfa)")
async def slash_gencode(interaction: discord.Interaction, reward_type: str, quantity: int = 1, uses: int = 1, custom_code: str = None):
    if not can_gencode(interaction.user.id, interaction.guild):
        return await interaction.response.send_message("❌ You must be a bot owner or a server administrator in a whitelisted server.", ephemeral=True)
    
    valid_types = ["powoncy"] + list(PRODUCTS.keys())
    reward_type = reward_type.lower()
    
    if reward_type not in valid_types:
        return await interaction.response.send_message(f"❌ Invalid reward type. Choose from: `{', '.join(valid_types)}`", ephemeral=True)
        
    if quantity <= 0 or uses <= 0:
        return await interaction.response.send_message("❌ Quantity and uses must be positive numbers.", ephemeral=True)
        
    if custom_code and len(custom_code) != 4:
        return await interaction.response.send_message("❌ Custom code must be exactly 4 characters.", ephemeral=True)
        
    code = custom_code.upper() if custom_code else ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    if code in CODES:
        return await interaction.response.send_message(f"❌ Code `{code}` already exists.", ephemeral=True)
        
    CODES[code] = {"reward_type": reward_type, "amount": quantity, "uses": uses, "used_by": []}
    save_data("codes.json", CODES)
    
    embed = discord.Embed(description=f"🎟️ **4-Digit Code Generated:** `{code}`\n**Reward:** {quantity}x {reward_type.upper()}\n**Uses:** {uses}", color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="redeem", description="Redeem a 4-digit code")
async def slash_redeem(interaction: discord.Interaction, code: str):
    code = code.upper()
    user_id = str(interaction.user.id)
    
    if len(code) != 4:
        return await interaction.response.send_message("❌ Redeem codes are strictly 4 characters long.", ephemeral=True)
    
    if code not in CODES:
        return await interaction.response.send_message("❌ Invalid or expired redeem code.", ephemeral=True)
        
    code_data = CODES[code]
    if interaction.user.id in code_data["used_by"]:
        return await interaction.response.send_message("❌ You have already claimed this code.", ephemeral=True)
        
    if code_data["uses"] <= 0:
        if code in CODES:
            del CODES[code]
            save_data("codes.json", CODES)
        return await interaction.response.send_message("❌ This code has reached its maximum uses and expired.", ephemeral=True)
        
    reward_type = code_data.get("reward_type", "powoncy")
    amount = code_data["amount"]
    
    if reward_type == "powoncy":
        ECONOMY[user_id] = ECONOMY.get(user_id, 0) + amount
        save_data("economy.json", ECONOMY)
        embed = discord.Embed(description=f"🎉 Successfully redeemed code! Added **₱{amount}** to your balance.", color=discord.Color.green())
    else:
        user_inv = INVENTORY.get(user_id, {})
        user_inv[reward_type] = user_inv.get(reward_type, 0) + amount
        INVENTORY[user_id] = user_inv
        save_data("inventory.json", INVENTORY)
        embed = discord.Embed(description=f"🎉 Code Redeemed! You received **{amount}x {reward_type.upper()}**! Check your `/inventory`.", color=discord.Color.green())
        
    code_data["uses"] -= 1
    code_data["used_by"].append(interaction.user.id)
    if code_data["uses"] <= 0: 
        if code in CODES:
            del CODES[code]
    save_data("codes.json", CODES)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="work", description="Work for some Powoncy ₱")
async def slash_work(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    earned = random.randint(20, 150)
    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + earned
    save_data("economy.json", ECONOMY)
    
    embed = discord.Embed(description=f"💼 You worked hard and earned **₱{earned}** Powoncy!", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="bj", description="Play Blackjack")
async def slash_bj(interaction: discord.Interaction, bet: int):
    user_id = str(interaction.user.id)
    if ECONOMY.get(user_id, 0) < bet or bet <= 0:
        return await interaction.response.send_message("❌ Invalid bet or insufficient funds.", ephemeral=True)
    
    ECONOMY[user_id] -= bet
    save_data("economy.json", ECONOMY)
    
    view = BlackjackView(interaction.user.id, bet)
    embed = discord.Embed(
        title="🃏 Blackjack",
        description=f"{interaction.user.mention}, you drew a total of **{view.player_total}**.\nDealer is showing **{view.dealer_total - random.randint(2,6)}**.\nWhat will you do?",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()

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
    
    embed = discord.Embed(description=f"✅ Order placed for **{item['name']}** (₱{item['price']})!", color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)

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
    
    user_inv = INVENTORY.get(user_id, {})
    user_inv[product_key] = user_inv.get(product_key, 0) + 1
    INVENTORY[user_id] = user_inv
    
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
    save_data("inventory.json", INVENTORY)
    save_data("orders.json", ORDERS)
    
    embed = discord.Embed(description=f"🎉 Successfully purchased **{item['name']}** for **₱{price}**! Check your `/inventory`.", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="bal", description="Check your ₱ Powoncy balance")
async def slash_bal(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    balance = ECONOMY.get(user_id, 0)
    
    embed = discord.Embed(description=f"💰 You have **₱{balance}** Powoncy!", color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="daily", description="Claim daily Powoncy ₱")
async def slash_daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = time.time()
    last_claim = DAILY_COOLDOWNS.get(user_id, 0)

    if now - last_claim < 86400:
        remaining_sec = int(86400 - (now - last_claim))
        hours, remainder = divmod(remaining_sec, 3600)
        minutes, _ = divmod(remainder, 60)
        return await interaction.response.send_message(f"⏳ Wait **{hours}h {minutes}m** to claim again!", ephemeral=True)

    ECONOMY[user_id] = ECONOMY.get(user_id, 0) + 100
    DAILY_COOLDOWNS[user_id] = now
    save_data("economy.json", ECONOMY)
    save_data("cooldowns.json", DAILY_COOLDOWNS)
    
    embed = discord.Embed(description="✅ Claimed daily **₱100** Powoncy!", color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)

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
