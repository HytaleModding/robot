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

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='🎫 Create Ticket', style=discord.ButtonStyle.green, custom_id='create_ticket')
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        
        # Clean username for channel name
        clean_username = re.sub(r'[^a-zA-Z0-9\-_]', '', user.display_name.lower())
        if not clean_username:
            clean_username = f"user{user.id}"
        
        # Check for existing open ticket
        cog = interaction.client.get_cog('Tickets')
        db = cog.bot.db
        
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
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        staff_role = discord.utils.get(guild.roles, name="Staff")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # Create channel with username
        channel_name = f"ticket-{clean_username}"
        counter = 1
        original_name = channel_name
        
        # Handle duplicate names
        while discord.utils.get(guild.channels, name=channel_name):
            channel_name = f"{original_name}-{counter}"
            counter += 1

        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites
        )

        # Store ticket in database
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
        db = cog.bot.db
        
        # Get ticket info from database
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
            
            # Update ticket in database
            await db.close_ticket(channel.id, interaction.user.id, transcript_url)
            
            if transcript_url:
                # Send transcript to ticket owner
                if ticket_owner:
                    try:
                        embed = discord.Embed(
                            title="🎫 Ticket Transcript",
                            description=f"Your ticket `{channel.name}` has been closed.\nYou can view the full transcript using the button below.",
                            color=discord.Color.blue()
                        )
                        embed.add_field(name="Ticket ID", value=f"`{ticket_info['id']}`", inline=True)
                        embed.add_field(name="Closed by", value=interaction.user.mention, inline=True)
                        embed.add_field(name="Closed at", value=discord.utils.format_dt(discord.utils.utcnow()), inline=True)
                        
                        await ticket_owner.send(embed=embed, view=TranscriptView(transcript_url))
                    except discord.Forbidden:
                        pass
                
                # Send to ticket logs channel
                logs_channel = discord.utils.get(interaction.guild.channels, name="ticket-logs")
                if logs_channel:
                    log_embed = discord.Embed(
                        title="🎫 Ticket Closed",
                        description=f"Ticket `{channel.name}` has been closed.",
                        color=discord.Color.orange()
                    )
                    log_embed.add_field(name="Ticket ID", value=f"`{ticket_info['id']}`", inline=True)
                    log_embed.add_field(name="Ticket Owner", value=ticket_owner.mention if ticket_owner else "Unknown", inline=True)
                    log_embed.add_field(name="Closed by", value=interaction.user.mention, inline=True)
                    
                    message_count = 0
                    async for _ in channel.history(limit=None):
                        message_count += 1
                    log_embed.add_field(name="Messages", value=str(message_count), inline=True)
                    
                    await logs_channel.send(embed=log_embed, view=TranscriptView(transcript_url))
                
                staff_channel = interaction.guild.get_channel(1440173445739446366)
                if staff_channel:
                    message_count = len(await channel.history(limit=None).flatten())
                    
                    ticket_created = datetime.fromisoformat(ticket_info['created_at'])
                    ticket_duration = discord.utils.utcnow().replace(tzinfo=None) - ticket_created
                    
                    staff_embed = discord.Embed(
                        title="🎫 Ticket Closed - Staff Notification",
                        description=f"**Ticket:** `{channel.name}` (ID: `{ticket_info['id']}`)",
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow()
                    )
                    
                    staff_embed.add_field(
                        name="👤 Owner", 
                        value=ticket_owner.mention if ticket_owner else f"`{ticket_info['username']}`", 
                        inline=True
                    )
                    staff_embed.add_field(
                        name="🔒 Closed by", 
                        value=interaction.user.mention, 
                        inline=True
                    )
                    staff_embed.add_field(
                        name="📊 Stats", 
                        value=f"Messages: {message_count}\nDuration: {str(ticket_duration).split('.')[0]}", 
                        inline=True
                    )
                    
                    await staff_channel.send(embed=staff_embed, view=TranscriptView(transcript_url))
            
        except Exception as e:
            print(f"Error generating transcript: {e}")
        
        await asyncio.sleep(3)
        await channel.delete()

    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.red)
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Ticket closure cancelled.", ephemeral=True)

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.website_upload_url = "https://archive.hytalemodding.xyz/api/upload-transcript"
        self.website_view_url = "https://archive.hytalemodding.xyz/transcripts/"
        self.upload_token = bot.upload_token

    async def upload_transcript(self, transcript_html, filename):
        """Upload transcript to your website and return the URL"""
        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('file', transcript_html, filename=filename, content_type='text/html')
                data.add_field('token', self.upload_token)
                
                async with session.post(self.website_upload_url, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return f"{self.website_view_url}{filename}"
                    else:
                        print(f"Upload failed with status {response.status}")
                        return None
        except Exception as e:
            print(f"Error uploading transcript: {e}")
            return None

    async def cog_load(self):
        """Add persistent views when the cog loads"""
        self.bot.add_view(TicketView())
        self.bot.add_view(TicketControlView())
        print("Ticket views added!")

    @commands.Cog.listener()
    async def on_ready(self):
        print("Ticket system loaded!")

    @app_commands.command(name="ticket-panel", description="Create a ticket panel")
    @app_commands.describe(channel="The channel to send the ticket panel to")
    async def ticket_panel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return

        target_channel = channel or interaction.channel

        embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Click the button below to create a support ticket.\n\nOur staff team will assist you as soon as possible!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📋 Before creating a ticket:",
            value="• Check FAQ channels\n• Search for existing solutions\n• Be clear about your issue",
            inline=False
        )

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