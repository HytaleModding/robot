import discord
from discord import app_commands
from discord.ext import commands

class JoinToCreate(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.jtc_channel = bot.get_channel(1462142617797136385)
        self.jtc_category = bot.get_channel(1440185623469228115)
        self.channels: dict[int, discord.VoiceChannel] = {}

    voice_group = app_commands.Group(name="voice", description="Voice channel management commands")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if after.channel == self.jtc_channel:
            new_voice = await self.jtc_category.create_voice_channel(
                f"{member.name}'s Channel",
                overwrites={
                    member.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    member: discord.PermissionOverwrite(read_messages=True)
                }
            )
            self.channels[member.id] = new_voice
            await member.move_to(new_voice)
        elif after.channel is None and member.id in self.channels and before.channel == self.channels[member.id]:
            channel: discord.VoiceChannel = before.channel
            del self.channels[member.id]
            if len(channel.members) == 0:
                await channel.delete()
            else:
                # give someone else owner
                new_owner = channel.members[0]
                self.channels[new_owner.id] = channel

    @voice_group.command()
    async def name(self, interaction: discord.Interaction, name: str):
        if interaction.user.id in self.channels and self.channels[interaction.user.id] == interaction.channel:
            channel = self.channels[interaction.user.id]
            await channel.edit(name=name)
            await interaction.response.send_message(f"Channel name changed to {name}.")
        else:
            await interaction.response.send_message("You don't own that channel.")

    @voice_group.command()
    async def limit(self, interaction: discord.Interaction, limit: int):
        if interaction.user.id in self.channels and self.channels[interaction.user.id] == interaction.channel:
            channel = self.channels[interaction.user.id]
            await channel.edit(user_limit=limit)
            await interaction.response.send_message(f"Channel limit set to {limit}.")
        else:
            await interaction.response.send_message("You don't own that channel.")

    @voice_group.command()
    async def kick(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id in self.channels and self.channels[interaction.user.id] == interaction.channel:
            if member in interaction.channel.members:
                await member.move_to(None)
                await interaction.response.send_message(f"{member.mention} has been kicked from the channel.")
            else:
                await interaction.response.send_message("That member is not in your channel.")
        else:
            await interaction.response.send_message("You don't own that channel.")

    @voice_group.command()
    async def lock(self, interaction: discord.Interaction):
        if interaction.user.id in self.channels and self.channels[interaction.user.id] == interaction.channel:
            channel = self.channels[interaction.user.id]
            await channel.set_permissions(interaction.guild.default_role, connect=False)
            await interaction.response.send_message("Channel locked.")
        else:
            await interaction.response.send_message("You don't own that channel.")

    @voice_group.command()
    async def unlock(self, interaction: discord.Interaction):
        if interaction.user.id in self.channels and self.channels[interaction.user.id] == interaction.channel:
            channel = self.channels[interaction.user.id]
            await channel.set_permissions(interaction.guild.default_role, connect=None)
            await interaction.response.send_message("Channel unlocked.")
        else:
            await interaction.response.send_message("You don't own that channel.")

async def setup(bot: commands.Bot):
    await bot.add_cog(JoinToCreate(bot))
