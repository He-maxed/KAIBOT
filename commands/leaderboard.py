import discord
from discord import app_commands
from discord.ext import commands
from database.coin_db import get_top_balances, get_balance

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_server_member_ids(self, guild):
        """Fetch all server member IDs"""
        if not guild.chunked:
            await guild.chunk()
        return {str(member.id) for member in guild.members}

    async def get_ranked_server_users(self, guild, limit=None):
        """Get all users with their ranks, filtered to server members"""
        all_users = get_top_balances(limit or 1000)
        server_member_ids = await self.get_server_member_ids(guild)
        
        ranked_users = []
        current_rank = 0
        last_balance = None
        real_rank = 0
        
        for user_id, balance in all_users:
            if str(user_id) in server_member_ids:
                real_rank += 1
                if balance != last_balance:
                    current_rank = real_rank
                ranked_users.append({
                    'user_id': user_id,
                    'balance': balance,
                    'rank': current_rank
                })
                last_balance = balance
                
        return ranked_users

    @app_commands.command(name="leaderboard", description="Show the top smiles holders in this server")
    @app_commands.describe(count="Number of top users to display (default 10)")
    async def leaderboard(self, interaction: discord.Interaction, count: int = 10):
        await interaction.response.defer()
        
        ranked_users = await self.get_ranked_server_users(interaction.guild, count)
        
        if not ranked_users:
            await interaction.followup.send("No server members found in the leaderboard.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 Server smiles Leaderboard",
            color=discord.Color.gold()
        )

        for user in ranked_users[:count]:
            member = interaction.guild.get_member(int(user['user_id']))
            display_name = member.display_name if member else f"Unknown User ({user['user_id']})"
            embed.add_field(
                name=f"#{user['rank']} {display_name}",
                value=f"💰 {user['balance']} smiles",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="rank", description="Check your smiles rank in this server")
    async def slash_rank(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        ranked_users = await self.get_ranked_server_users(interaction.guild)
        user_id = str(interaction.user.id)
        
        user_data = next((u for u in ranked_users if str(u['user_id']) == user_id), None)
        
        if user_data:
            embed = discord.Embed(
                title="Your smiles Rank",
                description=(
                    f"🏅 **Rank:** #{user_data['rank']}\n"
                    f"💰 **Balance:** {user_data['balance']} smiles\n"
                    f"👑 **Top {'%'}:** {self.calculate_top_percentage(user_data['rank'], len(ranked_users))}%"
                ),
                color=discord.Color.gold()
            )
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url
            )
            await interaction.followup.send(embed=embed)
        else:
            balance = get_balance(user_id)
            await interaction.followup.send(
                f"You're not ranked yet! Your balance: {balance} smiles",
                ephemeral=True
            )

    @commands.command(name="leaderboard")
    async def legacy_leaderboard(self, ctx, count: int = 10):
        """Show the top smiles holders in this server. Usage: !leaderboard [count]"""
        ranked_users = await self.get_ranked_server_users(ctx.guild, count)
        
        if not ranked_users:
            await ctx.send("No server members found in the leaderboard.")
            return

        embed = discord.Embed(
            title="🏆 Server smiles Leaderboard",
            color=discord.Color.gold()
        )

        for user in ranked_users[:count]:
            member = ctx.guild.get_member(int(user['user_id']))
            display_name = member.display_name if member else f"Unknown User ({user['user_id']})"
            embed.add_field(
                name=f"#{user['rank']} {display_name}",
                value=f"💰 {user['balance']} smiles",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name="rank")
    async def legacy_rank(self, ctx):
        """Check your smiles rank in this server. Usage: !rank"""
        ranked_users = await self.get_ranked_server_users(ctx.guild)
        user_id = str(ctx.author.id)
        
        user_data = next((u for u in ranked_users if str(u['user_id']) == user_id), None)
        
        if user_data:
            embed = discord.Embed(
                title="Your smiles Rank",
                description=(
                    f"🏅 **Rank:** #{user_data['rank']}\n"
                    f"💰 **Balance:** {user_data['balance']} smiles\n"
                    f"👑 **Top {'%'}:** {self.calculate_top_percentage(user_data['rank'], len(ranked_users))}%"
                ),
                color=discord.Color.gold()
            )
            embed.set_author(
                name=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.url
            )
            await ctx.send(embed=embed)
        else:
            balance = get_user_balance(user_id)
            await ctx.send(f"You're not ranked yet! Your balance: {balance} smiles")

    def calculate_top_percentage(self, rank, total_users):
        """Calculate what percentage of users you're above"""
        if total_users == 0:
            return 0
        return round((1 - (rank / total_users)) * 100, 1)

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))