import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import re
from difflib import SequenceMatcher
import asyncio
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import json

import logging

log = logging.getLogger(__name__)

class Guides(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guides_cache: Dict[str, Dict[str, str]] = {}
        self.sitemap_url = "https://hytalemodding.dev/sitemap.xml"
        self.cache_file = Path(__file__).resolve().parent.parent / "cache" / "guides_cache.json"
        self.last_refresh_at: Optional[str] = None
        self._refresh_lock = asyncio.Lock()
        
    async def cog_load(self):
        """Load guides from disk, then refresh in background"""
        await self.load_guides_cache_from_file()
        if not self.daily_guides_refresh.is_running():
            self.daily_guides_refresh.start()

    def cog_unload(self):
        """Stop the background task when cog is unloaded"""
        if self.daily_guides_refresh.is_running():
            self.daily_guides_refresh.cancel()

    async def load_guides_cache_from_file(self):
        """Load cached guides from local JSON file"""
        if not self.cache_file.exists():
            log.info("Guides cache file not found; starting with empty cache")
            return

        def _read_cache(path: Path):
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)

        try:
            payload = await asyncio.to_thread(_read_cache, self.cache_file)
            guides = payload.get("guides", {})
            if isinstance(guides, dict):
                self.guides_cache = guides
                self.last_refresh_at = payload.get("last_refresh_at")
                log.info(f"Loaded {len(self.guides_cache)} guides from local cache")
            else:
                log.warning("Guides cache file has invalid format; ignoring")
        except Exception as e:
            log.error(f"Error loading guides cache file: {e}")

    async def save_guides_cache_to_file(self):
        """Persist cached guides to local JSON file"""
        payload = {
            "last_refresh_at": self.last_refresh_at,
            "guides": self.guides_cache,
        }

        def _write_cache(path: Path, data: Dict):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=True, indent=2)

        try:
            await asyncio.to_thread(_write_cache, self.cache_file, payload)
        except Exception as e:
            log.error(f"Error saving guides cache file: {e}")
    
    async def fetch_sitemap(self) -> Optional[str]:
        """Fetch the sitemap.xml content"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.sitemap_url) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        log.error(f"Failed to fetch sitemap: HTTP {response.status}")
                        return None
        except Exception as e:
            log.error(f"Error fetching sitemap: {e}")
            return None
    
    async def fetch_page_content(self, session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, str]]:
        """Fetch page content to extract title and description"""
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()

                    title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                    title = title_match.group(1).strip() if title_match else "No Title"

                    desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', content, re.IGNORECASE)
                    if not desc_match:
                        desc_match = re.search(r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']', content, re.IGNORECASE)

                    description = desc_match.group(1).strip() if desc_match else "No description available"

                    return {
                        "title": title,
                        "description": description,
                        "url": url
                    }
        except Exception as e:
            log.error(f"Error fetching page content for {url}: {e}")
            return None
    
    async def refresh_guides_cache(self):
        """Refresh the guides cache from sitemap"""
        async with self._refresh_lock:
            log.info("Refreshing guides cache...")
            sitemap_content = await self.fetch_sitemap()

            if not sitemap_content:
                log.error("Failed to fetch sitemap content")
                return

            try:
                root = ET.fromstring(sitemap_content)

                namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
                urls = root.findall('.//ns:url/ns:loc', namespace)

                if not urls:
                    urls = root.findall('.//url/loc')

                guide_urls = []
                for url_elem in urls:
                    url = url_elem.text
                    if url and '/docs/' in url and '/en/docs/' in url:
                        guide_urls.append(url)

                log.info(f"Found {len(guide_urls)} potential guide URLs")

                new_cache: Dict[str, Dict[str, str]] = {}
                async with aiohttp.ClientSession() as session:
                    for url in guide_urls:
                        guide_data = await self.fetch_page_content(session, url)
                        if guide_data:
                            path = urlparse(url).path
                            new_cache[path] = guide_data

                        await asyncio.sleep(0.1)

                if new_cache:
                    self.guides_cache = new_cache
                    self.last_refresh_at = datetime.now(timezone.utc).isoformat()
                    await self.save_guides_cache_to_file()
                    log.info(f"Cached {len(self.guides_cache)} guides")
                else:
                    log.warning("Guide refresh returned zero guides; keeping existing cache")
            except ET.ParseError as e:
                log.error(f"Error parsing sitemap XML: {e}")
            except Exception as e:
                log.error(f"Error processing sitemap: {e}")

    @tasks.loop(hours=24)
    async def daily_guides_refresh(self):
        """Refresh guide cache once per day in the background"""
        try:
            await self.refresh_guides_cache()
        except Exception as e:
            log.error(f"Error in daily guides refresh: {e}")

    @daily_guides_refresh.before_loop
    async def before_daily_guides_refresh(self):
        await self.bot.wait_until_ready()
        await self.refresh_guides_cache()

    def similarity(self, a: str, b: str) -> float:
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def search_guides(self, query: str, limit: int = 5) -> List[Dict[str, str]]:
        """Search guides based on query"""
        query = query.lower()
        results = []
        
        for path, guide_data in self.guides_cache.items():
            title = guide_data['title'].lower()
            description = guide_data['description'].lower()
            
            title_score = self.similarity(query, title)
            desc_score = self.similarity(query, description)
            
            query_words = query.split()
            title_words = title.split()
            desc_words = description.split()
            
            word_match_score = 0
            for q_word in query_words:
                if any(q_word in t_word for t_word in title_words):
                    word_match_score += 0.3
                if any(q_word in d_word for d_word in desc_words):
                    word_match_score += 0.1
            
            total_score = max(title_score * 2, desc_score) + word_match_score
            
            if total_score > 0.1:
                results.append({
                    'score': total_score,
                    'title': guide_data['title'],
                    'description': guide_data['description'],
                    'url': guide_data['url']
                })
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]
    
    @app_commands.command(name='guides', description='Search for guides based on keywords')
    async def guide_search(self, interaction: discord.Interaction, query: str):
        """Search for guides based on keywords"""
        if not self.guides_cache:
            embed = discord.Embed(
                title="❌ No Guides Cached",
                description="Guide cache is empty. A background refresh is running, please try again shortly.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            asyncio.create_task(self.refresh_guides_cache())
            return
        
        results = self.search_guides(query)
        
        if not results:
            embed = discord.Embed(
                title="❌ No Guides Found",
                description=f"No guides found matching: **{query}**",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            return
        main_result = results[0]

        desc = f"# [{main_result['title']}]({main_result['url']})\n" + main_result['description'] + "\n\n**Not quite what you're looking for?**"
        for i, result in enumerate(results[1:4], 1):
            desc += f"\n- [{result['title']}]({result['url']})"

        embed = discord.Embed(
            description=desc,
            color=0x2F3136
        )

        embed.set_footer(text=f"HytaleModding Search | {len(self.guides_cache)} cached guides", icon_url=self.bot.user.avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='refresh_guides', description='Manually refresh the guides cache (Admin only)')
    @app_commands.default_permissions(administrator=True)
    async def refresh_guides_command(self, interaction: discord.Interaction):
        """Manually refresh the guides cache (Admin only)"""
        embed = discord.Embed(
            title="🔄 Refreshing Guides Cache",
            description="This may take a moment...",
            color=discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed)
        
        await self.refresh_guides_cache()
        
        embed = discord.Embed(
            title="✅ Cache Refreshed",
            description=f"Successfully cached {len(self.guides_cache)} guides",
            color=discord.Color.green()
        )
        await interaction.edit_original_response(embed=embed)
    
    @app_commands.command(name='guide_stats', description='Show statistics about cached guides')
    async def guide_stats(self, interaction: discord.Interaction):
        """Show statistics about cached guides"""
        embed = discord.Embed(
            title="📊 Guide Cache Statistics",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Total Guides Cached",
            value=str(len(self.guides_cache)),
            inline=True
        )
        
        embed.add_field(
            name="Sitemap URL",
            value=self.sitemap_url,
            inline=False
        )

        embed.add_field(
            name="Last Refresh (UTC)",
            value=self.last_refresh_at or "Unknown",
            inline=False
        )

        embed.add_field(
            name="Cache File",
            value=str(self.cache_file),
            inline=False
        )
        
        if self.guides_cache:
            examples = list(self.guides_cache.values())[:3]
            example_text = "\n".join([f"• {guide['title']}" for guide in examples])
            embed.add_field(
                name="Example Guides",
                value=example_text,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Guides(bot))