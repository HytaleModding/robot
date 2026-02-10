import discord
from discord import app_commands
from discord.ext import commands
from typing import List
from config import ConfigSchema


class ThreadUtils(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config: ConfigSchema = bot.config
        self.cog_config = self.config.cogs.thread_utils

        self.pin_menu = app_commands.ContextMenu(
            name="Pin Message",
            callback=self.pin_message
        )

        self.bot.tree.add_command(self.pin_menu)

    @commands.Cog.listener()
    async def on_ready(self,):
        self.bot.add_view(CloseThreadView(None))

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

    @app_commands.command(name="close", description="Close the thread and award points to helpful users")
    async def close_thread(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "This command can only be used in threads.", ephemeral=True
            )
            return

        if interaction.channel.parent_id != self.cog_config.modding_help_channel_id:
            await interaction.response.send_message(
                "This command can only be used in the modding-help forum.", ephemeral=True
            )
            return

        if interaction.channel.owner_id != interaction.user.id:
            owner = self.bot.get_user(interaction.channel.owner_id)
            if not owner:
                await interaction.response.send_message(
                    "Could not find the thread owner.", ephemeral=True
                )
                return
            
            participants = set()
            async for message in interaction.channel.history(limit=None):
                if not message.author.bot and message.author.id != interaction.user.id:
                    participants.add(message.author)

                if not participants:
                    await interaction.response.send_message(
                        f"{owner.mention}, {interaction.user.display_name} suggested closing this thread, but no other contributors were found.",
                        allowed_mentions=discord.AllowedMentions(users=True)
                    )
                    return

                select = UserSelect(list(participants), interaction.channel, self.bot)
                view = CloseThreadView(select, interaction.channel.id, interaction.user.id)
                
                await interaction.response.send_message(
                    f"{owner.mention}, {interaction.user.display_name} suggested closing this thread. Select the users who helped solve the problem:",
                    view=view,
                    allowed_mentions=discord.AllowedMentions(users=True)
                )
                return

        participants = set()
        async for message in interaction.channel.history(limit=None):
            if not message.author.bot and message.author.id != interaction.user.id:
                participants.add(message.author)

        if not participants:
            channel: discord.Thread = interaction.channel
            await channel.edit(archived=True, locked=True)
            await interaction.response.send_message(
                "No other users found in this thread to award points to.", ephemeral=True
            )
            return

        select = UserSelect(list(participants), interaction.channel, self.bot)
        view = CloseThreadView(select, interaction.channel.id, interaction.user.id)

        await interaction.response.send_message(
            "Select the users who helped you solve your problem:",
            view=view,
            ephemeral=True
        )

class UserSelect(discord.ui.Select):
    def __init__(self, participants: List[discord.User], thread: discord.Thread, bot: commands.Bot):
        self.thread = thread
        self.bot = bot
        
        options = []
        for user in participants[:25]:
            options.append(discord.SelectOption(
                label=user.display_name,
                description=f"@{user.name}",
                value=str(user.id)
            ))
        
        super().__init__(
            placeholder="Choose users who helped you...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id=f"close_thread_select:{thread.id}"
        )

    async def callback(self, interaction: discord.Interaction):
        if not self.values:
            await interaction.response.send_message(
                "Thread will be closed without awarding points.", ephemeral=True
            )
        else:
            for user_id in self.values:
                await self.bot.database.award_points(
                    guild_id=interaction.guild.id,
                    user_id=user_id,
                    awarded_by=interaction.user.id,
                    points=1,
                    reason="Helped in modding-help thread",
                    thread_id=self.thread.id
                )
            
            await interaction.response.send_message(
                f"Thread will be closed.",
                ephemeral=True
            )

        await self.thread.edit(archived=True, locked=True)
        
        embed = discord.Embed(
            title=f"{interaction.user.display_name} has closed the thread",
            color=discord.Color.red()
        )
        
        if self.values:
            awarded_names = []
            for user_id in self.values:
                user = interaction.guild.get_member(int(user_id))
                if user:
                    awarded_names.append(user.display_name)
            
            if awarded_names:
                embed.description = f"Listing {', '.join(awarded_names)} as contributors."
        else:
            embed.description = "No contributors were selected."

        await self.thread.send(embed=embed)
        await self.thread.edit(archived=True, locked=True)

class CancelButton(discord.ui.Button):
    def __init__(self, thread_id: int):
        super().__init__(
            style=discord.ButtonStyle.secondary, 
            label="Cancel", 
            emoji="❌",
            custom_id=f"close_thread_cancel:{thread_id}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Thread closing cancelled.", ephemeral=True)
        self.view.clear_items()
        self.view.stop()

class CloseThreadView(discord.ui.View):
    def __init__(self, select: UserSelect = None, thread_id: int = None, owner_id: int = None):
        super().__init__(timeout=None)
        self.thread_id = thread_id
        self.owner_id = owner_id
        
        if select:
            self.add_item(select)
        if thread_id:
            self.add_item(CancelButton(thread_id))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


async def setup(bot):
    await bot.add_cog(ThreadUtils(bot))
