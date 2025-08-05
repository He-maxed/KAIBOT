import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import database.coin_db as coin_db
from flask import Flask, Response
import threading
import asyncio

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Flask server setup
app = Flask(__name__)

@app.route('/')
def health_check():
    return Response("Bot is alive (Render-compatible)", status=200)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Start Flask in a separate thread
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# Setup Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Bot setup
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print(f"✅ {bot.user} is online and slash commands are synced!")
        # Start status task only AFTER bot is ready
        bot.loop.create_task(status_task())
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

@bot.event
async def setup_hook():
    # Load all Cogs
    extensions = [
        "commands.admin_give",
        "commands.balance",
        "commands.leaderboard",
        "commands.shop_system",
        "features.auction.auction_managercommands",
        "features.trivia_and_Interesting.trivia",
        "commands.cointoss",
        "features.upvote.upvote_tracker",
        "features.trivia_and_Interesting.interestingquestions",
    ]
    
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"✅ Loaded cog: {ext}")
        except Exception as e:
            print(f"❌ Failed to load cog {ext}: {e}")
    
    print("✅ All Cogs Loaded")

async def status_task():
    """Change bot status periodically to show it's alive"""
    while True:
        try:
            if bot.is_ready():  # Only change presence if bot is connected
                await bot.change_presence(activity=discord.Game(name="Serving Kai Bot"))
                await asyncio.sleep(60)
                await bot.change_presence(activity=discord.Game(name=f"spreading Smiles Everywhere!"))
                await asyncio.sleep(60)
            else:
                await asyncio.sleep(5)  # Wait if bot isn't ready
        except Exception as e:
            print(f"❌ Status task error: {e}")
            await asyncio.sleep(10)  # Wait before retrying

# Initialize DB
coin_db.init_db()

if __name__ == '__main__':
    try:
        bot.run(TOKEN)
    except discord.LoginError:
        print("❌ Invalid Discord token. Check your .env file")
    except KeyboardInterrupt:
        print("🛑 Bot shutting down...")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")