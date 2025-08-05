import discord
import random
import asyncio
import json
import os
from discord.ext import commands, tasks
from datetime import datetime, timedelta

class InterestingQuestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_message_time = {}
        self.question_cooldown = timedelta(minutes=30)
        self.activity_check = timedelta(minutes=10)
        self.questions_file = os.path.join(os.path.dirname(__file__), "questions.json")
        self.questions = self.load_questions()

    def load_questions(self):
        """Load questions from JSON file with proper structure handling"""
        try:
            with open(self.questions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Handle both array-only and structured JSON formats
                if isinstance(data, list):
                    return data  # Direct list of questions
                elif isinstance(data, dict) and 'questions' in data:
                    return data['questions']  # Structured format
                else:
                    raise ValueError("Invalid JSON structure")
                
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            print(f"Error loading questions: {e}. Using default questions.")
            # Default fallback questions
            default_questions = [
                "Pineapple on pizza - delicious or crime against food?",
                "If you could have any superpower, but it had to be completely useless, what would you choose?",
                "What's the most overrated movie/TV show everyone loves but you don't get?"
            ]
            self.save_questions(default_questions)
            return default_questions

    def save_questions(self, questions):
        """Save questions to JSON file with proper structure"""
        data = {
            "meta": {
                "version": "1.1",
                "last_updated": datetime.utcnow().isoformat(),
                "count": len(questions)
            },
            "questions": questions
        }
        with open(self.questions_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def cog_unload(self):
        self.check_activity.cancel()

    @tasks.loop(minutes=5)
    async def check_activity(self):
        await self.bot.wait_until_ready()
        
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if "chat" in channel.name.lower():
                    now = datetime.utcnow()
                    
                    try:
                        last_message = [m async for m in channel.history(limit=1)][0]
                        last_msg_time = last_message.created_at
                    except IndexError:
                        last_msg_time = now - timedelta(days=1)
                    
                    last_question = self.last_message_time.get(channel.id, now - self.question_cooldown)
                    
                    if (now - last_msg_time >= self.activity_check and 
                        now - last_question >= self.question_cooldown):
                        # Get fresh random question
                        question = random.choice(self.questions)
                        await channel.send(f"💬 **Chat Starter**: {question}")
                        self.last_message_time[channel.id] = now
                        # Refresh questions periodically
                        if random.random() < 0.1:  # 10% chance to reload
                            self.questions = self.load_questions()

    @commands.command(name="suggestquestion", aliases=["sq"])
    @commands.has_permissions(administrator=True)
    async def suggest_question(self, ctx, *, question: str):
        """Suggest a new question to be added to the rotation (Admin only)"""
        self.questions.append(question)
        self.save_questions(self.questions)
        await ctx.send("Thanks for your question suggestion! It's been added to the rotation.")
    
    @suggest_question.error
    async def suggest_question_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Only administrators can suggest new questions!")

    @commands.command(name="reloadquestions", aliases=["rq"])
    @commands.has_permissions(administrator=True)
    async def reload_questions(self, ctx):
        """Reload questions from the JSON file (Admin only)"""
        self.questions = self.load_questions()
        await ctx.send(f"✅ Reloaded {len(self.questions)} questions!")

async def setup(bot):
    await bot.add_cog(InterestingQuestions(bot))