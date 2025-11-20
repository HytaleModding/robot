import discord
from discord import app_commands
from discord.ext import commands


class ThreadUtils(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.pin_menu = app_commands.ContextMenu(
            name="Pin Message",
            callback=self.pin_message
        )

        self.bot.tree.add_command(self.pin_menu)

    async def pin_message(self, interaction: discord.Interaction, message: discord.Message):
        if not isinstance(message.channel, discord.Thread):
            await interaction.response.send_message(
                "This message is not in a thread.", ephemeral=True
            )
            return

        if message.channel.owner_id != interaction.user.id:
            await interaction.response.send_message(
                "You are not the owner of this thread.", ephemeral=True
            )
            return

        await message.pin(reason=f"Pinned by thread owner {interaction.user}.")

        await interaction.response.send_message("Message pinned!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ThreadUtils(bot))
