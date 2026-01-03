import discord
from discord.ext import commands, tasks

import datetime

class Countdown(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.countdown_channel = bot.get_channel(1456991332135342198)

    @commands.Cog.listener()
    async def on_ready(self):
        self.countdown.start()

    def cog_unload(self):
        self.countdown.cancel()

    @tasks.loop(minutes=1)
    async def countdown(self):
        end_time = datetime.datetime.fromtimestamp(1768262400)
        now = datetime.datetime.now()
        time_left = end_time - now
        new_name = f"{time_left.days}-{time_left.seconds // 3600}-{(time_left.seconds // 60) % 60}"
        await self.countdown_channel.edit(name=new_name)

    @countdown.before_loop
    async def before_countdown(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Countdown(bot))