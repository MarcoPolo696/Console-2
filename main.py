import discord

@bot.tree.command(name="kick", description="Kick member")
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

@bot.tree.command(name="ban", description="Ban member")
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
bot.run(TOKEN)
