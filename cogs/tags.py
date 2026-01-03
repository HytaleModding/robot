import discord
from discord.ext import commands

from config import ConfigSchema


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.config: ConfigSchema = bot.config
        self.cog_config = self.config.cogs.tags
    
    async def get_replied_message(self, ctx: commands.Context) -> discord.Message:
        if ctx.message.reference:
            replied_message = ctx.message.reference.resolved
            if replied_message is None:
                replied_message = await ctx.channel.fetch_message(
                    ctx.message.reference.message_id
                )
        else:
            replied_message = ctx.message
        return replied_message

    async def send_tag(self, tag_name: str, ctx_or_interaction, replied_message=None):
        if tag_name not in self.cog_config.mentionable_tags:
            if hasattr(ctx_or_interaction, 'response'):
                await ctx_or_interaction.response.send_message(f"Tag '{tag_name}' not found.", ephemeral=True)
            else:
                await ctx_or_interaction.send(f"Tag '{tag_name}' not found.")
            return

        tag_data = self.cog_config.mentionable_tags[tag_name]
        
        embed = None
        if tag_data.description:
            embed = discord.Embed(description=tag_data.description)
            if tag_data.title:
                embed.title = tag_data.title
            embed.set_footer(text="Hytale Modding", icon_url='https://img.willofsteel.me/u/p2SdbC.png')

        content = tag_data.url or ""

        if hasattr(ctx_or_interaction, 'response'):
            await ctx_or_interaction.response.send_message(content=content or None, embed=embed)
        else:
            if replied_message:
                await replied_message.reply(content=content or None, embed=embed)
            else:
                if tag_name == "threaded" and replied_message == ctx_or_interaction.message:
                    await ctx_or_interaction.channel.send(embed=embed)
                else:
                    await ctx_or_interaction.send(content=content or None, embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for tag commands in messages"""
        if message.author.bot:
            return
        
        prefixes = await self.bot.get_prefix(message)
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        
        used_prefix = None
        for prefix in prefixes:
            if message.content.startswith(prefix):
                used_prefix = prefix
                break
        
        if not used_prefix:
            return
        
        command_content = message.content[len(used_prefix):].strip()
        if not command_content:
            return
        
        command_name = command_content.split()[0].lower()
        
        if command_name in self.cog_config.mentionable_tags:
            ctx = await self.bot.get_context(message)
            replied_message = await self.get_replied_message(ctx)
            await self.send_tag(command_name, ctx, replied_message)

    @discord.app_commands.command(name="tag", description="Send a predefined tag")
    @discord.app_commands.describe(name="The name of the tag to send")
    async def tag_slash(self, interaction: discord.Interaction, name: str):
        await self.send_tag(name, interaction)

    @tag_slash.autocomplete('name')
    async def tag_autocomplete(self, interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
        """Autocomplete for tag names"""
        choices = []
        for tag_name in self.cog_config.mentionable_tags.keys():
            if current.lower() in tag_name.lower():
                choices.append(discord.app_commands.Choice(name=tag_name, value=tag_name))
        return choices[:25]

async def setup(bot):
    await bot.add_cog(Tags(bot))
