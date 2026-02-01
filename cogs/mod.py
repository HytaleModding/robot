import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta

from config import ConfigSchema


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database
        self.config: ConfigSchema = bot.config
        self.cog_config = self.config.cogs.mod
    
    async def log_to_channel(self, guild: discord.Guild, embed: discord.Embed):
        """Send log embed to configured mod log channel"""
        channel_id = await self.db.get_log_channel(guild.id)
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except:
                    pass
    
    # Config commands
    @app_commands.command(name="setlogchannel", description="Set the moderation log channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.db.set_log_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(f"✅ Mod log channel set to {channel.mention}", ephemeral=True)
    
    # Moderation commands
    @app_commands.command(name="warn", description="Warn a user")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, rule: str, reason: str = "No reason provided"):
        await interaction.response.defer(ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.followup.send("❌ You cannot warn someone with a higher or equal role.", ephemeral=True)
        
        warning_id = await self.db.add_warning(interaction.guild.id, member.id, interaction.user.id, reason)
        await self.db.log_action(interaction.guild.id, "warn", member.id, interaction.user.id, reason)
        
        warnings = await self.db.get_warnings(interaction.guild.id, member.id)
        warning_count = len(warnings)
        reason = f"{rule} - {reason}"
        
        embed = discord.Embed(
            title="⚠️ User Warned",
            color=discord.Color.yellow(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Warning ID", value=f"#{warning_id}", inline=True)
        embed.add_field(name="Total Warnings", value=f"{warning_count}", inline=True)
        
        await self.log_to_channel(interaction.guild, embed)
        
        try:
            dm_embed = discord.Embed(
                title=f"⚠️ Warning from {interaction.guild.name}",
                color=discord.Color.yellow(),
                timestamp=datetime.utcnow()
            )
            dm_embed.add_field(name="Reason", value=reason, inline=False)
            dm_embed.add_field(name="Total Warnings", value=f"{warning_count}", inline=False)
            dm_embed.set_footer(text="Create a support ticket to dispute this warning.", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            await member.send(embed=dm_embed)
        except:
            pass
        
        await interaction.followup.send(f"✅ {member.mention} has been warned. Total warnings: {warning_count}", ephemeral=True)
    
    @app_commands.command(name="warnings", description="Check warnings for a user")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)
        warnings = await self.db.get_warnings(interaction.guild.id, member.id)
        
        if not warnings:
            return await interaction.followup.send(f"{member.mention} has no warnings.", ephemeral=True)
        
        embed = discord.Embed(
            title=f"⚠️ Warnings for {member}",
            color=discord.Color.yellow(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        for idx, warn in enumerate(warnings[:10], 1):
            mod = interaction.guild.get_member(warn['moderator_id'])
            mod_name = mod.mention if mod else f"ID: {warn['moderator_id']}"
            timestamp = warn['timestamp'].strftime("%Y-%m-%d %H:%M UTC")
            
            embed.add_field(
                name=f"Warning #{warn['id']} - {timestamp}",
                value=f"**Moderator:** {mod_name}\n**Reason:** {warn['reason']}",
                inline=False
            )
        
        if len(warnings) > 10:
            embed.set_footer(text=f"Showing 10 of {len(warnings)} warnings")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="clearwarnings", description="Clear all warnings for a user")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def clear_warnings(self, interaction: discord.Interaction, member: discord.Member):
        count = await self.db.clear_warnings(interaction.guild.id, member.id)
        await self.db.log_action(interaction.guild.id, "clear_warnings", member.id, interaction.user.id, f"Cleared {count} warnings")
        
        embed = discord.Embed(
            title="🗑️ Warnings Cleared",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
        embed.add_field(name="Warnings Cleared", value=f"{count}", inline=False)
        
        await self.log_to_channel(interaction.guild, embed)
        await interaction.response.send_message(f"✅ Cleared {count} warning(s) for {member.mention}", ephemeral=True)
    
    @app_commands.command(name="kick", description="Kick a user from the server")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await interaction.response.defer(ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ You cannot kick someone with a higher or equal role.", ephemeral=True)
        
        try:
            dm_embed = discord.Embed(
                title=f"👢 Kicked from {interaction.guild.name}",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            dm_embed.add_field(name="Reason", value=reason, inline=False)
            await member.send(embed=dm_embed)
        except:
            pass
        
        await member.kick(reason=f"{interaction.user}: {reason}")
        await self.db.log_action(interaction.guild.id, "kick", member.id, interaction.user.id, reason)
        
        embed = discord.Embed(
            title="👢 User Kicked",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        await self.log_to_channel(interaction.guild, embed)
        await interaction.followup.send(f"✅ {member} has been kicked.", ephemeral=True)
    
    @app_commands.command(name="ban", description="Ban a user from the server")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_messages: int = 0):
        await interaction.response.defer(ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ You cannot ban someone with a higher or equal role.", ephemeral=True)
        
        try:
            dm_embed = discord.Embed(
                title=f"🔨 Banned from {interaction.guild.name}",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            dm_embed.add_field(name="Reason", value=reason, inline=False)
            await member.send(embed=dm_embed)
        except:
            pass
        
        await member.ban(reason=f"{interaction.user}: {reason}", delete_message_days=delete_messages)
        await self.db.log_action(interaction.guild.id, "ban", member.id, interaction.user.id, reason)
        
        embed = discord.Embed(
            title="🔨 User Banned",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        await self.log_to_channel(interaction.guild, embed)
        await interaction.followup.send(f"✅ {member} has been banned.", ephemeral=True)
    
    @app_commands.command(name="unban", description="Unban a user")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        try:
            user_id = int(user_id)
            user = await self.bot.fetch_user(user_id)
            await interaction.guild.unban(user, reason=f"{interaction.user}: {reason}")
            await self.db.log_action(interaction.guild.id, "unban", user.id, interaction.user.id, reason)
            
            embed = discord.Embed(
                title="✅ User Unbanned",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
            embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await self.log_to_channel(interaction.guild, embed)
            await interaction.response.send_message(f"✅ {user} has been unbanned.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("❌ User not found or not banned.", ephemeral=True)
    
    @app_commands.command(name="timeout", description="Timeout a user")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
        """Timeout a user for a specified duration in minutes"""
        await interaction.response.defer(ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ You cannot timeout someone with a higher or equal role.", ephemeral=True)
        
        if duration < 1 or duration > 40320:  # Max 28 days
            return await interaction.response.send_message("❌ Duration must be between 1 minute and 40320 minutes (28 days).", ephemeral=True)
        
        timeout_until = discord.utils.utcnow() + timedelta(minutes=duration)
        
        try:
            await member.timeout(timeout_until, reason=f"{interaction.user}: {reason}")
            await self.db.log_action(interaction.guild.id, "timeout", member.id, interaction.user.id, reason, duration)
            
            # Calculate duration display
            if duration < 60:
                duration_text = f"{duration} minute{'s' if duration != 1 else ''}"
            elif duration < 1440:
                hours = duration // 60
                mins = duration % 60
                duration_text = f"{hours} hour{'s' if hours != 1 else ''}"
                if mins > 0:
                    duration_text += f" {mins} minute{'s' if mins != 1 else ''}"
            else:
                days = duration // 1440
                hours = (duration % 1440) // 60
                duration_text = f"{days} day{'s' if days != 1 else ''}"
                if hours > 0:
                    duration_text += f" {hours} hour{'s' if hours != 1 else ''}"
            
            embed = discord.Embed(
                title="🔇 User Timed Out",
                color=discord.Color.dark_gray(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="Duration", value=duration_text, inline=True)
            embed.add_field(name="Until", value=f"<t:{int(timeout_until.timestamp())}:F>", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await self.log_to_channel(interaction.guild, embed)
            
            try:
                dm_embed = discord.Embed(
                    title=f"🔇 Timed Out in {interaction.guild.name}",
                    color=discord.Color.dark_gray(),
                    timestamp=datetime.utcnow()
                )
                dm_embed.add_field(name="Duration", value=duration_text, inline=False)
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                await member.send(embed=dm_embed)
            except:
                pass

            await interaction.followup.send(f"✅ {member.mention} has been timed out for {duration_text}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to timeout this user.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="untimeout", description="Remove timeout from a user")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await interaction.response.defer(ephemeral=True)
        if member.timed_out_until is None:
            return await interaction.response.send_message("❌ User is not timed out.", ephemeral=True)
        
        try:
            await member.timeout(None, reason=f"{interaction.user}: {reason}")
            await self.db.log_action(interaction.guild.id, "untimeout", member.id, interaction.user.id, reason)
            
            embed = discord.Embed(
                title="🔊 Timeout Removed",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await self.log_to_channel(interaction.guild, embed)
            await interaction.followup.send(f"✅ {member.mention}'s timeout has been removed.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to remove timeout from this user.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="history", description="View moderation history for a user")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def history(self, interaction: discord.Interaction, member: discord.Member):
        history = await self.db.get_user_history(interaction.guild.id, member.id)
        
        if not history:
            return await interaction.response.send_message(f"{member.mention} has no moderation history.", ephemeral=True)
        
        embed = discord.Embed(
            title=f"📜 Moderation History for {member}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        for idx, action in enumerate(history[:10], 1):
            mod = interaction.guild.get_member(action['moderator_id'])
            mod_name = mod.mention if mod else f"ID: {action['moderator_id']}"
            timestamp = action['timestamp'].strftime("%Y-%m-%d %H:%M UTC")

            duration = f" ({action['duration']} min)" if action['duration'] else ""
            embed.add_field(
                name=f"{action['action_type'].upper()}{duration} - {timestamp}",
                value=f"**Moderator:** {mod_name}\n**Reason:** {action['reason'] or 'N/A'}",
                inline=False
            )
        
        if len(history) > 10:
            embed.set_footer(text=f"Showing 10 of {len(history)} actions")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command()
    async def deletepost(self, interaction: discord.Interaction, reason: str):
        """Delete a thread"""
    
        if not isinstance(interaction.channel, discord.Thread):
            return await interaction.response.send_message("❌ This command can only be used in a thread.", ephemeral=True)
        
        if not interaction.user.guild_permissions.manage_threads:
            return await interaction.response.send_message("❌ You do not have permission to delete threads.", ephemeral=True)
        channel: discord.Thread = interaction.channel  # type: ignore
        owner = channel.owner
        e = discord.Embed(title="Your thread has been deleted", description="Our staff have flagged the contents of your thread to be in violation of our server rules.", color=discord.Color.red())
        await owner.send(embed=e)
        await channel.delete(reason=f"Thread deleted by {interaction.user} | Reason: {reason}")
        e = discord.Embed(title="Thread Deleted", description=f"Thread '{channel.name}' has been deleted by {interaction.user.mention}. Reason: {reason}", color=discord.Color.orange())
        await self.log_to_channel(interaction.guild, e)

    @warn.autocomplete("rule")
    async def rule_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        rules = self.cog_config.rules
        return [
            app_commands.Choice(name=rule, value=rule)
            for rule in rules if current.lower() in rule.lower()
        ][:25]
    
async def setup(bot):
    await bot.add_cog(Moderation(bot))