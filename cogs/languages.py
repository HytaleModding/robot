import discord
from discord import app_commands
from discord.ext import commands

import logging

from config import ConfigSchema

log = logging.getLogger(__name__)

class Languages(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.db = bot.database
        self.config: ConfigSchema = bot.config
        self.cog_config = self.config.cogs.languages

        self.translation_channel: discord.TextChannel = self.bot.get_channel(self.cog_config.translator_channel_id)

        # Other decorators are applied already in class definition so this is fine
        translator_command_choices_decorator = app_commands.choices(
            language=[app_commands.Choice(name=lang, value=lang) for lang in self.cog_config.languages]
        )
        self.translator = translator_command_choices_decorator(self.translator)

        self.mention_translators_menu = app_commands.ContextMenu(
            name="Mention Translators",
            callback=self.mention_translators
        )
        self.bot.tree.add_command(self.mention_translators_menu)

    @app_commands.command()
    @app_commands.describe(language="Select the language you translate to")
    async def translator(self, interaction: discord.Interaction, language: str):
        thread: discord.Thread = None
        for t in self.translation_channel.threads: # for people looking at this, I know it's not the best way but it works dynamically and I don't have to hard code IDs.
            if t.name == f"{language} Discussion":
                thread = t
                break

        if thread is None:
            thread = await self.translation_channel.create_thread(name=f"{language} Discussion", type=discord.ChannelType.private_thread, auto_archive_duration=None, reason=f"Translator thread for {language} created by {interaction.user}.", invitable=False)
            for user_id in self.cog_config.thread_watcher_user_ids:
                await thread.add_user(await self.bot.fetch_user(user_id)) # This is fine if it's like below 5 users
            log.info(f"Created new translator thread for {language}")

        await thread.add_user(interaction.user)
        await interaction.response.send_message(f"You have been added to the translator thread for {language}.", ephemeral=True)

    async def mention_translators(self, interaction: discord.Interaction, message: discord.Message) -> None:
        if not isinstance(message.channel, discord.Thread):
            await interaction.response.send_message(
                "This message is not in a translator thread.", ephemeral=True
            )
            return
        
        channel: discord.Thread = interaction.channel
        if channel.parent_id != self.cog_config.translator_channel_id:
            await interaction.response.send_message(
                "This message is not in a translator thread.", ephemeral=True
            )
            return
        
        language = channel.name.replace(" Discussion", "")
        # `thread_watcher_user_ids` could also be added here, or maybe a new core config option for staff users or roles
        proofreaders = self.cog_config.proof_reader_user_ids_by_language.get(language, [])
        if interaction.user.id not in proofreaders:
            await interaction.response.send_message(
                "You are not authorized to mention translators for this language.", ephemeral=True
            )
            return

        mentions = []
        async for member in channel.fetch_members():
            if member.id != interaction.user.id:
                mentions.append(member.mention)

        if not mentions:
            await interaction.response.send_message(
                "There are no other translators in this thread.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Mentioning translators for {language}: \n{', '.join(mentions)}"
        )

async def setup(bot):
    await bot.add_cog(Languages(bot))