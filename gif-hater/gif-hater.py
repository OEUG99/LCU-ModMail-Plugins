# gif-hater.py - ModMail Plugin
import re
import datetime
from typing import Optional

import discord
from discord.ext import commands

GIF_URL_RE = re.compile(r"https?://[^\s]+\.gif(?:\?[^\s]*)?", re.IGNORECASE)


def message_contains_gif(message: discord.Message) -> bool:
    """Return True if the message contains a GIF via attachment, embed, or URL."""
    # 1) Attachments with .gif filename or GIF content type
    for att in message.attachments:
        filename = (att.filename or "").lower()
        if filename.endswith(".gif"):
            return True
        # some attachments provide content_type like "image/gif"
        if getattr(att, "content_type", None) and "gif" in att.content_type.lower():
            return True

    # 2) Embeds with image or thumbnail that end with .gif
    for emb in message.embeds:
        # Check embed type for common GIF platforms
        if getattr(emb, "type", None) in ("gifv", "image"):
            if emb.url and ".gif" in emb.url.lower():
                return True

        # embed.image and embed.thumbnail are discord.EmbedProxy objects with .url
        img = getattr(emb, "image", None)
        thumb = getattr(emb, "thumbnail", None)
        for e in (img, thumb):
            if e and getattr(e, "url", None) and e.url.lower().endswith(".gif"):
                return True
        # some embeds (like Giphy) may have a .url pointing to gif
        if getattr(emb, "url", None) and emb.url.lower().endswith(".gif"):
            return True

    # 3) Plain text URLs ending with .gif
    if message.content and GIF_URL_RE.search(message.content):
        return True

    return False


class GifTimeoutCog(commands.Cog):
    """Cog that deletes GIF messages and times the poster out for 10 seconds."""

    def __init__(self, bot: commands.Bot, timeout_seconds: int = 10, target_channel_id: int = 1375291016403222559):
        self.bot = bot
        self.timeout_seconds = timeout_seconds
        self.target_channel_id = target_channel_id

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignore DMs, bots, and messages from the bot itself
        if message.guild is None or message.author.bot:
            return

        # Only process messages in the target channel
        if message.channel.id != self.target_channel_id:
            return

        if not message_contains_gif(message):
            return

        # permissions/safety checks:
        # - Bot needs manage_messages to delete and moderate_members to timeout
        # - Do not timeout members who have moderation perms or are guild owner
        guild = message.guild
        member: Optional[discord.Member] = message.author if isinstance(message.author, discord.Member) else None
        if member is None:
            return  # can't timeout a non-member

        # Skip guild owner and members with manage_messages or moderate_members perms
        try:
            if guild.owner_id == member.id:
                return
        except Exception:
            pass

        # Check member's top-level permissions in the guild (avoid timing out mods/admins)
        member_perms = member.guild_permissions
        if member_perms.manage_guild or member_perms.manage_messages or member_perms.moderate_members or member_perms.administrator:
            # don't timeout staff
            return

        # Try to delete the message first (so GIF doesn't stay visible)
        try:
            await message.delete()
        except discord.Forbidden:
            # bot lacks manage_messages; abort or optionally log
            return
        except discord.NotFound:
            # message already deleted
            pass
        except Exception:
            # other errors; continue to attempt timeout
            pass

        # Apply the timeout
        try:
            await member.timeout(
                datetime.timedelta(seconds=self.timeout_seconds),
                reason=f"Posted a GIF in #{message.channel} (auto-timeout)"
            )
        except discord.Forbidden:
            # bot doesn't have moderate_members permission
            return
        except discord.HTTPException:
            # rate limit, member already timed out, or other API issues
            return
        except Exception:
            # unexpected errors
            return


# Required setup function for ModMail plugin system
async def setup(bot: commands.Bot):
    """Setup function required by ModMail to load this plugin."""
    await bot.add_cog(GifTimeoutCog(bot))