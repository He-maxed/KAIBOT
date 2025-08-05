import discord
from discord.ext import commands
from discord import app_commands
from database.coin_db import change_balance, get_balance

class AdminGive(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def give_smiles(self, target_user: discord.User, amount: int, context):
        """DRY helper method to handle smile giving logic"""
        change_balance(target_user.id, amount)
        new_balance = get_balance(target_user.id)
        
        response = f"✅ Gave `{amount}` smiles to {target_user.mention}. New balance: `{new_balance}` smiles."
        
        if isinstance(context, commands.Context):
            await context.send(response)
        else:
            await context.response.send_message(response)

    # --- Slash Command: /give <user> <amount> ---
    @app_commands.command(name="give", description="Admin: Give smiles to a user")
    @app_commands.describe(user="User to give smiles to", amount="Amount of smiles to give")
    async def slash_give(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        await self.give_smiles(user, amount, interaction)

    # --- Legacy Command: !give <amount> @user ---
    @commands.command(name="give")
    @commands.has_permissions(manage_messages=True)
    async def legacy_give(self, ctx: commands.Context, amount: int, member: discord.Member):
        await self.give_smiles(member, amount, ctx)

    @legacy_give.error
    async def give_error(self, ctx, error):
        error_messages = {
            commands.MissingRequiredArgument: "⚠️ Usage: `!give <amount> @user`",
            commands.BadArgument: "⚠️ Make sure to provide a number and mention a valid user.",
            commands.MissingPermissions: "❌ You don't have permission to use this command."
        }
        
        message = error_messages.get(type(error), "⚠️ An error occurred.")
        await ctx.send(message)

async def setup(bot):
    await bot.add_cog(AdminGive(bot))