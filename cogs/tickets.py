import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
import chat_exporter
import aiohttp
import aiofiles
from datetime import datetime
import re
import logging

from config import ConfigSchema

log = logging.getLogger(__name__)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='🎫 Create Ticket', style=discord.ButtonStyle.green, custom_id='create_ticket')
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        
        clean_username = re.sub(r'[^a-zA-Z0-9\-_]', '', user.display_name.lower())
        if not clean_username:
            clean_username = f"user{user.id}"
        
        cog = interaction.client.get_cog('Tickets')
        db = cog.bot.database
        
        existing_tickets = await db.get_user_tickets(guild.id, user.id, 1)
        if existing_tickets and any(ticket['status'] == 'open' for ticket in existing_tickets):
            await interaction.response.send_message("You already have an open ticket!", ephemeral=True)
            return

        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.bot.staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        staff_role = discord.utils.get(guild.roles, name="Staff")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel_name = f"ticket-{clean_username}"
        counter = 1
        original_name = channel_name
        
        while discord.utils.get(guild.channels, name=channel_name):
            channel_name = f"{original_name}-{counter}"
            counter += 1

        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites
        )

        ticket_id = await db.create_ticket(guild.id, channel.id, user.id, user.display_name)

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=f"Hello {user.mention}! Thank you for creating a ticket.\nPlease describe your issue and a staff member will assist you shortly.",
            color=discord.Color.green()
        )
        embed.add_field(name="Ticket Owner", value=user.mention, inline=True)
        embed.add_field(name="Ticket ID", value=f"`{ticket_id}`", inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(discord.utils.utcnow()), inline=True)

        await channel.send(embed=embed, view=TicketControlView())

        await interaction.response.send_message(f"Ticket created! {channel.mention}", ephemeral=True)

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='🔒 Close Ticket', style=discord.ButtonStyle.red, custom_id='close_ticket')
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🔒 Close Ticket",
            description="Are you sure you want to close this ticket?",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=ConfirmCloseView(), ephemeral=True)

class TranscriptView(discord.ui.View):
    def __init__(self, transcript_url):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label='📄 View Transcript',
            style=discord.ButtonStyle.url,
            url=transcript_url
        ))

