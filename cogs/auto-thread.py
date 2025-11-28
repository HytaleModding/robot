import discord
from discord.ext import commands

class AutoThread(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self._last_member = None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.channel.id == 1440185755745124503:
            await message.add_reaction('🔥')
            await message.create_thread(
                name=f"Discussion - {message.author.display_name}",
                reason="Auto-thread for discussion channel"
            )


    @commands.Cog.listener
    async def on_thread_create(self, thread: discord.Thread):
        if isinstance(thread.parent, discord.ForumChannel):
            await thread.starter_message.pin()

async def setup(bot):
    await bot.add_cog(AutoThread(bot))