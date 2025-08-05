import asyncio
import os
import json
import time
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import pytz
from database.coin_db import get_balance, change_balance

AUCTION_FILE = "database/current_auction.json"
WIN_TRACKER_FILE = "database/win_tracker.json"
CONFIG_FILE = "database/auction_config.json"


def get_embed_color():
    # Always use #d9fc32
    return 0xd9fc32


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f)


def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)


def can_win(user_id):
    wins = load_json(WIN_TRACKER_FILE)
    return wins.get(str(user_id), 0) < 4


def add_win(user_id):
    wins = load_json(WIN_TRACKER_FILE)
    uid = str(user_id)
    wins[uid] = wins.get(uid, 0) + 1
    save_json(WIN_TRACKER_FILE, wins)

def format_thread_bid_message(user, amount):
    return f"{user.mention} placed a bid of **{amount}** smiles!"

def format_bid_message(user, amount, item):
    return f"✅ {user.mention}, your bid of **{amount}** smiles has been placed for **{item}**!"


class BidModal(discord.ui.Modal, title="Place Your Bid"):
    amount = discord.ui.TextInput(label="Bid Amount", placeholder="Enter your bid (number)", required=True)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
        except ValueError:
            return await interaction.response.send_message("❌ Please enter a valid number.", ephemeral=True)

        cog = interaction.client.get_cog("AuctionManager")
        if not cog:
            return await interaction.response.send_message("❌ Auction system not found.", ephemeral=True)

        # Defer the response here
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Pass the interaction.followup.send as the response method
            await cog._place_bid(
                interaction.user, 
                amount, 
                lambda msg: interaction.followup.send(msg, ephemeral=True)
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Something went wrong: {e}", ephemeral=True)


class BidView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.add_item(BidButton(bot))

class BidButton(Button):
    def __init__(self, bot):
        super().__init__(label="Place Bid", style=discord.ButtonStyle.green, custom_id="auction_place_bid")
        self.bot = bot
        self.cooldowns = {}  # 1 bid per 30 seconds per user

    async def callback(self, interaction: discord.Interaction):
        # Check cooldown
        current_time = time.time()
        last_bid = self.cooldowns.get(interaction.user.id, 0)
        
        if current_time - last_bid < 30:  # 30 second cooldown
            remaining = 30 - (current_time - last_bid)
            return await interaction.response.send_message(
                f"⏱️ You're bidding too fast! Please wait {remaining:.1f} seconds.",
                ephemeral=True
            )

        self.cooldowns[interaction.user.id] = current_time
        await interaction.response.send_modal(BidModal(self.bot))


async def send_auction_embed(channel, auction, bot):
    embed = await build_auction_embed(auction, bot)
    view = BidView(bot)
    msg = await channel.send(embed=embed, view=view)
    return msg

def format_countdown(end_time):
    # Convert to local time
    local_tz = pytz.timezone('UTC')  # Default to UTC
    now = datetime.now(local_tz)
    end_time_local = end_time.astimezone(local_tz)
    
    remaining = end_time_local - now
    if remaining.total_seconds() > 0:
        days = remaining.days
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"⏳ REMAINING TIME : {days}d {hours}h {minutes}m"
    else:
        return "🛑 AUCTION ENDED"

async def get_bidder_mention(bot, bidder_id):
    if bidder_id:
        try:
            user = bot.get_user(int(bidder_id))
            if user is None:
                user = await bot.fetch_user(int(bidder_id))
            return user.mention
        except Exception:
            return f"`{bidder_id}`"
    return "None"

async def build_auction_embed(auction, bot):
    # Create the main embed
    embed = discord.Embed(
        title=f"**{auction['item']}**",
        color=get_embed_color(),
        description=""
    )

    # Handle description (optional)

    description = auction.get("description", "")
    if description:
        embed.add_field(
            name="\u200b", 
            value=f"```{description}```", 
            inline=False
    )
    else:
        embed.add_field(
            name="\u200b", 
            value="\u200b", 
            inline=False
        )

    
    embed.add_field(
        name="🏷️ MINIMUM BID", 
        value=f"🔴  **{auction['minimum_bid']} smiles**", 
        inline=True
    )
    
    embed.add_field(
        name="😊 CURRENT BID", 
        value=f"🟢  **{auction['highest_bid']} smiles**", 
        inline=True
    )
    
    bidder_mention = await get_bidder_mention(bot, auction.get("highest_bidder"))
    embed.add_field(
        name="👤 BIDDER", 
        value=f"🙋🏻‍♀️  **{bidder_mention}**", 
        inline=False
    )

    embed.add_field(
        name="\u200b", 
        value="", 
        inline=False
    )
    
    end_time = datetime.fromisoformat(auction["end_time"]).replace(tzinfo=pytz.UTC)
    countdown = format_countdown(end_time)
    # Check if auction has ended
    end_time = datetime.fromisoformat(auction["end_time"]).replace(tzinfo=pytz.UTC)
    countdown = format_countdown(end_time)
    
    if countdown == "🛑 AUCTION ENDED":
        embed.add_field(
            name="STATUS",
            value="**🛑 AUCTION HAS ENDED**",
            inline=False
        )
        # Remove the "Ends at" timestamp for ended auctions
    else:
        embed.add_field(
            name="", 
            value=f"**{countdown}**\n\n*Ends at: <t:{int(end_time.timestamp())}:F>*", 
            inline=False
        )

    embed.add_field(
        name="\u200b", 
        value="", 
        inline=False
    )
    # Add images if provided
    if auction.get("image_url"):
        embed.set_thumbnail(url=auction["image_url"])
    if auction.get("banner_url"):
        embed.set_image(url=auction["banner_url"])

    embed.set_footer(text=f"Official Kai Bot")
   #embed.timestamp = datetime.now(pytz.UTC)  # Set the timestamp to now
    return embed

class AuctionManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.live_update_message = None
        self.all_bidders = set()  # Track all users who have bid
        self.pending_refunds = {}  # Track pending refunds for overbid users
        self.bid_cooldowns = {}
        self.auction_message_id = None  # Add this line to track the message ID
        bot.loop.create_task(self.reload_active_auction())
        
    async def reload_active_auction(self):
        """Reload active auction on bot startup"""
        await self.bot.wait_until_ready()
        
        auction = load_json(AUCTION_FILE)
        if not auction:
            return
            
        channel = self.bot.get_channel(auction.get("channel_id"))
        if not channel:
            return
            
        try:
            # Try to fetch the existing message
            self.live_update_message = await channel.fetch_message(auction["message_id"])
            self.auction_message_id = auction["message_id"]
            
            # Restart the countdown
            end_time = datetime.fromisoformat(auction["end_time"]).replace(tzinfo=pytz.UTC)
            self.bot.loop.create_task(self.live_auction_countdown(channel, end_time))
            
        except discord.NotFound:
            # If message not found, create a new one
            self.live_update_message = await send_auction_embed(channel, auction, self.bot)
            auction["message_id"] = self.live_update_message.id
            auction["channel_id"] = channel.id
            save_json(AUCTION_FILE, auction)
            self.bot.loop.create_task(self.live_auction_countdown(channel, end_time))
    
    async def _start_auction(self, ctx_or_interaction, item, description, days, hours, minutes, minimum_bid, is_slash, image_url=None, banner_url=None):
        channel = ctx_or_interaction.channel
        if is_slash:
            await ctx_or_interaction.response.defer()
            
        if os.path.exists(AUCTION_FILE):
            msg = "❌ An auction is already running."
            if is_slash:
                await ctx_or_interaction.followup.send(msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(msg)
            return
            
        try:
            thread = await channel.create_thread(name=f"Auction: {item}", type=discord.ChannelType.public_thread)
            await thread.send(
                f"🎉 **Auction Started!**\n"
                f"🎯 **Item:** {item}\n"
                f"🔖 **Minimum Bid:** {minimum_bid} smiles\n"
            )
        except Exception as e:
            await channel.send(f"❌ Failed to create auction thread: {e}")
            return
            
        total_minutes = days * 24 * 60 + hours * 60 + minutes
        end_time = (datetime.now(pytz.UTC) + timedelta(minutes=total_minutes)).isoformat()
        auction = {
            "item": item,
            "description": description,
            "end_time": end_time,
            "highest_bid": 0,
            "highest_bidder": None,
            "minimum_bid": minimum_bid,
            "image_url": image_url,
            "banner_url": banner_url,
            "thread_id": thread.id,
            "channel_id": channel.id  # Add channel ID to auction data
        }
        
        self.live_update_message = await send_auction_embed(channel, auction, self.bot)
        auction["message_id"] = self.live_update_message.id  # Store message ID
        save_json(AUCTION_FILE, auction)
        
        self.bot.loop.create_task(self.live_auction_countdown(channel, end_time))

    async def notify_outbid_user(self, previous_bidder_id, new_bidder_mention, amount, item):
        """Notify the previous highest bidder they've been outbid"""
        if not previous_bidder_id:
            return
            
        try:
            # Refund the previous bidder
            if previous_bidder_id in self.pending_refunds:
                change_balance(int(previous_bidder_id), self.pending_refunds[previous_bidder_id])
                del self.pending_refunds[previous_bidder_id]

            user = await self.bot.fetch_user(int(previous_bidder_id))
            dm_msg = f"⚠️ You've been outbid by {new_bidder_mention} for **{amount}** smiles on **{item}**! Your bid has been refunded."
            await user.send(dm_msg)
        except Exception as e:
            print(f"Failed to DM outbid notification: {e}")

    async def send_30_minute_warning(self, auction):
        """Send 30-minute warning to all bidders"""
        if not self.all_bidders:
            return
            
        item = auction["item"]
        thread_id = auction.get("thread_id")
        thread = None
        
        # Find the thread
        if thread_id:
            for guild in self.bot.guilds:
                thread = guild.get_thread(thread_id)
                if thread:
                    break
        
        warning_sent = set()
        
        for bidder_id in self.all_bidders:
            try:
                user = await self.bot.fetch_user(int(bidder_id))
                if user.id not in warning_sent:
                    warning_msg = f"⏰ **Auction ending soon!** The '{item}' auction ends in 30 minutes!"
                    try:
                        await user.send(warning_msg)
                    except:
                        # If DM fails, try to mention in thread
                        if thread:
                            await thread.send(f"{user.mention} {warning_msg}")
                    warning_sent.add(user.id)
            except Exception as e:
                print(f"Failed to send 30-minute warning: {e}")
        
        if thread:
            await thread.send("⏰ **Auction ending in 30 minutes!**")

    async def _place_bid(self, user, amount, respond):
        current_time = time.time()
        if user.id in self.bid_cooldowns:
            last_bid = self.bid_cooldowns[user.id]
            if current_time - last_bid < 30:  # 30 second cooldown
                remaining = 30 - (current_time - last_bid)
                return await respond(f"⏱️ Please wait {remaining:.1f} seconds before bidding again")
        
        self.bid_cooldowns[user.id] = current_time
    
        auction = load_json(AUCTION_FILE)
        uid = str(user.id)
        if not auction:
            return await respond("❌ No active auction right now.")  # Remove this line if using modal
        if not can_win(user.id):
            return await respond("🚫 You have reached your 4 wins/month limit.")
        if amount <= auction["highest_bid"]:
            return await respond(f"❌ Your bid must be higher than the current bid: {auction['highest_bid']}")
        if amount < auction.get("minimum_bid", 0):
            return await respond(f"❌ Your bid must be at least the minimum bid: {auction['minimum_bid']}")
    
        # Check user balance including any pending refund from previous bid
        user_balance = get_balance(user.id)
        if uid in self.pending_refunds:
            user_balance += self.pending_refunds[uid]  # Add back pending refund
    
        if user_balance < amount:
            return await respond(f"❌ You don't have enough smiles! Your balance: {user_balance}")
    
        # Track all bidders
        self.all_bidders.add(uid)
    
        # Handle same-user rebid - refund previous bid first
        if uid in self.pending_refunds:
            change_balance(user.id, self.pending_refunds[uid])  # Refund previous bid
            del self.pending_refunds[uid]
    
        # Deduct new bid amount from current user
        change_balance(user.id, -amount)
        self.pending_refunds[uid] = amount  # Track this in case they get outbid
    
        previous_bidder = auction.get("highest_bidder")
        if previous_bidder and previous_bidder != uid:
            await self.notify_outbid_user(
                previous_bidder,
                user.mention,
                amount,
                auction['item']
            )
    
        auction["highest_bid"] = amount
        auction["highest_bidder"] = uid
        save_json(AUCTION_FILE, auction)
    
        thread_id = auction.get("thread_id")
        if thread_id:
            for guild in self.bot.guilds:
                thread = guild.get_thread(thread_id)
                if thread:
                    if previous_bidder and previous_bidder != uid:
                        try:
                            prev_user = await self.bot.fetch_user(int(previous_bidder))
                            await thread.send(f"⚠️ {prev_user.mention}, you've been outbid by {user.mention}!")
                        except:
                            pass
                    await thread.send(format_thread_bid_message(user, amount))
                    break
                
        if self.live_update_message:
            updated_embed = await build_auction_embed(auction, self.bot)
            await self.live_update_message.edit(embed=updated_embed)
    
     # Only send one response
        if not isinstance(respond, type(lambda: None)):  # If not a lambda response
            await respond(format_bid_message(user, amount, auction['item']))

    async def live_auction_countdown(self, channel, end_time_iso):
        while True:
            auction = load_json(AUCTION_FILE)
            if not auction:
                return
                
            end_time = datetime.fromisoformat(auction["end_time"]).replace(tzinfo=pytz.UTC)
            now = datetime.now(pytz.UTC)
            remaining = end_time - now
            
            # Check if 30 minutes remaining
            if 1800 >= remaining.total_seconds() > 1740:  # ~30 minutes left
                await self.send_30_minute_warning(auction)
                
            if remaining.total_seconds() <= 0:
                # Force one final update to show ended status
                if self.live_update_message:
                    updated_embed = await build_auction_embed(auction, self.bot)
                    await self.live_update_message.edit(embed=updated_embed)
                break

            try:
                if self.live_update_message:
                    updated_embed = await build_auction_embed(auction, self.bot)
                    await self.live_update_message.edit(embed=updated_embed)
            except Exception:
                pass

            await asyncio.sleep(30) # Changed from 60 to 30 seconds


            
        # Auction end logic
        auction = load_json(AUCTION_FILE)
        if not auction:
            return
        self.all_bidders.clear()
        winner_id = auction["highest_bidder"]
        item = auction["item"]
        bid = auction["highest_bid"]
        thread_id = auction.get("thread_id")
        
        # Clear any pending refunds (winner keeps their money)
        if winner_id and winner_id in self.pending_refunds:
            del self.pending_refunds[winner_id]
            
        if winner_id:
            add_win(int(winner_id))
            user = await self.bot.fetch_user(int(winner_id))
            end_msg = f"🎉 Auction ended! `{item}` won by {user.mention} for **{bid}** <:smile:123456789012345678>!"
        else:
            end_msg = "⚠️ Auction ended with no bids."
            
            # Refund all pending bids if no winner
            for bidder_id, amount in self.pending_refunds.items():
                change_balance(int(bidder_id), amount)
            self.pending_refunds.clear()
            
        if self.live_update_message:
            await self.live_update_message.edit(content=end_msg)
        await channel.send(end_msg)
        os.remove(AUCTION_FILE)

    # ==== COMMANDS ====
    @app_commands.command(name="startauction", description="Start a new auction (admin only)")
    @app_commands.describe(
        item="Item to auction",
        description="Description of the item (optional)",
        minutes="Minutes",
        hours="Hours (required)",
        minimum_bid="Minimum allowed bid",
        days="Days (optional)",
        thumbnail="(Optional) Thumbnail image attachment",
        banner="(Optional) Banner image attachment"
    )
    async def slash_startauction(
        self, 
        interaction: discord.Interaction,
        item: str,
        description: str = "",
        days: int = 0,
        hours: int = 0,
        minutes: int = 1,
        minimum_bid: int = 0,
        thumbnail: discord.Attachment = None,
        banner: discord.Attachment = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Admins only!", ephemeral=True)
            return

        # Process attachments
        image_url = thumbnail.url if thumbnail else None
        banner_url = banner.url if banner else None

        await self._start_auction(
            interaction, 
            item, 
            description, 
            days, 
            hours, 
            minutes, 
            minimum_bid, 
            is_slash=True,
            image_url=image_url,
            banner_url=banner_url
        )

    @commands.command(name="startauction")
    @commands.has_permissions(administrator=True)
    async def legacy_startauction(
        self, 
        ctx, 
        item: str, 
        description: str = "", 
        days: int = 0, 
        hours: int = 0, 
        minutes: int = 1, 
        minimum_bid: int = 0
    ):
        # Check for attachments
        image_url = None
        banner_url = None

        if ctx.message.attachments:
            # First attachment is thumbnail, second is banner
            if len(ctx.message.attachments) >= 1:
                image_url = ctx.message.attachments[0].url
            if len(ctx.message.attachments) >= 2:
                banner_url = ctx.message.attachments[1].url

        await self._start_auction(
            ctx, 
            item, 
            description, 
            days, 
            hours, 
            minutes, 
            minimum_bid, 
            is_slash=False,
            image_url=image_url,
            banner_url=banner_url
        )

    @app_commands.command(name="bid", description="Place a bid in the current auction")
    @app_commands.describe(amount="The amount of smiles you want to bid")
    async def slash_bid(self, interaction: discord.Interaction, amount: int):
        await self._place_bid(interaction.user, amount, lambda msg: interaction.response.send_message(msg, ephemeral=True))
    
    @commands.command(name="bid")
    async def legacy_bid(self, ctx, amount: int):
        await self._place_bid(ctx.author, amount, lambda msg: ctx.send(msg))

    @app_commands.command(name="cancelauction", description="Cancel the current auction (admin only)")
    @app_commands.describe(confirm="Type YES to confirm cancellation")
    async def slash_cancelauction(self, interaction: discord.Interaction, confirm: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Admins only!", ephemeral=True)
            return
        if confirm != "YES":
            await interaction.response.send_message("❗ Please type YES to confirm cancellation.", ephemeral=True)
            return
        if not os.path.exists(AUCTION_FILE):
            await interaction.response.send_message("❌ No auction is running.", ephemeral=True)
            return
            
        # Refund all pending bids when auction is cancelled
        auction = load_json(AUCTION_FILE)
        for bidder_id, amount in self.pending_refunds.items():
            change_balance(int(bidder_id), amount)
        self.pending_refunds.clear()
        self.all_bidders.clear()
        
        # Force update the embed to show cancelled status
        if self.live_update_message:
            auction["end_time"] = datetime.now(pytz.UTC).isoformat()
            updated_embed = await build_auction_embed(auction, self.bot)
            await self.live_update_message.edit(embed=updated_embed, content="❌ AUCTION CANCELLED BY ADMIN")
        
        os.remove(AUCTION_FILE)
        await interaction.response.send_message("❌ Auction cancelled. All bids have been refunded.", ephemeral=True)
    
    @app_commands.command(name="endauction", description="End the current auction (admin only)")
    @app_commands.describe(confirm="Type YES to confirm ending")
    async def slash_endauction(self, interaction: discord.Interaction, confirm: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Admins only!", ephemeral=True)
            return
        if confirm != "YES":
            await interaction.response.send_message("❗ Please type YES to confirm ending.", ephemeral=True)
            return
        auction = load_json(AUCTION_FILE)
        if not auction:
            await interaction.response.send_message("❌ No auction is running.", ephemeral=True)
            return
            
        self.all_bidders.clear()
        winner_id = auction.get("highest_bidder")
        item = auction.get("item")
        bid = auction.get("highest_bid")
        
        # Clear winner's pending refund (they keep the money)
        if winner_id and winner_id in self.pending_refunds:
            del self.pending_refunds[winner_id]
            
        if winner_id:
            add_win(int(winner_id))
            user = await self.bot.fetch_user(int(winner_id))
            end_msg = f"🎉 Auction ended! `{item}` won by {user.mention} for **{bid}** smiles!"
        else:
            end_msg = "⚠️ Auction ended with no bids."
            
            # Refund all pending bids if no winner
            for bidder_id, amount in self.pending_refunds.items():
                change_balance(int(bidder_id), amount)
            self.pending_refunds.clear()
        
        # Force update the embed to show ended status
        if self.live_update_message:
            # Set end time to now to trigger ended status
            auction["end_time"] = datetime.now(pytz.UTC).isoformat()
            updated_embed = await build_auction_embed(auction, self.bot)
            await self.live_update_message.edit(embed=updated_embed, content=None)
        
        await interaction.response.send_message(end_msg, ephemeral=True)
        os.remove(AUCTION_FILE)

    @app_commands.command(name="updateauction", description="Update auction details (admin only)")
    @app_commands.describe(
        item="New item name (optional)",
        description="New description (optional)",
        minimum_bid="New minimum bid (optional)",
        thumbnail="New thumbnail image (optional)",
        banner="New banner image (optional)"
    )
    async def slash_updateauction(
        self, 
        interaction: discord.Interaction, 
        item: str = None, 
        description: str = None, 
        minimum_bid: int = None,
        thumbnail: discord.Attachment = None,
        banner: discord.Attachment = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Admins only!", ephemeral=True)
            return

        auction = load_json(AUCTION_FILE)
        if not auction:
            await interaction.response.send_message("❌ No auction is running.", ephemeral=True)
            return

        if item:
            auction["item"] = item
        if description:
            auction["description"] = description
        if minimum_bid is not None:
            auction["minimum_bid"] = minimum_bid
        if thumbnail:
            auction["image_url"] = thumbnail.url
        if banner:
            auction["banner_url"] = banner.url

        save_json(AUCTION_FILE, auction)

        if self.live_update_message:
            updated_embed = await build_auction_embed(auction, self.bot)
            await self.live_update_message.edit(embed=updated_embed)

        await interaction.response.send_message("✅ Auction updated.", ephemeral=True)

    @app_commands.command(name="auctionstatus", description="Check current auction details")
    async def auctionstatus(self, interaction: discord.Interaction):
        """Check the current auction status"""
        auction = load_json(AUCTION_FILE)
        if not auction:
            return await interaction.response.send_message("ℹ️ No active auction currently running.", ephemeral=True)

        embed = await build_auction_embed(auction, self.bot)
        # Add additional admin-only info
        if interaction.user.guild_permissions.administrator:
            total_bidders = len(self.all_bidders)
            pending_refunds = sum(self.pending_refunds.values())
            embed.add_field(
                name="Admin Stats",
                value=f"• Total Bidders: {total_bidders}\n"
                      f"• Pending Refunds: {pending_refunds} smiles",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="resetauctionwins", description="Reset the monthly auction win counter for all users or a specific user (admin only)")
    @app_commands.describe(
        user="Provide 'all', a user ID, or a username to reset wins"
    )
    async def slash_resetauctionwins(self, interaction: discord.Interaction, user: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Admins only!", ephemeral=True)
            return

        wins = load_json(WIN_TRACKER_FILE)

        # Reset all users
        if user.lower() == "all":
            save_json(WIN_TRACKER_FILE, {})
            await interaction.response.send_message("✅ Monthly auction win counters have been reset for all users.", ephemeral=True)
            return

        # Try user ID first
        if user.isdigit():
            if user in wins:
                wins[user] = 0
                save_json(WIN_TRACKER_FILE, wins)
                member = interaction.guild.get_member(int(user))
                name = member.display_name if member else user
                await interaction.response.send_message(f"✅ Auction win counter reset for user: {name}", ephemeral=True)
            else:
                await interaction.response.send_message("❌ User ID not found in win tracker.", ephemeral=True)
            return

        # Try username
        found = False
        for uid, count in wins.items():
            member = interaction.guild.get_member(int(uid))
            if member and (member.name.lower() == user.lower() or member.display_name.lower() == user.lower()):
                wins[uid] = 0
                save_json(WIN_TRACKER_FILE, wins)
                await interaction.response.send_message(f"✅ Auction win counter reset for user: {member.display_name}", ephemeral=True)
                found = True
        if not found:
            await interaction.response.send_message("❌ Username not found in win tracker.", ephemeral=True)


       #ERROR HANDLING#
    @slash_bid.error
    async def slash_bid_error(self, interaction, error):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"⏱️ Cooldown: Try again in {error.retry_after:.1f}s",
                ephemeral=True
            )
    
    
            
    @legacy_bid.error
    async def bid_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏱️ Cooldown: Try again in {error.retry_after:.1f}s", delete_after=5)


async def setup(bot):
    await bot.add_cog(AuctionManager(bot))