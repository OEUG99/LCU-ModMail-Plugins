import discord
from discord.ext import commands

# Hardcoded forwarding mappings: {source_channel_id: dest_channel_id}
# Add your channel IDs here
FORWARDING_RULES = {
    # Example: 1234567890123456789: 9876543210987654321,
    # Add more mappings as needed
}


class MessageForwarder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.forwarding_rules = FORWARDING_RULES
        # Fallback: All voice channel text chats forward to this thread
        self.vc_fallback_thread_id = 1497340830669734059

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bot messages to prevent loops
        if message.author.bot:
            return

        # Determine destination based on hardcoded rules or fallback
        dest_channel_id = None

        if message.channel.id in self.forwarding_rules:
            # Use hardcoded rule if available (priority)
            dest_channel_id = self.forwarding_rules[message.channel.id]
        elif isinstance(message.channel, discord.VoiceChannel):
            # Fallback: voice channel text chat → specific thread
            dest_channel_id = self.vc_fallback_thread_id

        if not dest_channel_id:
            return

        dest_channel = self.bot.get_channel(dest_channel_id)

        if not dest_channel:
            return

        # Build the forwarded message embed
        embed = discord.Embed(
            description=message.content,
            timestamp=message.created_at,
            color=discord.Color.blurple()
        )
        embed.set_author(name=f"{message.author.name} ({message.author.id})", icon_url=message.author.display_avatar.url)
        embed.set_footer(text=f"From #{message.channel.name}")

        # Add attachments info if any
        if message.attachments:
            attachment_urls = "\n".join([a.url for a in message.attachments])
            embed.add_field(name="📎 Attachments", value=attachment_urls, inline=False)

        # Add embeds info if any (just note their presence)
        if message.embeds:
            embed.add_field(name="📊 Embeds", value=f"{len(message.embeds)} embed(s) in original message", inline=False)

        try:
            await dest_channel.send(embed=embed)
        except discord.Forbidden:
            pass
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(MessageForwarder(bot))
