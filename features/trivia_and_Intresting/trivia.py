import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import html
import os
import random
from dotenv import load_dotenv
from database.coin_db import change_balance  # Make sure this import is correct

load_dotenv()
TRIVIA_CHANNEL_ID = int(os.getenv("TRIVIA_CHANNEL_ID", "0"))  # Fetch from .env

class Trivia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_message = None
        self.current_answer = None
        self.trivia_task.start()

    def cog_unload(self):
        self.trivia_task.cancel()

    async def fetch_trivia(self):
        category = random.choice([17])  # 9: General Knowledge, 17: Science & Nature
        url = f"https://opentdb.com/api.php?amount=1&category={category}&difficulty=easy&type=multiple"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                q = data["results"][0]
                question = html.unescape(q["question"])
                answer = html.unescape(q["correct_answer"])
                return question, answer

    @tasks.loop(minutes=4)
    async def trivia_task(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(TRIVIA_CHANNEL_ID)
        if not channel:
            return

        # Delete previous unanswered question if still present
        if self.current_message:
            try:
                await self.current_message.delete()
            except Exception:
                pass
            self.current_message = None
            self.current_answer = None

        question, answer = await self.fetch_trivia()
        self.current_answer = answer.lower().strip()
        self.current_message = await channel.send(f"🧠 **Trivia Time!**\n{question}")

        def check(m):
            return (
                m.channel.id == channel.id and
                m.content.lower().strip() == self.current_answer and
                not m.author.bot
            )

        try:
            msg = await self.bot.wait_for("message", timeout=240, check=check)
            await msg.add_reaction("✅")
            change_balance(msg.author.id, 10)
            await channel.send(f"🎉 {msg.author.mention} got it right and earned 10 coins!")
            await self.current_message.delete()
            self.current_message = None
            self.current_answer = None
        except asyncio.TimeoutError:
            if self.current_message:
                await self.current_message.delete()
                self.current_message = None
                self.current_answer = None

    @trivia_task.before_loop
    async def before_trivia(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Trivia(bot))