import discord
from discord import app_commands
from discord.ext import commands
import re

from better_profanity import profanity

class Utils(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.database
        profanity.load_censor_words(whitelist_words=["hytale", "hypixel", "mcc", "mcp", "mcpe", "minecraft", "fuck", "fucking", "shit", "bullshit", "bs", "idiot", "dumb"])

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

    @app_commands.command(
        name="follow",
        description="Follow a thread to get notified of announcements."
    )
    async def follow_thread(self, interaction: discord.Interaction):
        """Follow the current thread to get notifications when the owner makes announcements."""
        if not isinstance(interaction.channel, discord.Thread) and interaction.channel_id != 1444683282246668440:
            await interaction.response.send_message(
            "This command can only be used in threads.",
            ephemeral=True
            )
            return

        thread = interaction.channel
        user_id = interaction.user.id
        
        if await self.db.is_following_thread(thread.id, user_id):
            await interaction.response.send_message(
                "You are already following this thread.",
                ephemeral=True
            )
            return

        added = await self.db.add_thread_follower(thread.id, user_id)
        if added:
            await interaction.response.send_message(
                f"✅ You are now following **{thread.name}**. You'll be notified when the thread owner makes announcements.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Failed to follow the thread. Please try again.",
                ephemeral=True
            )

    @app_commands.command(
        name="unfollow",
        description="Unfollow a thread to stop getting notifications."
    )
    async def unfollow_thread(self, interaction: discord.Interaction):
        """Stop following the current thread."""
        if not isinstance(interaction.channel, discord.Thread) and interaction.channel_id != 1444683282246668440:
            await interaction.response.send_message(
                "This command can only be used in threads.",
                ephemeral=True
            )
            return

        thread = interaction.channel
        user_id = interaction.user.id
        
        removed = await self.db.remove_thread_follower(thread.id, user_id)
        if removed:
            await interaction.response.send_message(
                f"✅ You are no longer following **{thread.name}**.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "You are not currently following this thread.",
                ephemeral=True
            )

    @app_commands.command(
        name="announce",
        description="Ping all thread followers (thread owner only)."
    )
    async def announce_to_followers(self, interaction: discord.Interaction):
        """Ping all followers of this thread. Only the thread owner can use this."""
        if interaction.channel_id == 1444683282246668440:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "Only administrators can use this command in this thread.",
                    ephemeral=True
                )
                return
            
            followers = await self.db.get_thread_followers(thread.id)
        
            if not followers:
                await interaction.response.send_message(
                    "No one is following this thread yet.",
                    ephemeral=True
                )
                return

            mentions = " ".join([f"<@{user_id}>" for user_id in followers])
            
            if len(mentions) > 2000:
                chunk_size = 20
                follower_chunks = [followers[i:i + chunk_size] for i in range(0, len(followers), chunk_size)]
                
                await interaction.response.send_message(
                    f"📢 Pinging {len(followers)} followers...",
                    ephemeral=True
                )
                
                for chunk in follower_chunks:
                    chunk_mentions = " ".join([f"<@{user_id}>" for user_id in chunk])
                    await thread.send(chunk_mentions)
            else:
                await interaction.response.send_message(mentions)
            return
        
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "This command can only be used in threads.",
                ephemeral=True
            )
            return

        thread = interaction.channel
        
        if thread.owner_id != interaction.user.id or any(role.id == 1440180775512178750 for role in interaction.user.roles):
            await interaction.response.send_message(
                "Only the thread owner can send announcements.",
                ephemeral=True
            )
            return

        followers = await self.db.get_thread_followers(thread.id)
        
        if not followers:
            await interaction.response.send_message(
                "No one is following this thread yet.",
                ephemeral=True
            )
            return

        mentions = " ".join([f"<@{user_id}>" for user_id in followers])
        
        if len(mentions) > 2000:
            chunk_size = 20
            follower_chunks = [followers[i:i + chunk_size] for i in range(0, len(followers), chunk_size)]
            
            await interaction.response.send_message(
                f"📢 Pinging {len(followers)} followers...",
                ephemeral=True
            )
            
            for chunk in follower_chunks:
                chunk_mentions = " ".join([f"<@{user_id}>" for user_id in chunk])
                await thread.send(chunk_mentions)
        else:
            await interaction.response.send_message(mentions)

    @app_commands.command(
        name="followers",
        description="List all followers of this thread (thread owner only)."
    )
    async def list_followers(self, interaction: discord.Interaction):
        """List all followers of the current thread. Only the thread owner can use this."""
        if interaction.channel_id == 1444683282246668440:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "Only administrators can use this command in this thread.",
                    ephemeral=True
                )
                return
            
            follower_ids = await self.db.get_thread_followers(interaction.channel.id)
        
            if not follower_ids:
                await interaction.response.send_message(
                    "No one is following this thread yet.",
                    ephemeral=True
                )
                return

            followers = []
            for user_id in follower_ids:
                member = interaction.guild.get_member(user_id)
                if member:
                    followers.append(member.display_name)
                else:
                    followers.append(f"Unknown User ({user_id})")

            embed = discord.Embed(
                title=f"👥 Followers of {interaction.channel.name}",
                description="\n".join([f"• {name}" for name in followers]),
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Total followers: {len(followers)}")

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "This command can only be used in threads.",
                ephemeral=True
            )
            return

        thread = interaction.channel

        if thread.owner_id != interaction.user.id or any(role.id == 1440180775512178750 for role in interaction.user.roles):
            await interaction.response.send_message(
                "Only the thread owner can view the followers list.",
                ephemeral=True
            )
            return

        follower_ids = await self.db.get_thread_followers(thread.id)
        
        if not follower_ids:
            await interaction.response.send_message(
                "No one is following this thread yet.",
                ephemeral=True
            )
            return

        followers = []
        for user_id in follower_ids:
            member = interaction.guild.get_member(user_id)
            if member:
                followers.append(member.display_name)
            else:
                followers.append(f"Unknown User ({user_id})")

        embed = discord.Embed(
            title=f"👥 Followers of {thread.name}",
            description="\n".join([f"• {name}" for name in followers]),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Total followers: {len(followers)}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.channel.id == 1440984193181028394:
            if len(message.embeds) < 1:
                return
            
            embed = message.embeds[0]
            if embed.author == "github-actions[bot]" and "crowdin-translations was force-pushed" in embed.title:
                await message.delete()
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
                    description=profanity.censor(target_message.content) or "*No text content*",
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

        twitter_patterns = [
            r'https://(?:www\.)?twitter\.com/\S+',
            r'https://(?:www\.)?x\.com/\S+',
            r'https://vxtwitter\.com/\S+',
            r'https://fxtwitter\.com/\S+',
            r'https://nitter\.net/\S+',
        ]
        
        twitter_links = []
        content = message.content
        for pattern in twitter_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if 'twitter.com' in match or 'x.com' in match:
                    path = re.search(r'(?:twitter|x)\.com(/\S+)', match)
                    if path:
                        xcancel_link = f"https://xcancel.com{path.group(1)}"
                        twitter_links.append(xcancel_link)
                else:
                    xcancel_link = re.sub(r'https://[^/]+', 'https://xcancel.com', match)
                    twitter_links.append(xcancel_link)
        
        if twitter_links:
            links_text = '\n'.join([f"<{link}>" for link in twitter_links])
            await message.reply(f"{links_text}\n-# This is a link that makes it more convenient to share X tweets. XCancel allows you to view tweets without signing in", mention_author=False)

async def setup(bot):
    await bot.add_cog(Utils(bot))
