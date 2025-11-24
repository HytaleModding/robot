import discord
from discord import app_commands
from discord.ext import commands

import re

class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Automatically delete messages containing discord links."""
        if message.author.bot:
            return

        DISCORD_INVITE_URL_REGEX = r"(https?:\/\/)?(www\.)?(discord\.gg|discordapp\.com\/invite)\/[a-zA-Z0-9]+"
        if re.search(DISCORD_INVITE_URL_REGEX, message.content):
            await message.delete()
            await message.channel.send(
                f"{message.author.mention}, posting Discord invite links is not allowed! Please DM @itsneil if you would like to post an invite to your server."
            )
            clean_content = re.sub(DISCORD_INVITE_URL_REGEX, "[invite link removed]", message.content)
            await message.channel.send(
                f"Cleaned message from {message.author.mention}: \n\n{clean_content}"
            ) 


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
