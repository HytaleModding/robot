import discord
from discord import app_commands
from discord.ext import commands, tasks

import asyncio
from database import Database

class Voting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: Database = bot.database

        self.showcase_channel = self.bot.get_channel(1440185755745124503)
        self.update_votes.start()

    def cog_unload(self):
        self.update_votes.cancel()
        return super().cog_unload()
    
    async def scan_existing_showcases(self):
        """Scan all messages in showcase channel and update database with current upvote counts"""
        if not self.showcase_channel:
            print("Showcase channel not found")
            return
        
        print("Starting to scan existing showcases...")
        message_count = 0
        
        async for message in self.showcase_channel.history(limit=None):
            if message.author.bot:
                continue
                
            fire_reaction = None
            for reaction in message.reactions:
                if str(reaction.emoji) == '🔥':
                    fire_reaction = reaction
                    break
            
            if fire_reaction:
                async for user in fire_reaction.users():
                    if not user.bot:
                        await self.db.log_upvote(user.id, message.id)
                        
                print(f"Updated message {message.id} with {fire_reaction.count - 1} upvotes")
            
            message_count += 1
            
            if message_count % 10 == 0:
                await asyncio.sleep(1)
                print(f"Processed {message_count} messages...")
        
        print(f"Finished scanning {message_count} messages")

    @app_commands.command(name="sync_votes", description="Sync existing showcase votes to database")
    @app_commands.default_permissions(administrator=True)
    async def sync_votes(self, interaction: discord.Interaction):
        """Admin command to sync existing votes"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            await self.scan_existing_showcases()
            await interaction.followup.send("✅ Successfully synced all existing showcase votes!")
        except Exception as e:
            await interaction.followup.send(f"❌ Error syncing votes: {str(e)}")
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return
        
        if reaction.message.channel.id != 1440185755745124503:
            return
        
        if str(reaction.emoji) == '🔥':
            await self.db.log_upvote(user.id, reaction.message.id)
        
    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return
        
        if reaction.message.channel.id != 1440185755745124503:
            return
        
        if str(reaction.emoji) == '🔥':
            await self.db.remove_upvote(user.id, reaction.message.id)

    @tasks.loop(seconds=30)
    async def update_votes(self):
        showcases = await self.db.get_top_5_showcases()
        channel = self.bot.get_channel(1442968358080221254)
        if not isinstance(channel, discord.TextChannel):
            return

        async for msg in channel.history(limit=100):
            if msg.author == self.bot.user:
                await msg.delete()

        for i, showcase in enumerate(showcases[:5], 1):
            original_message = None
            try:
                original_message = await self.showcase_channel.fetch_message(showcase['showcase_id'])
            except Exception as e:
                print(e)
                continue
            
            if not original_message:
                print("Original message not found")
                continue
            
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
            
            await channel.send(embed=embed)
        e = discord.Embed(
            description="React with 🔥 in the <#1440185755745124503> channel to upvote your favorite showcases!",
            color=0x2F3136
        )
        await channel.send(embed=e)


async def setup(bot):
    await bot.add_cog(Voting(bot))
