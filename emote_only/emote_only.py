import discord
from discord.ext import commands
import re

# {channel_id: True}
emote_only_channels: dict[int, bool] = {}

EXEMPT_ROLE_IDS = {
    1324176164918525982,  # Host
    1229552048672870420,  # Mod
}

# Matches Discord custom emotes: <:name:id> or <a:name:id>
CUSTOM_EMOTE_RE = re.compile(r'<a?:\w+:\d+>')


class EmoteOnly(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_exempt(self, member: discord.Member) -> bool:
        if member.guild_permissions.administrator:
            return True
        return any(role.id in EXEMPT_ROLE_IDS for role in member.roles)

    @staticmethod
    def is_emotes_only(content: str) -> bool:
        if not content.strip():
            return False
        # Remove all custom emotes, then check if only whitespace remains
        stripped = CUSTOM_EMOTE_RE.sub('', content).strip()
        if not stripped:
            return True
        # Check if remaining text is only Unicode emoji
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001f926-\U0001f937"
            "\U00010000-\U0010ffff"
            "\u200d"  # zero width joiner
            "\u2640-\u2642"
            "\u2600-\u2B55"
            "\u23cf"
            "\u23e9"
            "\u23f0"
            "\u23f3"
            "\u2580-\u25ff"
            "\u2702"
            "\u2705"
            "\u2764"
            "\ufe0f"  # variation selector
            "]+",
            re.UNICODE
        )
        # If the entire stripped content is composed of emoji, allow it
        non_emoji = emoji_pattern.sub('', stripped).strip()
        return len(non_emoji) == 0

    @commands.command(name="emoteonly")
    @commands.has_permissions(manage_channels=True)
    async def enable_emote_only(self, ctx):
        """Enable emote-only mode in this channel."""
        emote_only_channels[ctx.channel.id] = True
        await ctx.send(
            f"🔒 Emote-only mode enabled in {ctx.channel.mention}."
        )

    @commands.command(name="emoteonlyoff")
    @commands.has_permissions(manage_channels=True)
    async def disable_emote_only(self, ctx):
        """Disable emote-only mode in this channel."""
        if ctx.channel.id in emote_only_channels:
            del emote_only_channels[ctx.channel.id]
            await ctx.send(
                f"🔓 Emote-only mode disabled in {ctx.channel.mention}."
            )
        else:
            await ctx.send("Emote-only mode is not active in this channel.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.channel.id not in emote_only_channels:
            return
        if self.is_exempt(message.author):
            return

        content = message.content.strip()
        if not content:
            return

        if self.is_emotes_only(content):
            return

        try:
            await message.delete()
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(EmoteOnly(bot))
