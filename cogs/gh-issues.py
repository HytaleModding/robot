import discord
from discord.ext import commands
import aiohttp
import re

class GitHubIssues(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.known_repos = {
            'site': 'hytalemodding/site',
            'robot': 'hytalemodding/robot',
            'archive': 'hytalemodding/archive',
        }
        self.github_api_base = 'https://api.github.com/repos'
        
        self.status_emojis = {
            'pr_open': '<:PROpen:1441898066830430218>',
            'pr_closed': '<:PRClosed:1441898059071230043>',
            'pr_merged': '<:PRMerged:1441898064779546726>',
            'pr_draft': '<:PRDraft:1441898061830819970>',
            'issue_closed': '<:IssueClosed:1441898085616713818>',
            'issue_not_planned': '<:IssueNotPlanned:1441898087802077214>',
            'issue_open': '<:IssueOpen:1441898090234646598>',
            'commit': '📝'
        }

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        pattern = r'(\w+)#([a-fA-F0-9]+|\d+)'
        matches = re.findall(pattern, message.content)
        
        if not matches:
            return
        
        valid_matches = []
        seen_items = set()
        
        for repo_name, identifier in matches:
            if repo_name.lower() in self.known_repos:
                item_key = (repo_name.lower(), identifier)
                if item_key not in seen_items:
                    seen_items.add(item_key)
                    valid_matches.append((repo_name.lower(), identifier))
        
        if valid_matches:
            await self.send_items_embed(message, valid_matches)

    async def send_items_embed(self, message, matches):
        items_data = []
        
        async with aiohttp.ClientSession() as session:
            for repo_name, identifier in matches:
                repo_path = self.known_repos[repo_name]
                
                try:
                    if re.match(r'^[a-fA-F0-9]+$', identifier) and len(identifier) >= 7:
                        url = f"{self.github_api_base}/{repo_path}/commits/{identifier}"
                        async with session.get(url) as response:
                            if response.status == 200:
                                data = await response.json()
                                items_data.append((data, repo_name, 'commit'))
                                continue
                    
                    if identifier.isdigit():
                        url = f"{self.github_api_base}/{repo_path}/issues/{identifier}"
                        async with session.get(url) as response:
                            if response.status == 200:
                                data = await response.json()
                                items_data.append((data, repo_name, 'issue'))
                            elif response.status == 404:
                                url = f"{self.github_api_base}/{repo_path}/pulls/{identifier}"
                                async with session.get(url) as pr_response:
                                    if pr_response.status == 200:
                                        data = await pr_response.json()
                                        items_data.append((data, repo_name, 'pr'))
                except:
                    continue
        
        if items_data:
            embed = self.create_combined_embed(items_data)
            await message.reply(embed=embed)

    def get_priority_label(self, labels):
        """Extract priority from labels if exists"""
        for label in labels:
            if label['name'].lower().startswith('priority:'):
                return label['name']
        return None

    def get_status_emoji(self, data, item_type):
        """Get appropriate emoji based on item type and status"""
        if item_type == 'issue':
            if data['state'] == 'open':
                return self.status_emojis['issue_open']
            elif data.get('state_reason') == 'not_planned':
                return self.status_emojis['issue_not_planned']
            else:
                return self.status_emojis['issue_closed']
        elif item_type == 'pr':
            if data['merged']:
                return self.status_emojis['pr_merged']
            elif data['state'] == 'open':
                if data.get('draft', False):
                    return self.status_emojis['pr_draft']
                else:
                    return self.status_emojis['pr_open']
            else:
                return self.status_emojis['pr_closed']
        else:  # commit
            return self.status_emojis['commit']

    def create_combined_embed(self, items_data):
        embed = discord.Embed(color=discord.Color.blue())
        
        description_lines = []
        
        for data, repo_name, item_type in items_data:
            status_emoji = self.get_status_emoji(data, item_type)
            
            if item_type == 'commit':
                commit_sha = data['sha'][:7]
                commit_message = data['commit']['message'].split('\n')[0] 
                if len(commit_message) > 50:
                    commit_message = commit_message[:47] + "..."
                
                line = f"{status_emoji} **[{repo_name}]** [`{commit_sha}`]({data['html_url']}) {commit_message}"
            else:
                priority = self.get_priority_label(data.get('labels', []))
                priority_text = f" `{priority}`" if priority else ""
                
                line = f"{status_emoji} **[{repo_name}]** [#{data['number']} {data['title']}]({data['html_url']}){priority_text}"
            
            description_lines.append(line)
        
        embed.description = '\n'.join(description_lines)
        return embed

    def create_issue_embed(self, data, repo_name):
        if data['state'] == 'open':
            status_emoji = self.status_emojis['issue_open']
            color = discord.Color.green()
        elif data.get('state_reason') == 'not_planned':
            status_emoji = self.status_emojis['issue_not_planned']
            color = discord.Color.greyple()
        else:
            status_emoji = self.status_emojis['issue_closed']
            color = discord.Color.red()
        
        priority = self.get_priority_label(data.get('labels', []))
        priority_text = f" • Priority: {priority}" if priority else ""
        
        embed = discord.Embed(
            description=f"{status_emoji} **[{repo_name}]** #{data['number']} {data['title']}",
            url=data['html_url'],
            color=color
        )
        footer_text = f"by {data['user']['login']}{priority_text}"
        embed.set_footer(text=footer_text)
        
        return embed

    def create_pr_embed(self, data, repo_name):
        if data['merged']:
            status_emoji = self.status_emojis['pr_merged']
            color = discord.Color.purple()
        elif data['state'] == 'open':
            if data.get('draft', False):
                status_emoji = self.status_emojis['pr_draft']
                color = discord.Color.greyple()
            else:
                status_emoji = self.status_emojis['pr_open']
                color = discord.Color.blue()
        else:
            status_emoji = self.status_emojis['pr_closed']
            color = discord.Color.red()
        
        priority = self.get_priority_label(data.get('labels', []))
        priority_text = f" • Priority: {priority}" if priority else ""
        
        embed = discord.Embed(
            description=f"{status_emoji} **[{repo_name}]** #{data['number']} {data['title']}",
            url=data['html_url'],
            color=color
        )
        
        footer_text = f"by {data['user']['login']} • {data['head']['ref']} → {data['base']['ref']}{priority_text}"
        embed.set_footer(text=footer_text)
        
        return embed

    def create_commit_embed(self, data, repo_name):
        commit_sha = data['sha'][:7]
        commit_message = data['commit']['message']
        author = data['commit']['author']['name']
        
        message_lines = commit_message.split('\n')
        title = message_lines[0]
        
        embed = discord.Embed(
            description=f"{self.status_emojis['commit']} **[{repo_name}]** [`{commit_sha}`]({data['html_url']}) {title}",
            color=discord.Color.orange()
        )
        
        embed.set_footer(text=f"by {author}")
        
        return embed

async def setup(bot):
    await bot.add_cog(GitHubIssues(bot))