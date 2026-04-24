import discord
from discord.ext import commands
import aiohttp
import io

# Hardcoded forwarding mappings: {source_channel_id: dest_channel_id}
# Add your channel IDs here
FORWARDING_RULES = {
    # Example: 1234567890123456789: 9876543210987654321,
    # Add more mappings as needed
    1497343488482869381: 1497343226368098354, # Live VC
}


class MessageForwarder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.forwarding_rules = FORWARDING_RULES
        # Fallback: All voice channel text chats forward to this thread
        self.vc_fallback_thread_id = 1497340830669734059

    async def download_attachment(self, attachment):
        """Download attachment bytes from Discord."""
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    return await resp.read()
                return None

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

        # Prepare files to re-upload (downloads and stores them)
        files_to_send = []
        if message.attachments:
            for attachment in message.attachments:
                file_bytes = await self.download_attachment(attachment)
                if file_bytes:
                    files_to_send.append(discord.File(
                        fp=io.BytesIO(file_bytes),
                        filename=attachment.filename,
                        spoiler=attachment.is_spoiler()
                    ))

        # Add note about original embeds if any
        if message.embeds:
            embed.add_field(name="📊 Embeds", value=f"{len(message.embeds)} embed(s) in original message", inline=False)

        try:
            # Send embed first
            await dest_channel.send(embed=embed)
            # Send attachments separately so they appear below
            if files_to_send:
                await dest_channel.send(files=files_to_send)
        except discord.Forbidden:
            pass
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(MessageForwarder(bot))
