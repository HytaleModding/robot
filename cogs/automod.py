import re

import discord
from discord.ext import commands

from config import ConfigSchema


class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config: ConfigSchema = bot.config
        self.cog_config = self.config.cogs.automod

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Automatically delete messages containing discord links."""
        if message.author.bot:
            return

        if any(role.id in self.cog_config.whitelisted_role_ids for role in message.author.roles) or message.author.guild_permissions.administrator:
            return

        DISCORD_INVITE_URL_REGEX = r"(https?:\/\/)?(www\.)?(discord\.gg|discordapp\.com\/invite)\/[a-zA-Z0-9]+"
        if re.search(DISCORD_INVITE_URL_REGEX, message.content):
            await message.delete()
            await message.channel.send(
                f"{message.author.mention}, posting Discord invite links is not allowed! Please DM <@702385226407608341> if you would like to post an invite to your server.", delete_after=30
            )
            clean_content = re.sub(DISCORD_INVITE_URL_REGEX, "[invite link removed]", message.content)
            await message.channel.send(
                f"Cleaned message from {message.author.mention}: \n\n{clean_content}",
                allowed_mentions=discord.AllowedMentions.none()
            ) 


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
