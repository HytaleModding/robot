import discord
from discord.ext import commands

TAGS = {
    "languages": {
        "title": None,
        "description": "Hytale will support the following languages:\n\n- The server is written in Java (currently Java 25).\n- The client is written in C#.\n- In addition, modders will be able to use **Noesis Engine** to create custom UI, which supports C++ and C# (assumedly C# will be used).\n- It is unknown how the client will be moddable, if at all. Servers will be fully moddable and will have a **handshake process** where textures and other resources are sent from the server to the client the first time you join.\n\n-# *This information is subject to change as Hytale is still in development. It is not confirmed.*",
        "url": None
    },
    "security": {
        "title": None,
        "description": "Hypixel Studios will have a bug bounty program to help improve the security of Hytale. \n\n### [Click here or the link above to visit](https://hytale.com/security)",
        "url": "https://hytale.com/security"
    },
    "site": {
        "title": None,
        "description": None,
        "url": "https://github.com/HytaleModding/site"
    },
    "bot": {
        "title": None,
        "description": None,
        "url": "https://github.com/HytaleModding/robot"
    },
    "threaded": {
        "title": None,
        "description": "# THIS CHANNEL IS THREADED :thread:\n\nIf you wish to reply to a message, please reply in the thread and not in this channel. This helps keep the channel clean and organized. A thread for every message sent will automatically be created by me. \n\nThank you for your cooperation! :smiley:",
        "url": None
    },
    "threadpin": {
        "title": None,
        "description": "Right-click any message in a thread you own and select 'Apps' -> 'Pin Message' to pin that message to the thread. Only the thread owner can pin messages in their thread.",
        "url": None
    },
    "platforms": {
        "title": None,
        "description": "- Hytale will initially release only for Windows PC\n- Mac & Linux support will be attempted but not guaranteed. Can use Wine/Proton in the meantime\n- Console and mobile app not being considered anytime soon, but Simon says it will be possible to make the Legacy Engine cross-platform",
        "url": None
    },
    "networking": {
        "title": None,
        "description": "- Hytale will use the QUIC transport protocol.\n- QUIC is a hybrid protocol that builds off UDP to get the same speed benefits, but adds some layers of reliability like TCP.",
        "url": None
    },
    "featured-guide": {
        "title": "Featured Community Projects",
        "description": "Congratulations! Your project is being featured on our website, here are the steps to add your projects:\n\n- Fork the [site repository](https://github.com/HytaleModding/site)\n- On the `dev` branch, open the `content/docs/projects` folder\n- Create a new markdown file for your project, following the existing format\n- Submit a pull request to the `dev` branch\n\nOnce your pull request is reviewed and merged, your project will be featured on the website!\n\nThank you for contributing to the Hytale Modding community!",
        "url": None
    },
    "follow-threads": {
        "title": "Following Threads",
        "description": "To follow a thread and receive notifications for new updates, run the `/follow` command. You can unfollow a thread at any time using the `/unfollow` command.",
        "url": None
    }
}

class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
    
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
        if tag_name not in TAGS:
            if hasattr(ctx_or_interaction, 'response'):
                await ctx_or_interaction.response.send_message(f"Tag '{tag_name}' not found.", ephemeral=True)
            else:
                await ctx_or_interaction.send(f"Tag '{tag_name}' not found.")
            return

        tag_data = TAGS[tag_name]
        
        embed = None
        if tag_data.get("description"):
            embed = discord.Embed(description=tag_data["description"])
            if tag_data.get("title"):
                embed.title = tag_data["title"]
            embed.set_footer(text="Hytale Modding", icon_url='https://img.willofsteel.me/u/p2SdbC.png')

        content = tag_data.get("url", "")

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
        
        if command_name in TAGS:
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
        for tag_name in TAGS.keys():
            if current.lower() in tag_name.lower():
                choices.append(discord.app_commands.Choice(name=tag_name, value=tag_name))
        return choices[:25]

async def setup(bot):
    await bot.add_cog(Tags(bot))
