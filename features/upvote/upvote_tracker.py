import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Server listing sites with their URLs
SERVER_SITES = {
    "top.gg": {
        "url": "https://top.gg/discord/servers/543744500728799233/vote",
        "emoji": "⬆️"
    },
    "disboard.org": {
        "url": "https://disboard.org/server/859736561830592522",
        "emoji": "⬆️"
    }
}

class UpvoteView(ui.View):
    def __init__(self, server_id):
        super().__init__(timeout=None)  # Persistent view
        self.server_id = server_id
        self.add_buttons()

    def add_buttons(self):
        for site, config in SERVER_SITES.items():
            self.add_item(UpvoteButton(
                site=site,
                url=config['url'].format(server_id=self.server_id),
                emoji=config['emoji']
            ))

class UpvoteButton(ui.Button):
    def __init__(self, site, url, emoji):
        super().__init__(
            label=f"Upvote on {site}",
            url=url,
            style=discord.ButtonStyle.link,
            emoji=emoji
        )

class UpvoteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server_id = os.getenv('SERVER_ID')  # Your server ID

    @app_commands.command(name="upvote", description="Upvote/Review our server to help us grow!")
    async def upvote_command(self, interaction: discord.Interaction):
        """Main upvote command with interactive buttons"""
        embed = discord.Embed(
            title="Review/Upvote Our Server!",
            description="Help grow our community by reviewing us on these sites:",
            color=discord.Color.green()
        )
        
        for site, config in SERVER_SITES.items():
            embed.add_field(
                name=site,
                value=f"[Click here to review/upvote]({config['url'].format(server_id=self.server_id)})",
                inline=False
            )
        
        embed.set_footer(text="Thank you for supporting our server!")
        await interaction.response.send_message(
            embed=embed,
            view=UpvoteView(self.server_id),
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(UpvoteTracker(bot))