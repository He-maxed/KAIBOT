import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import os
from dotenv import load_dotenv
from database.coin_db import change_balance, get_balance, get_top_balances
import time

class EarnDaily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.earn_cooldowns = {}
        self.daily_cooldowns = {}
        self.repeat_count = {}
        self.last_sender = None
        load_dotenv()
        self.ignored_channels = self._load_ignored_channels()

    def _load_ignored_channels(self):
        """Load ignored channel IDs from .env"""
        ignored = os.getenv("IGNORED_CHANNELS", "")
        return [int(x.strip()) for x in ignored.split(",") if x.strip()]

    def is_on_cooldown(self, user_id: int, cooldown_seconds: int, cooldown_map: dict):
        now = time.time()
        last_used = cooldown_map.get(user_id, 0)
        return (now - last_used < cooldown_seconds, last_used + cooldown_seconds - now)

    def format_time_left(self, seconds_left, command_type):
        if command_type == "daily":
            hours = seconds_left // 3600
            minutes = (seconds_left % 3600) // 60
            return f"{int(hours)}h {int(minutes)}m"
        else:  # earn
            minutes = seconds_left // 60
            seconds = seconds_left % 60
            return f"{int(minutes)}m {int(seconds)}s"

    async def get_user_rank(self, user_id):
        top_users = get_top_balances(1000)
        for rank, (uid, _) in enumerate(top_users, start=1):
            if str(uid) == str(user_id):
                return rank
        return None

    async def add_smiles(self, user: discord.User, amount: int):
        change_balance(user.id, amount)

    class BalanceView(View):
        def __init__(self, cog):
            super().__init__(timeout=None)
            self.cog = cog
            
            # Earn Button
            earn_btn = Button(label="Earn Smiles", style=discord.ButtonStyle.green, emoji="💰")
            earn_btn.callback = self.earn_callback
            self.add_item(earn_btn)
            
            # Daily Button
            daily_btn = Button(label="Daily Reward", style=discord.ButtonStyle.blurple, emoji="🎁")
            daily_btn.callback = self.daily_callback
            self.add_item(daily_btn)
        
        async def earn_callback(self, interaction: discord.Interaction):
            user_id = interaction.user.id
            on_cooldown, time_left = self.cog.is_on_cooldown(user_id, 3600, self.cog.earn_cooldowns)
            if on_cooldown:
                readable_time = self.cog.format_time_left(time_left, "earn")
                await interaction.response.send_message(
                    f"⏳ You can earn again in {readable_time}\n"
                    f"🕒 Try again at <t:{int(time.time() + time_left)}:t>",
                    ephemeral=True
                )
                return

            await interaction.response.defer()
            await self.cog.add_smiles(interaction.user, 50)
            self.cog.earn_cooldowns[user_id] = time.time()
            new_balance = get_balance(user_id)
            await interaction.followup.send(
                f"🎉 You earned 50 smiles!\n"
                f"💰 New balance: `{new_balance}` smiles\n"
                f"⏳ Next earn in 60 minutes (<t:{int(time.time() + 3600)}:R>)"
            )
        
        async def daily_callback(self, interaction: discord.Interaction):
            user_id = interaction.user.id
            on_cooldown, time_left = self.cog.is_on_cooldown(user_id, 86400, self.cog.daily_cooldowns)
            if on_cooldown:
                readable_time = self.cog.format_time_left(time_left, "daily")
                await interaction.response.send_message(
                    f"⏳ You can claim daily again in {readable_time}\n"
                    f"🗓️ Next daily at <t:{int(time.time() + time_left)}:F>",
                    ephemeral=True
                )
                return

            await interaction.response.defer()
            await self.cog.add_smiles(interaction.user, 50)
            self.cog.daily_cooldowns[user_id] = time.time()
            new_balance = get_balance(user_id)
            await interaction.followup.send(
                f"🎁 Daily reward claimed! +50 smiles\n"
                f"💰 New balance: `{new_balance}` smiles\n"
                f"⏳ Next daily in 24 hours (<t:{int(time.time() + 86400)}:R>)"
            )

    # Slash Commands
    @app_commands.command(name="earn", description="Earn 50 smiles (1 hour cooldown)")
    async def slash_earn(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        on_cooldown, time_left = self.is_on_cooldown(user_id, 3600, self.earn_cooldowns)
        if on_cooldown:
            readable_time = self.format_time_left(time_left, "earn")
            await interaction.response.send_message(
                f"⏳ You can earn again in {readable_time}\n"
                f"🕒 Try again at <t:{int(time.time() + time_left)}:t>",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        await self.add_smiles(interaction.user, 50)
        self.earn_cooldowns[user_id] = time.time()
        new_balance = get_balance(user_id)
        await interaction.followup.send(
            f"🎉 You earned 50 smiles!\n"
            f"💰 New balance: `{new_balance}` smiles\n"
            f"⏳ Next earn in 60 minutes (<t:{int(time.time() + 3600)}:R>)"
        )

    @app_commands.command(name="daily", description="Claim your daily 50 smiles (24-hour cooldown)")
    async def slash_daily(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        on_cooldown, time_left = self.is_on_cooldown(user_id, 86400, self.daily_cooldowns)
        if on_cooldown:
            readable_time = self.format_time_left(time_left, "daily")
            await interaction.response.send_message(
                f"⏳ You can claim daily again in {readable_time}\n"
                f"🗓️ Next daily at <t:{int(time.time() + time_left)}:F>",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        await self.add_smiles(interaction.user, 50)
        self.daily_cooldowns[user_id] = time.time()
        new_balance = get_balance(user_id)
        await interaction.followup.send(
            f"🎁 Daily reward claimed! +50 smiles\n"
            f"💰 New balance: `{new_balance}` smiles\n"
            f"⏳ Next daily in 24 hours (<t:{int(time.time() + 86400)}:R>)"
        )

    @app_commands.command(name="balance", description="Check your or another user's smiles balance and rank")
    @app_commands.describe(user="The user to check (leave empty for yourself)")
    async def slash_balance(self, interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        user_id = target.id
        bal = get_balance(user_id)
        rank = await self.get_user_rank(user_id)
        
        embed = discord.Embed(
            title=f"{target.display_name}'s Smiles Balance",
            color=discord.Color.gold()
        )
        embed.add_field(name="💰 Balance", value=f"{bal} smiles", inline=True)
        embed.add_field(name="🏆 Rank", value=f"#{rank}" if rank else "Unranked", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        
        # Use discord.utils.MISSING instead of None
        view = discord.utils.MISSING if target != interaction.user else self.BalanceView(self)
        await interaction.response.send_message(embed=embed, view=view)

    # Legacy Commands
    @commands.command(name="earn")
    async def legacy_earn(self, ctx: commands.Context):
        user_id = ctx.author.id
        on_cooldown, time_left = self.is_on_cooldown(user_id, 3600, self.earn_cooldowns)
        if on_cooldown:
            readable_time = self.format_time_left(time_left, "earn")
            await ctx.send(
                f"⏳ You can earn again in {readable_time}\n"
                f"🕒 Try again at <t:{int(time.time() + time_left)}:t>"
            )
            return

        await self.add_smiles(ctx.author, 50)
        self.earn_cooldowns[user_id] = time.time()
        new_balance = get_balance(user_id)
        await ctx.send(
            f"🎉 You earned 50 smiles!\n"
            f"💰 New balance: `{new_balance}` smiles\n"
            f"⏳ Next earn in 60 minutes (<t:{int(time.time() + 3600)}:R>)"
        )

    @commands.command(name="daily")
    async def legacy_daily(self, ctx: commands.Context):
        user_id = ctx.author.id
        on_cooldown, time_left = self.is_on_cooldown(user_id, 86400, self.daily_cooldowns)
        if on_cooldown:
            readable_time = self.format_time_left(time_left, "daily")
            await ctx.send(
                f"⏳ You can claim daily again in {readable_time}\n"
                f"🗓️ Next daily at <t:{int(time.time() + time_left)}:F>"
            )
            return

        await self.add_smiles(ctx.author, 50)
        self.daily_cooldowns[user_id] = time.time()
        new_balance = get_balance(user_id)
        await ctx.send(
            f"🎁 Daily reward claimed! +50 smiles\n"
            f"💰 New balance: `{new_balance}` smiles\n"
            f"⏳ Next daily in 24 hours (<t:{int(time.time() + 86400)}:R>)"
        )
    
    @commands.command(name="balance")
    async def legacy_balance(self, ctx: commands.Context, user: discord.User = None):
        target = user or ctx.author
        user_id = target.id
        bal = get_balance(user_id)
        rank = await self.get_user_rank(user_id)
        
        embed = discord.Embed(
            title=f"{target.display_name}'s Smiles Balance",
            color=discord.Color.gold()
        )
        embed.add_field(name="💰 Balance", value=f"{bal} smiles", inline=True)
        embed.add_field(name="🏆 Rank", value=f"#{rank}" if rank else "Unranked", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        
        # Create empty view if checking another user's balance
        view = discord.utils.MISSING if target != ctx.author else self.BalanceView(self)
        await ctx.send(embed=embed, view=view)

    # Message earning system
    @commands.Cog.listener()
    async def on_message(self, message):
        if (message.author.bot or 
            not message.guild or 
            message.channel.id in self.ignored_channels or
            message.content.startswith(('!', '/'))):
            return

        # Always give 1 coin per valid message
        change_balance(message.author.id, 1)

        # Anti-spam (prevents same user getting multiple coins rapidly)
        if self.last_sender == message.author.id:
            return
        self.last_sender = message.author.id

async def setup(bot):
    await bot.add_cog(EarnDaily(bot))