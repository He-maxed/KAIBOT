import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from typing import Optional
from database.coin_db import get_balance, change_balance 

SHOP_DATA_FILE = 'database/shop_items.json'
TICKETS_FILE = 'database/shop_tickets.json'
TICKETS_CHANNEL_ID = os.getenv("TICKETS_CHANNEL_ID")  # Set your dedicated channel ID here

# Ensure data files exist
for file in [SHOP_DATA_FILE, TICKETS_FILE]:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump({}, f)

def load_data(file):
    with open(file, 'r') as f:
        return json.load(f)

def save_data(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

class BuyButton(discord.ui.Button):
    def __init__(self, item_id):
        super().__init__(
            style=discord.ButtonStyle.green,
            label="Purchase",
            custom_id=f"buy_{item_id}"
        )
        self.item_id = item_id

    async def callback(self, interaction: discord.Interaction):
        shop_data = load_data(SHOP_DATA_FILE)
        item = shop_data.get(self.item_id)
        
        if not item:
            return await interaction.response.send_message(
                "❌ This item is no longer available", 
                ephemeral=True
            )

        user_id = str(interaction.user.id)
        price = item['price']
        role_id = item.get('role_id')

        if get_balance(user_id) < price:
            return await interaction.response.send_message(
                f"❌ You need {price - get_balance(user_id)} more smiles!",
                ephemeral=True
            )

        change_balance(user_id, -price)

        if role_id:
            role = interaction.guild.get_role(role_id)
            if role:
                if role in interaction.user.roles:
                    return await interaction.response.send_message(
                        "❌ You already own this role",
                        ephemeral=True
                    )
                await interaction.user.add_roles(role)
                await interaction.response.send_message(
                    f"✅ Purchased **{item['title']}** for {price} smiles!",
                    ephemeral=True
                )
                return

        # No role - create ticket
        tickets = load_data(TICKETS_FILE)
        ticket_id = f"ticket_{interaction.id}"
        
        tickets[ticket_id] = {
            "user_id": user_id,
            "username": str(interaction.user),
            "item": item['title'],
            "price": price,
            "status": "open",
            "timestamp": str(discord.utils.utcnow())
        }
        save_data(TICKETS_FILE, tickets)

        # Notify in tickets channel
        channel = interaction.guild.get_channel(TICKETS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="🛒 New Shop Ticket",
                description=f"{interaction.user.mention} purchased **{item['title']}**",
                color=discord.Color.orange()
            )
            embed.add_field(name="Price", value=f"{price} smiles")
            embed.add_field(name="Ticket ID", value=ticket_id)
            embed.set_footer(text=f"User ID: {user_id}")
            await channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Purchased **{item['title']}** for {price} smiles!\n"
            "An admin will process your request shortly.",
            ephemeral=True
        )

class ShopItemView(discord.ui.View):
    def __init__(self, item_id):
        super().__init__(timeout=None)
        self.add_item(BuyButton(item_id))

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create_shop_item", description="Create a new shop listing")
    @app_commands.describe(
        title="Item name",
        description="Item description",
        price="Price in smiles",
        role="Role ID or name (optional)",
        image="Optional banner image (attach file)"
    )
    async def create_shop_item(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        price: int,
        role: str = None,
        image: Optional[discord.Attachment] = None
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Administrator permission required",
                ephemeral=True
            )

        role_id = None
        if role:
            resolved_role = await self.resolve_role(interaction.guild, role)
            if not resolved_role:
                return await interaction.response.send_message(
                    "❌ Couldn't find that role",
                    ephemeral=True
                )
            role_id = resolved_role.id

        item_id = f"item_{interaction.id}"
        shop_data = load_data(SHOP_DATA_FILE)
        
        shop_data[item_id] = {
            "title": title,
            "description": description,
            "price": price,
            "role_id": role_id,
            "image_url": image.url if image else None
        }
        save_data(SHOP_DATA_FILE, shop_data)

        embed = discord.Embed(
            title=f"\n",
            description=f"# **🛍️ {title}**",
            color=discord.Color.gold()
        )
        embed.add_field(name="**Price**", value=f"**{price} smiles**")
        if role_id:
            embed.add_field(name="**Role**", value=f"<@&{role_id}>")
        if image:
            embed.set_image(url=image.url)

        await interaction.channel.send(
            embed=embed,
            view=ShopItemView(item_id)
        )
        await interaction.response.send_message(
            "✅ Shop item created!",
            ephemeral=True
        )
        

    @app_commands.command(name="list_shop_tickets", description="List all open shop tickets")
    async def list_shop_tickets(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Administrator permission required",
                ephemeral=True
            )

        tickets = load_data(TICKETS_FILE)
        open_tickets = {k: v for k, v in tickets.items() if v['status'] == 'open'}

        if not open_tickets:
            return await interaction.response.send_message(
                "ℹ️ No open tickets found.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="📝 Open Shop Tickets",
            color=discord.Color.blue()
        )

        for ticket_id, data in open_tickets.items():
            embed.add_field(
                name=f"Ticket {ticket_id}",
                value=(
                    f"**User:** {data['username']}\n"
                    f"**Item:** {data['item']}\n"
                    f"**Price:** {data['price']} smiles\n"
                    f"**Date:** {data['timestamp']}"
                ),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="close_shop_ticket", description="Close a shop ticket")
    @app_commands.describe(
        user="User who made the purchase",
        notes="Optional notes about fulfillment"
    )
    async def close_shop_ticket(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        notes: str = None
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Administrator permission required",
                ephemeral=True
            )

        tickets = load_data(TICKETS_FILE)
        user_tickets = {
            k: v for k, v in tickets.items() 
            if v['user_id'] == str(user.id) and v['status'] == 'open'
        }

        if not user_tickets:
            return await interaction.response.send_message(
                f"❌ No open tickets found for {user.mention}",
                ephemeral=True
            )

        # Close all open tickets for this user
        for ticket_id in user_tickets:
            tickets[ticket_id]['status'] = 'closed'
            tickets[ticket_id]['closed_by'] = str(interaction.user)
            tickets[ticket_id]['closed_at'] = str(discord.utils.utcnow())
            if notes:
                tickets[ticket_id]['notes'] = notes

        save_data(TICKETS_FILE, tickets)

        embed = discord.Embed(
            title="✅ Ticket Closed",
            description=f"Closed {len(user_tickets)} ticket(s) for {user.mention}",
            color=discord.Color.green()
        )
        if notes:
            embed.add_field(name="Notes", value=notes, inline=False)
        
        await interaction.response.send_message(embed=embed)

        # Notify user
        try:
            await user.send(
                f"Your shop purchase(s) have been fulfilled!\n"
                f"Closed by: {interaction.user.mention}\n"
                f"{f'Notes: {notes}' if notes else ''}"
            )
        except discord.Forbidden:
            pass

    async def resolve_role(self, guild: discord.Guild, role_input: str) -> Optional[discord.Role]:
        """Resolve role from ID or name"""
        try:
            # Try as ID first
            role = guild.get_role(int(role_input))
            if role:
                return role
            
            # Try as name
            return discord.utils.get(guild.roles, name=role_input)
        except ValueError:
            return None

    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent views
        for item_id in load_data(SHOP_DATA_FILE):
            self.bot.add_view(ShopItemView(item_id))

async def setup(bot):
    await bot.add_cog(Shop(bot))