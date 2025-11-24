import discord
from discord import app_commands
from discord.ext import commands
import re


class Utils(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="cooldown",
        description="Set a cooldown on a channel."
    )
    async def cooldown(
        self,
        interaction: discord.Interaction,
        seconds: int
    ):
        """Sets a cooldown on the current channel."""
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "You do not have permission to manage channels.",
                ephemeral=True
            )
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "This command can only be used in text channels.",
                ephemeral=True
            )
            return

        await channel.edit(slowmode_delay=seconds)
        await interaction.response.send_message(
            f"Set a cooldown of {seconds} seconds on this channel.",
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        discord_link_pattern = r'https://discord\.com/channels/(\d+)/(\d+)/(\d+)'
        matches = re.findall(discord_link_pattern, message.content)

        for match in matches:
            guild_id, channel_id, message_id = map(int, match)

            if guild_id != 1440173445039132724:
                continue

            try:
                target_guild = self.bot.get_guild(guild_id)
                if not target_guild:
                    continue

                target_channel = target_guild.get_channel(channel_id)
                if not target_channel:
                    continue

                target_message = await target_channel.fetch_message(message_id)
                if not target_message:
                    continue

                embed = discord.Embed(
                    description=target_message.content or "*No text content*",
                    color=0x2F3136,
                    timestamp=target_message.created_at
                )
                embed.set_author(
                    name=target_message.author.display_name,
                    icon_url=target_message.author.display_avatar.url
                )
                embed.set_footer(
                    text=f"#{target_channel.name}",
                    icon_url=target_guild.icon.url if target_guild.icon else None
                )

                if target_message.attachments:
                    attachment_text = f"\n\n📎 {len(target_message.attachments)} attachment(s)"
                    embed.description += attachment_text

                await message.reply(embed=embed, mention_author=False)

            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue


async def setup(bot):
    await bot.add_cog(Utils(bot))
