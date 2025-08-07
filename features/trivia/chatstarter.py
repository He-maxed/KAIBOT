import discord
import random
import asyncio
import json
import os
import aiohttp
import html
from discord.ext import commands, tasks
from datetime import timezone, datetime, timedelta
from typing import List, Dict, Tuple, Optional

# ======================
# BASE QUESTION HANDLER
# ======================
class QuestionHandler:
    def __init__(self, data_file: str):
        self.data_file = data_file
        self.questions = self.load_questions()

    def load_questions(self) -> List[str]:
        """Load questions from JSON file"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'questions' in data:
                    return data['questions']
                return self.get_default_questions()
        except (FileNotFoundError, json.JSONDecodeError):
            return self.get_default_questions()

    def save_questions(self, questions: List[str]) -> None:
        """Save questions to JSON file"""
        data = {
            "meta": {
                "version": "1.1",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "count": len(questions)
            },
            "questions": questions
        }
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def get_default_questions(self) -> List[str]:
        """Return default questions if file not found"""
        default_questions = [
            "Pineapple on pizza - delicious or crime against food?",
            "If you could have any superpower, but it had to be completely useless, what would you choose?",
            "What's the most overrated movie/TV show everyone loves but you don't get?"
        ]
        self.save_questions(default_questions)
        return default_questions

# ======================
# TRIVIA SYSTEM
# ======================
class TriviaSystem:
    def __init__(self, bot: commands.Bot, channel_id: int):
        self.bot = bot
        self.channel_id = channel_id
        self.current_message = None
        self.current_answer = None

    async def fetch_trivia(self) -> Tuple[str, str]:
        """Fetch trivia question from API without options"""
        category = random.choice([17])  #17: Science & Nature
        url = f"https://opentdb.com/api.php?amount=1&category={category}&difficulty=easy&type=multiple"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if not data.get('results'):
                    return self.get_fallback_question()
                
                q = data["results"][0]
                question = html.unescape(q["question"])
                answer = html.unescape(q["correct_answer"])
                return question, answer

    def get_fallback_question(self) -> Tuple[str, str]:
        """Fallback questions without options"""
        fallbacks = [
            ("The capital of France is Paris.", "True"),
            ("Mars is known as the Red Planet.", "True"),
            ("The largest mammal is the blue whale.", "True")
        ]
        return random.choice(fallbacks)

    async def post_trivia(self) -> None:
        """Post a new trivia question without options"""
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return

        # Clean up previous question
        await self.cleanup_question()

        question, answer = await self.fetch_trivia()
        self.current_answer = answer.lower().strip()
        
        message_text = f"🧠 **Trivia Time!**\n{question}"
        self.current_message = await channel.send(message_text)
        return self.current_message

    async def cleanup_question(self) -> None:
        """Delete current question if exists"""
        if self.current_message:
            try:
                await self.current_message.delete()
            except Exception:
                pass
            self.current_message = None
            self.current_answer = None

    async def check_answer(self, message: discord.Message) -> bool:
        """Check if message contains correct answer"""
        if not self.current_answer:
            return False

        content = message.content.lower().strip()
        return content == self.current_answer

# ======================
# CHAT ACTIVITY MONITOR 
# ======================
class ChatActivityMonitor:
    def __init__(self, channel_ids: List[int], cooldown: int = 30, activity_window: int = 10):
        self.channel_ids = channel_ids
        self.question_cooldown = timedelta(minutes=cooldown)
        self.activity_check = timedelta(minutes=activity_window)
        self.last_message_time = {}
        self.last_bot_messages = {}

    async def cleanup_previous_message(self, channel: discord.TextChannel) -> None:
        """Delete our previous message if it's the last message"""
        if channel.id in self.last_bot_messages:
            try:
                last_msg = [m async for m in channel.history(limit=1)][0]
                if last_msg.id == self.last_bot_messages[channel.id]:
                    await last_msg.delete()
            except (IndexError, discord.NotFound, discord.Forbidden):
                pass
            finally:
                del self.last_bot_messages[channel.id]

    async def should_post_question(self, channel: discord.TextChannel) -> bool:
        """Check if we should post a question in this channel"""
        now = datetime.now(timezone.utc)
        
        try:
            messages = [m async for m in channel.history(limit=10)]
            last_msg = messages[0]
            
            # Clean up our previous message if it's the last one
            if last_msg.author == channel.guild.me:
                await self.cleanup_previous_message(channel)
                return False
            
            # Count recent non-bot messages
            message_count = sum(
                1 for m in messages 
                if m.created_at > now - self.activity_check 
                and not m.author.bot
            )
            if message_count >= 10:
                return False
                
            last_msg_time = last_msg.created_at
        except IndexError:
            last_msg_time = now - timedelta(days=1)

        last_question = self.last_message_time.get(channel.id, now - self.question_cooldown)
        return (now - last_msg_time >= self.activity_check and 
                now - last_question >= self.question_cooldown)

    def update_last_question_time(self, channel_id: int, message_id: int) -> None:
        """Update tracking for last question"""
        self.last_message_time[channel_id] = datetime.now(timezone.utc)
        self.last_bot_messages[channel_id] = message_id

