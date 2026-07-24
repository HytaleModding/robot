import asyncio
from contextlib import suppress

import aiohttp
import os
import discord
from discord import app_commands
from discord.ext import commands


AUTH_BASE_URL = "https://accounts.hytalemodding.dev"
STATUS_AUTH_TOKEN = os.getenv("STATUS_AUTH_TOKEN")
REQUESTED_SCOPES = os.getenv("AUTH_SCOPES")
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 600


class SharedSourceAuthView(discord.ui.View):
    def __init__(self, authorize_url: str):
        super().__init__(timeout=300)
        self.add_item(
            discord.ui.Button(
                label="Authorize with Hytale",
                style=discord.ButtonStyle.url,
                url=authorize_url,
            )
        )


class SharedSource(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.database
        self._poll_tasks: dict[int, asyncio.Task[None]] = {}

    def _build_start_url(self, user_id: int) -> str:
        return f"{AUTH_BASE_URL}/oauth/start?discord_user_id={user_id}"

    def _cancel_poll_task(self, user_id: int) -> None:
        task = self._poll_tasks.pop(user_id, None)
        if task is not None and not task.done():
            task.cancel()

    async def _poll_for_completion(self, interaction: discord.Interaction, user_id: int) -> None:
        deadline = asyncio.get_running_loop().time() + POLL_TIMEOUT_SECONDS

        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    if asyncio.get_running_loop().time() >= deadline:
                        await interaction.followup.send(
                            "The shared source login timed out. Run the command again to retry.",
                            ephemeral=True,
                        )
                        return

                    async with session.get(
                        f"{AUTH_BASE_URL}/sessions/by-discord/{user_id}/latest",
                        headers={"X-Shared-Source-Token": STATUS_AUTH_TOKEN},
                    ) as response:
                        if response.status == 404:
                            await asyncio.sleep(POLL_INTERVAL_SECONDS)
                            continue

                        if response.status == 401:
                            await interaction.followup.send(
                                "Shared source polling was rejected. Check the shared status token.",
                                ephemeral=True,
                            )
                            return

                        payload = await response.json()

                    status = payload.get("status")
                    if status == "pending":
                        await asyncio.sleep(POLL_INTERVAL_SECONDS)
                        continue

                    if status == "error":
                        await interaction.followup.send(
                            (
                                "Shared source verification failed: "
                                f"{payload.get('error_description') or payload.get('error') or 'unknown error'}"
                            ),
                            ephemeral=True,
                        )
                        return

                    if status == "completed":
                        profile_username = payload.get("profile_username") or "the signed-in Hytale account"
                        shared_source = payload.get("shared_source")

                        if shared_source:
                            await interaction.user.add_roles(
                                discord.Object(id=1523120733600088126), # 1523120733600088126
                            )
                            await interaction.followup.send(
                                (
                                    f"Shared source verification completed for {profile_username}. "
                                ),
                                ephemeral=True,
                            )
                            return
                        else:
                            await interaction.followup.send(
                                (
                                    f"You do not have access to the Hytale Shared Source Repositories. Please head to https://accounts.hytale.com/shared-source to request access to the shared source repositories and re-run this command."
                                ),
                                ephemeral=True,
                            )
                            return

                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            with suppress(Exception):
                await interaction.followup.send(
                    f"Shared source polling failed: {exc}",
                    ephemeral=True,
                )
        finally:
            self._poll_tasks.pop(user_id, None)

    @app_commands.command(
        name="shared-source",
        description="Get access to the shared source channel.",
    )
    async def shared_source(self, interaction: discord.Interaction):
        """Get access to the shared source channel."""
        authorize_url = self._build_start_url(interaction.user.id)

        embed = discord.Embed(
            title="Hytale Account Verification",
            description="Click the button below to authorize your Hytale account and get access to the shared source channel. \n\nYou will be prompted to log in to your Hytale account.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Shared Source Disclaimer", value="Per the [Hytale Shared Source License Agreement](https://hytale.com/shared-source-license), please don't share screenshots of the server code, or screenshots of the shared source channel, with anyone who hasn't accepted the agreement. Clicking the button below means you agree to these terms.", inline=False)
        embed.set_thumbnail(url="https://cdn.internal.hytalemodding.dev/assets/hytale-icon.png")

        await interaction.response.send_message(
            embed=embed,
            view=SharedSourceAuthView(authorize_url),
            ephemeral=True,
        )

        self._cancel_poll_task(interaction.user.id)
        self._poll_tasks[interaction.user.id] = asyncio.create_task(
            self._poll_for_completion(interaction, interaction.user.id)
        )

    async def cog_unload(self):
        for task in self._poll_tasks.values():
            task.cancel()
        self._poll_tasks.clear()


async def setup(bot):
    await bot.add_cog(SharedSource(bot))
