import requests
import discord
import xml.etree.ElementTree as ET
from discord.ext import commands, tasks

RELEASE_URL = "https://maven.hytale.com/release/com/hypixel/hytale/Server/maven-metadata.xml"
PRE_RELEASE_URL = "https://maven.hytale.com/pre-release/com/hypixel/hytale/Server/maven-metadata.xml"

class UpdateChecker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.modding_news_channel: discord.TextChannel

    @commands.Cog.listener()
    async def on_ready(self):
        self.release_version: str = await self.bot.database.get_latest_patch("release")
        self.pre_release_version: str = await self.bot.database.get_latest_patch("pre-release")
        self.modding_news_channel: discord.TextChannel = self.bot.get_channel(1440346500382064701)
        self.check_for_updates.start()

    @tasks.loop(minutes=1)
    async def check_for_updates(self):
        new_release_version = await self.fetch_version(RELEASE_URL)
        new_pre_release_version = await self.fetch_version(PRE_RELEASE_URL)
        if new_release_version != self.release_version:
            old_version = self.release_version
            self.release_version = new_release_version
            patch_id: int = await self.bot.database.add_patch(new_release_version, "release")
            embed = discord.Embed(title="Game Patches Update", description="New game patch available for release", timestamp=discord.utils.utcnow())
            embed.add_field(name="Patchline", value="`release`")
            embed.add_field(name="Version", value=f"`{new_release_version}`")
            embed.add_field(name="Previous", value=f"`{old_version}`")
            embed.add_field(name="Patch ID", value=f"`{patch_id}`")
            embed.set_thumbnail(url="https://cdn.internal.hytalemodding.dev/assets/hytale-icon.png")
            await self.modding_news_channel.send(embed=embed)

        if new_pre_release_version != self.pre_release_version:
            old_version = self.pre_release_version
            self.pre_release_version = new_pre_release_version
            patch_id: int = await self.bot.database.add_patch(new_pre_release_version, "pre-release")
            embed = discord.Embed(title="Game Patches Update", description="New game patch available for release", timestamp=discord.utils.utcnow())
            embed.add_field(name="Patchline", value="`pre-release`")
            embed.add_field(name="Version", value=f"`{new_pre_release_version}`")
            embed.add_field(name="Previous", value=f"`{old_version}`")
            embed.add_field(name="Patch ID", value=f"`{patch_id}`")
            embed.set_thumbnail(url="https://cdn.internal.hytalemodding.dev/assets/hytale-icon.png")
            await self.modding_news_channel.send(embed=embed)

    async def fetch_version(self, url: str) -> str:
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            root = ET.fromstring(response.content)
            latest_element = root.find(".//latest")
            if latest_element is not None:
                return latest_element.text
            return "unknown"
        except (requests.RequestException, ET.ParseError) as e:
            print(f"Error fetching version: {e}")
            return "unknown"

async def setup(bot: commands.Bot):
    await bot.add_cog(UpdateChecker(bot))