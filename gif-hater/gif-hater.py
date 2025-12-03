# gif-hater.py - ModMail Plugin
import re
import datetime
import io
from typing import Optional

import discord
from discord.ext import commands
from PIL import Image
import pytesseract

GIF_URL_RE = re.compile(r"https?://[^\s]+\.gif(?:\?[^\s]*)?", re.IGNORECASE)
TENOR_URL_RE = re.compile(r"https?://(?:[\w-]+\.)?tenor\.com/[\w-]+", re.IGNORECASE)
GIPHY_URL_RE = re.compile(r"https?://(?:[\w-]+\.)?giphy\.com/[\w-]+", re.IGNORECASE)


async def check_image_for_phrase(attachment: discord.Attachment, phrase: str = "reset the") -> bool:
    """
    Download an image attachment and use OCR to check if it contains the specified phrase.
    Returns True if the phrase is found (case-insensitive).
    """
    # Check if it's an image
    content_type = getattr(attachment, "content_type", None)
    if not content_type or not content_type.startswith("image/"):
        filename = (attachment.filename or "").lower()
        # Double-check with common image extensions if content_type is missing
        if not any(filename.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]):
            return False

    try:
        # Download the image bytes
        image_bytes = await attachment.read()

        # Open with PIL
        image = Image.open(io.BytesIO(image_bytes))

        # Perform OCR
        text = pytesseract.image_to_string(image)

        # Check if the phrase exists (case-insensitive)
        return phrase.lower() in text.lower()

    except Exception as e:
        # If OCR fails, log and return False to avoid false positives
        print(f"OCR error on {attachment.filename}: {e}")
        return False


def message_contains_gif(message: discord.Message) -> bool:
    """Return True if the message contains a GIF, video, or Tenor/Giphy link via attachment, embed, or URL."""
    # 1) Attachments with .gif filename or GIF content type
    for att in message.attachments:
        filename = (att.filename or "").lower()
        if filename.endswith(".gif"):
            return True
        # some attachments provide content_type like "image/gif"
        if getattr(att, "content_type", None) and "gif" in att.content_type.lower():
            return True

    # 2) Embeds with image, video, or thumbnail - this catches forwarded GIFs
    for emb in message.embeds:
        # Check embed type for common GIF/video platforms
        if getattr(emb, "type", None) in ("gifv", "image", "video"):
            if emb.url:
                url_lower = emb.url.lower()
                if ".gif" in url_lower or "tenor.com" in url_lower or "giphy.com" in url_lower:
                    return True

        # Check for video embeds (forwarded GIFs often appear as video embeds)
        video = getattr(emb, "video", None)
        if video and getattr(video, "url", None):
            # This catches forwarded GIFs that Discord embeds as video
            return True

        # Check for Tenor/Giphy embeds
        if getattr(emb, "url", None):
            url_lower = emb.url.lower()
            if "tenor.com" in url_lower or "giphy.com" in url_lower:
                return True

        # embed.image and embed.thumbnail are discord.EmbedProxy objects with .url
        img = getattr(emb, "image", None)
        thumb = getattr(emb, "thumbnail", None)
        for e in (img, thumb):
            if e and getattr(e, "url", None):
                url_lower = e.url.lower()
                if url_lower.endswith(".gif") or "tenor.com" in url_lower or "giphy.com" in url_lower:
                    return True

        # some embeds (like Giphy) may have a .url pointing to gif
        if getattr(emb, "url", None) and emb.url.lower().endswith(".gif"):
            return True

    # 3) Plain text URLs ending with .gif or Tenor/Giphy links
    if message.content:
        if GIF_URL_RE.search(message.content):
            return True
        if TENOR_URL_RE.search(message.content):
            return True
        if GIPHY_URL_RE.search(message.content):
            return True

    return False


class GifTimeoutCog(commands.Cog):
    """Cog that deletes GIF messages (including Tenor links and replies to GIFs) and times the poster out for 10 seconds."""

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

        # Check if this message contains a GIF
        has_gif = message_contains_gif(message)

        # Check if any image attachments contain "reset the" using OCR
        has_banned_phrase = False
        for attachment in message.attachments:
            if await check_image_for_phrase(attachment, "reset the"):
                has_banned_phrase = True
                break

        # Check if this is a reply/forward to a message with a GIF
        is_gif_reply = False
        if message.reference and message.reference.message_id:
            try:
                # Fetch the referenced message to check for GIF attachments
                referenced_msg = await message.channel.fetch_message(message.reference.message_id)
                if message_contains_gif(referenced_msg):
                    is_gif_reply = True

                # Check if any GIF attachments from the referenced message are showing in embeds
                if referenced_msg.attachments:
                    for att in referenced_msg.attachments:
                        filename = (att.filename or "").lower()
                        if filename.endswith(".gif") or (
                                getattr(att, "content_type", None) and "gif" in att.content_type.lower()):
                            # Check if this attachment URL appears in any of the current message's embeds
                            for emb in message.embeds:
                                if emb.image and att.url in str(getattr(emb.image, "url", "")):
                                    is_gif_reply = True
                                    break
                                if emb.thumbnail and att.url in str(getattr(emb.thumbnail, "url", "")):
                                    is_gif_reply = True
                                    break

                # Check if the referenced message had Tenor embeds that are now showing in this reply
                for ref_emb in referenced_msg.embeds:
                    ref_url = getattr(ref_emb, "url", None)
                    if ref_url and "tenor.com" in ref_url.lower():
                        # Check if this Tenor URL or content appears in the current message's embeds
                        for curr_emb in message.embeds:
                            curr_url = getattr(curr_emb, "url", None)
                            curr_img = getattr(curr_emb, "image", None)
                            curr_thumb = getattr(curr_emb, "thumbnail", None)

                            # Check if Tenor URL is present
                            if curr_url and "tenor.com" in curr_url.lower():
                                is_gif_reply = True
                                break
                            # Check if Tenor content is in image/thumbnail
                            if curr_img and getattr(curr_img, "url", None) and "tenor" in str(curr_img.url).lower():
                                is_gif_reply = True
                                break
                            if curr_thumb and getattr(curr_thumb, "url", None) and "tenor" in str(
                                    curr_thumb.url).lower():
                                is_gif_reply = True
                                break
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                # Can't fetch the message, skip this check
                pass

        # If none of the violations are detected, allow the message
        if not has_gif and not is_gif_reply and not has_banned_phrase:
            return

        # Determine the reason for deletion
        if has_banned_phrase:
            reason = f"Posted image containing banned phrase in #{message.channel} (auto-timeout)"
        else:
            reason = f"Posted/replied with GIF content in #{message.channel} (auto-timeout)"

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
                reason=reason
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