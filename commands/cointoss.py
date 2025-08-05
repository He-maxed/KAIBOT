import random
from discord.ext import commands
from database.coin_db import get_balance,change_balance

class CoinBet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def process_bet(self, ctx, user_choice, amount):
        user_id = str(ctx.author.id)
        balance = get_balance(user_id)

        if amount <= 0:
            await ctx.send("Bet amount must be positive.")
            return

        if balance < amount:
            await ctx.send("You don't have enough smiles.")
            return

        result = random.choice(["heads", "tails"])
        win = result == user_choice

        if win:
            change_balance(user_id, amount)  # Give back + double
            await ctx.send(f"🪙 It's **{result}**! You won 🎉 and gained `{amount}` smiles.")
        else:
            change_balance(user_id, -amount)  # Deduct only
            await ctx.send(f"🪙 It's **{result}**! You lost 😢 `{amount}` smiles.")

    @commands.command(name="heads")
    async def bet_heads(self, ctx, amount: int):
        await self.process_bet(ctx, "heads", amount)

    @commands.command(name="tails")
    async def bet_tails(self, ctx, amount: int):
        await self.process_bet(ctx, "tails", amount)

async def setup(bot):
    await bot.add_cog(CoinBet(bot))