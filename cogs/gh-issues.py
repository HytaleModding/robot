import discord
from discord.ext import commands
import aiohttp
import re

class GitHubIssues(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.known_repos = {
            'site': 'hytalemodding/site',
            'robot': 'hytalemodding/robot'
        }
        self.github_api_base = 'https://api.github.com/repos'
        
        self.status_emojis = {
            'pr_open': '<:PROpen:1441898066830430218>',
            'pr_closed': '<:PRClosed:1441898059071230043>',
            'pr_merged': '<:PRMerged:1441898064779546726>',
            'pr_draft': '<:PRDraft:1441898061830819970>',
            'issue_closed': '<:IssueClosed:1441898085616713818>',
            'issue_not_planned': '<:IssueNotPlanned:1441898087802077214>',
            'issue_open': '<:IssueOpen:1441898090234646598>'
        }

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        pattern = r'(\w+)#(\d+)'
        matches = re.findall(pattern, message.content)
        
        if not matches:
            return
        
        valid_matches = []
        for repo_name, issue_number in matches:
            if repo_name.lower() in self.known_repos:
                valid_matches.append((repo_name.lower(), issue_number))
        
        if valid_matches:
            await self.send_issues_embed(message, valid_matches)

    async def send_issues_embed(self, message, matches):
        issues_data = []
        
        async with aiohttp.ClientSession() as session:
            for repo_name, issue_number in matches:
                repo_path = self.known_repos[repo_name]
                
                try:
                    url = f"{self.github_api_base}/{repo_path}/issues/{issue_number}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            issues_data.append((data, repo_name, 'issue'))
                        elif response.status == 404:
                            # If issue not found, try as PR
                            url = f"{self.github_api_base}/{repo_path}/pulls/{issue_number}"
                            async with session.get(url) as pr_response:
                                if pr_response.status == 200:
                                    data = await pr_response.json()
                                    issues_data.append((data, repo_name, 'pr'))
                except:
                    continue
        
        if issues_data:
            embed = self.create_combined_embed(issues_data)
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
        else:  # PR
            if data['merged']:
                return self.status_emojis['pr_merged']
            elif data['state'] == 'open':
                if data.get('draft', False):
                    return self.status_emojis['pr_draft']
                else:
                    return self.status_emojis['pr_open']
            else:
                return self.status_emojis['pr_closed']

    def create_combined_embed(self, issues_data):
        embed = discord.Embed(color=discord.Color.blue())
        
        description_lines = []
        
        for data, repo_name, item_type in issues_data:
            status_emoji = self.get_status_emoji(data, item_type)
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

async def setup(bot):
    await bot.add_cog(GitHubIssues(bot))