import discord
from discord.ext import commands

class Keywords(commands.Cog):
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

    @commands.command()
    async def languages(self, ctx: commands.Context):
        replied_message = await self.get_replied_message(ctx)
        
        e = discord.Embed(description="Hytale will support the following languages:\n\n- The server is written in Java (currently Java 25).\n- The client is written in C#.\n- It is unknown how the client will be moddable, if at all. Servers will be fully moddable and will have a **handshake process** where textures and other resources are sent from the server to the client the first time you join.\n- In addition, modders will be able to use **Noesis Engine** to create custom UI, which supports C++ and C# (assumedly C# will be used).\n\n-# *This information is subject to change as Hytale is still in development. It is not confirmed.*")
        e.set_footer(text="Hytale Modding", icon_url='https://img.willofsteel.me/u/p2SdbC.png')
        await replied_message.reply(embed=e)
    
    @commands.command()
    async def security(self, ctx: commands.Context):
        replied_message = await self.get_replied_message(ctx)
        
        e = discord.Embed(description="Hypixel Studios will have a bug bounty program to help improve the security of Hytale. \n\n### [Click here or the link above to visit](https://hytale.com/security)")
        e.set_footer(text="Hytale Modding", icon_url='https://img.willofsteel.me/u/p2SdbC.png')
        await replied_message.reply(content="https://hytale.com/security", embed=e)

    @commands.command()
    async def site(self, ctx: commands.Context):
        replied_message = await self.get_replied_message(ctx)
        
        await replied_message.reply("https://github.com/HytaleModding/site")

    @commands.command()
    async def bot(self, ctx: commands.Context):
        replied_message = await self.get_replied_message(ctx)
        
        await replied_message.reply("https://github.com/HytaleModding/robot")

    @commands.command()
    async def threaded(self, ctx: commands.Context):
        replied_message = await self.get_replied_message(ctx)
        
        e = discord.Embed(description="# THIS CHANNEL IS THREADED :thread:\n\nIf you wish to reply to a message, please reply in the thread and not in this channel. This helps keep the channel clean and organized. A thread for every message sent will automatically be created by me. \n\nThank you for your cooperation! :smiley:")
        e.set_footer(text="Hytale Modding", icon_url='https://img.willofsteel.me/u/p2SdbC.png')
        if replied_message == ctx.message:
            await ctx.channel.send(embed=e)
        else:
            await replied_message.reply(embed=e)

    @commands.command()
    async def threadpin(self, ctx: commands.Context):
        replied_message = await self.get_replied_message(ctx)

        e = discord.Embed(description="Right-click any message in a thread you own and select 'Apps' -> 'Pin Message' to pin that message to the thread. Only the thread owner can pin messages in their thread.")
        e.set_footer(text="Hytale Modding", icon_url='https://img.willofsteel.me/u/p2SdbC.png')
        await replied_message.reply(embed=e)

async def setup(bot):
    await bot.add_cog(Keywords(bot))