# ======================
# MAIN COG IMPLEMENTATION
# ======================
class TriviaAndChatStarter(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.trivia_channel_id = 1397979623845007452  # Replace with your channel ID
        self.chat_starter_channel_ids = [1398311790345064458]
        self.questions_file = os.path.join(os.path.dirname(__file__), "questions.json")
        
        # Initialize systems
        self.question_handler = QuestionHandler(self.questions_file)
        self.trivia_system = TriviaSystem(bot, self.trivia_channel_id)
        self.chat_monitor = ChatActivityMonitor(self.chat_starter_channel_ids)
        
        # Start tasks
        self.trivia_task.start()
        self.chat_starter_task.start()

    def cog_unload(self):
        self.trivia_task.cancel()
        self.chat_starter_task.cancel()

    @tasks.loop(minutes=4)
    async def trivia_task(self):
        """Automated trivia posting task"""
        await self.bot.wait_until_ready()
        await self.post_trivia_question()

    async def post_trivia_question(self):
        """Post and manage a single trivia question"""
        channel = self.bot.get_channel(self.trivia_channel_id)
        if not channel:
            return
    
        await self.trivia_system.post_trivia()
    
        def check(m: discord.Message):
            if (
                m.channel.id != self.trivia_channel_id or
                m.author.bot or
                not self.trivia_system.current_answer
            ):
                return False
            return m.content.lower().strip() == self.trivia_system.current_answer
    
        try:
            msg = await self.bot.wait_for("message", timeout=300, check=check)
    
            try:
                from database.coin_db import change_balance
                change_balance(msg.author.id, 10)
                reward_msg = f"🎉 {msg.author.mention} got it right and earned 10 smiles"
            except Exception as e:
                print(f"Couldn't award coins: {e}")
                reward_msg = f"🎉 {msg.author.mention} got it right!"
    
            await msg.add_reaction("✅")
            await msg.reply(reward_msg)
    
        except asyncio.TimeoutError:
            pass
        finally:
            await self.trivia_system.cleanup_question()
    
    
    @tasks.loop(minutes=5)
    async def chat_starter_task(self):
        """Automated chat starter posting task"""
        await self.bot.wait_until_ready()
        
        for channel_id in self.chat_monitor.channel_ids:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue

            if await self.chat_monitor.should_post_question(channel):
                question = random.choice(self.question_handler.questions)
                sent_message = await channel.send(f"💬 **Chat Starter**: {question}")
                self.chat_monitor.update_last_question_time(channel.id, sent_message.id)
                
                if random.random() < 0.1:
                    self.question_handler.questions = self.question_handler.load_questions()

    @commands.command(name="suggestquestion", aliases=["sq"])
    @commands.has_permissions(administrator=True)
    async def suggest_question(self, ctx, *, question: str):
        """Suggest a new question (Admin only)"""
        self.question_handler.questions.append(question)
        self.question_handler.save_questions(self.question_handler.questions)
        await ctx.send("✅ Question added to rotation!")

    @commands.command(name="reloadquestions", aliases=["rq"])
    @commands.has_permissions(administrator=True)
    async def reload_questions(self, ctx):
        """Reload questions from file (Admin only)"""
        self.question_handler.questions = self.question_handler.load_questions()
        await ctx.send(f"✅ Reloaded {len(self.question_handler.questions)} questions!")

async def setup(bot: commands.Bot):
    cog = TriviaAndChatStarter(bot)
    await bot.add_cog(cog)