class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label='✅ Confirm', style=discord.ButtonStyle.green)
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        cog = interaction.client.get_cog('Tickets')
        db = cog.bot.database
        config: ConfigSchema = cog.bot.config
        
        ticket_info = await db.get_ticket_by_channel(channel.id)
        if not ticket_info:
            await interaction.response.send_message("Ticket not found in database!", ephemeral=True)
            return
        
        ticket_owner = interaction.guild.get_member(ticket_info['user_id'])
        
        await interaction.response.send_message("Generating transcript and closing ticket...", ephemeral=True)
        
        try:
            transcript = await chat_exporter.export(
                channel,
                limit=None,
                tz_info="UTC",
                guild=interaction.guild,
                bot=interaction.client
            )
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ticket_{ticket_info['id']}_{timestamp}.html"
            
            transcript_url = await cog.upload_transcript(transcript, filename)
            
            await db.close_ticket(channel.id, interaction.user.id, transcript_url)
            
            if transcript_url:
                embed = discord.Embed(
                    title="🎫 Ticket Transcript",
                    description=f"Your ticket `{channel.name}` has been closed.\nYou can view the full transcript using the button below.",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Ticket ID", value=f"`{ticket_info['id']}`", inline=True)
                embed.add_field(name="Closed by", value=interaction.user.mention, inline=True)
                embed.add_field(name="Closed at", value=discord.utils.format_dt(discord.utils.utcnow()), inline=True)
                if ticket_owner:
                    try:
                        await ticket_owner.send(embed=embed, view=TranscriptView(transcript_url))
                    except discord.Forbidden:
                        pass
                
                logs_channel = interaction.guild.get_channel(config.cogs.tickets.logs_channel_id)
                if logs_channel:
                    await logs_channel.send(embed=embed, view=TranscriptView(transcript_url))
                
        except Exception as e:
            log.error(f"Error generating transcript: {e}")
        
        await asyncio.sleep(3)
        await channel.delete()

    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.red)
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Ticket closure cancelled.", ephemeral=True)

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config: ConfigSchema = bot.config
        self.cog_config = self.config.cogs.tickets

        self.upload_token = bot.upload_token

    async def upload_transcript(self, transcript_html, filename):
        """Upload transcript to your website and return the URL"""
        try:
            if self.cog_config.website_upload_url is None or self.cog_config.website_view_url is None:
                raise ValueError("Website upload and view URL must be set")

            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('file', transcript_html, filename=filename, content_type='text/html')
                data.add_field('token', self.upload_token)
                
                async with session.post(self.cog_config.website_upload_url, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return f"{self.cog_config.website_view_url}{filename}"
                    else:
                        log.error(f"Upload failed with status {response.status}")
                        return None
        except Exception as e:
            log.error(f"Error uploading transcript: {e}")
            return None

    async def cog_load(self):
        """Add persistent views when the cog loads"""
        self.bot.add_view(TicketView())
        self.bot.add_view(TicketControlView())
        log.info("Ticket views added!")

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Ticket system loaded!")

    @app_commands.command(name="ticket-panel", description="Create a ticket panel")
    @app_commands.describe(channel="The channel to send the ticket panel to")
    async def ticket_panel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return

        target_channel = channel or interaction.channel

        embed = discord.Embed(
            description="Click the button below to create a ticket. This is for support regarding the server, or our libraries. For questions regarding how to Mod Hytale, please use the <#1440188811538862131> channel.",
            color=discord.Color.blue()
        )
        embed.set_author(name="Ticket")

        await target_channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message(f"Ticket panel created in {target_channel.mention}!", ephemeral=True)

    @app_commands.command(name="add-user", description="Add a user to the current ticket")
    @app_commands.describe(user="The user to add to the ticket")
    async def add_user(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("This command can only be used in ticket channels!", ephemeral=True)
            return

        ticket_info = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket_info:
            await interaction.response.send_message("Ticket not found in database!", ephemeral=True)
            return

        ticket_owner_id = ticket_info['user_id']
        staff_role = discord.utils.get(interaction.guild.roles, name="Staff")
        
        if interaction.user.id != ticket_owner_id and (not staff_role or staff_role not in interaction.user.roles) and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to add users to this ticket!", ephemeral=True)
            return

        await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
        await self.bot.db.add_ticket_participant(ticket_info['id'], user.id, interaction.user.id)
        
        await interaction.response.send_message(f"{user.mention} has been added to this ticket.")

    @app_commands.command(name="remove-user", description="Remove a user from the current ticket")
    @app_commands.describe(user="The user to remove from the ticket")
    async def remove_user(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("This command can only be used in ticket channels!", ephemeral=True)
            return

        ticket_info = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket_info:
            await interaction.response.send_message("Ticket not found in database!", ephemeral=True)
            return

        ticket_owner_id = ticket_info['user_id']
        staff_role = discord.utils.get(interaction.guild.roles, name="Staff")
        
        if interaction.user.id != ticket_owner_id and (not staff_role or staff_role not in interaction.user.roles) and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to remove users from this ticket!", ephemeral=True)
            return

        if user.id == ticket_owner_id:
            await interaction.response.send_message("You cannot remove the ticket owner!", ephemeral=True)
            return

        await interaction.channel.set_permissions(user, overwrite=None)
        await self.bot.db.remove_ticket_participant(ticket_info['id'], user.id)
        
        await interaction.response.send_message(f"{user.mention} has been removed from this ticket.")

    @app_commands.command(name="close", description="Close the current ticket")
    async def close_ticket_command(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("This command can only be used in ticket channels!", ephemeral=True)
            return

        ticket_info = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket_info:
            await interaction.response.send_message("Ticket not found in database!", ephemeral=True)
            return

        ticket_owner_id = ticket_info['user_id']
        staff_role = discord.utils.get(interaction.guild.roles, name="Staff")
        
        if interaction.user.id != ticket_owner_id and (not staff_role or staff_role not in interaction.user.roles) and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to close this ticket!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔒 Close Ticket",
            description="Are you sure you want to close this ticket?",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=ConfirmCloseView())

    @app_commands.command(name="ticket-info", description="Get information about the current ticket")
    async def ticket_info(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("This command can only be used in ticket channels!", ephemeral=True)
            return

        ticket_info = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket_info:
            await interaction.response.send_message("Ticket not found in database!", ephemeral=True)
            return

        ticket_owner = interaction.guild.get_member(ticket_info['user_id'])
        
        embed = discord.Embed(
            title="🎫 Ticket Information",
            color=discord.Color.blue()
        )
        embed.add_field(name="Ticket ID", value=f"`{ticket_info['id']}`", inline=True)
        embed.add_field(name="Ticket Owner", value=ticket_owner.mention if ticket_owner else f"Unknown (`{ticket_info['username']}`)", inline=True)
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(datetime.fromisoformat(ticket_info['created_at'])), inline=True)
        embed.add_field(name="Status", value=ticket_info['status'].title(), inline=True)
        
        message_count = 0
        async for _ in interaction.channel.history(limit=None):
            message_count += 1
        
        embed.add_field(name="Messages", value=str(message_count), inline=True)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ticket-stats", description="Get ticket statistics")
    async def ticket_stats(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return

        stats = await self.bot.db.get_ticket_stats(interaction.guild.id)
        
        embed = discord.Embed(
            title="🎫 Ticket Statistics",
            color=discord.Color.blue()
        )
        embed.add_field(name="Total Tickets", value=stats['total'], inline=True)
        embed.add_field(name="Open Tickets", value=stats['open'], inline=True)
        embed.add_field(name="Closed Tickets", value=stats['closed'], inline=True)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Tickets(bot))