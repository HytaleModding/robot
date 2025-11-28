import discord
from discord import app_commands
from discord.ext import commands, tasks

import asyncio
from database import Database

class Voting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: Database = bot.database

        self.upvote_menu = app_commands.ContextMenu(
            name="Upvote",
            callback=self.upvote_message
        )
        self.bot.tree.add_command(self.upvote_menu)
        self.showcase_channel = self.bot.get_channel(1440185755745124503)
        self.update_votes.start()

    def cog_unload(self):
        self.update_votes.cancel()
        return super().cog_unload()

    async def upvote_message(self, interaction: discord.Interaction, message: discord.Message):
        if interaction.channel_id != 1440185755745124503:
            await interaction.response.send_message(
                "Upvotes can only be given in the #voting channel.", ephemeral=True
            )
            return

        if message.author.id == interaction.user.id:
            await interaction.response.send_message(
                "You cannot upvote your own message.", ephemeral=True
            )
            return
        
        if message.author.bot:
            await interaction.response.send_message(
                "You cannot upvote bot messages.", ephemeral=True
            )
            return
        
        if len(message.attachments) == 0:
            await interaction.response.send_message(
                "You can only upvote messages with attachments.", ephemeral=True
            )
            return
        
        if await self.db.has_user_upvoted(interaction.user.id, message.id):
            upvotes = await self.db.get_upvotes(message.id)
            await interaction.response.send_message(
                f"You have already upvoted this message. This message has {upvotes} upvote(s).", ephemeral=True
            )
            return
        
        await self.db.log_upvote(interaction.user.id, message.id)
        total_upvotes = await self.db.get_upvotes(message.id)
        await interaction.response.send_message(
            f"You have upvoted this message! It now has {total_upvotes} upvote(s).",
            ephemeral=True
        )
    
    @tasks.loop(seconds=30)
    async def update_votes(self):
        showcases = await self.db.get_top_5_showcases()
        channel = self.bot.get_channel(1442943712538660934)
        if not isinstance(channel, discord.TextChannel):
            return

        async for msg in channel.history(limit=100):
            if msg.author == self.bot.user:
                await msg.delete()

        for i, showcase in enumerate(showcases[:5], 1):
            print(i, showcase)
            original_message = None
            try:
                original_message = await self.showcase_channel.fetch_message(showcase['showcase_id'])
            except Exception as e:
                print(e)
                continue
            
            if not original_message:
                print("Original message not found")
                continue
            
            # Create embed
            ranking_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            embed = discord.Embed(
                title=f"{ranking_emoji} Top Community Showcase",
                description=original_message.content if original_message.content else "No description provided",
                color=0xFFD700 if i == 1 else 0xC0C0C0 if i == 2 else 0xCD7F32 if i == 3 else 0x7289DA,
                url=original_message.jump_url
            )
            
            embed.set_author(
                name=original_message.author.display_name,
                icon_url=original_message.author.display_avatar.url
            )
            
            embed.add_field(
                name="⬆️ Upvotes",
                value=str(showcase['upvote_count']),
                inline=True
            )
            
            embed.add_field(
                name="👤 Author",
                value=original_message.author.mention,
                inline=True
            )
            
            if original_message.attachments:
                attachment = original_message.attachments[0]
                if attachment.content_type and attachment.content_type.startswith('video/'):
                    embed.add_field(
                        name="📹 Video",
                        value=f"[View Video]({attachment.url})",
                        inline=True
                    )
                elif attachment.content_type and attachment.content_type.startswith('audio/'):
                    embed.add_field(
                        name="🎵 Audio",
                        value=f"[Listen Here]({attachment.url})",
                        inline=True
                    )
                else:
                    embed.set_image(url=attachment.url)
            
            embed.set_footer(text="Community Showcase Leaderboard")
            
            # Send the embed
            await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Voting(bot))
