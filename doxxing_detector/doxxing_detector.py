from __future__ import annotations

import datetime
import re

import discord
from discord.ext import commands


TIMEOUT_DURATION = datetime.timedelta(hours=3)
LOG_CHANNEL_ID = 1497340655423324309
AUTO_FLAG_DM = (
    "Your message was automatically flagged by the moderation bot for possible private personal information "
    "and was removed. If this was a mistake, please message Mod Mail so the moderation team can review it."
)
EXEMPT_ROLE_IDS = {
    1372753814528065696,
    1372754405711155230,
    1324176164918525982,
    1426719967914491925,
    1372741169385050112,
}

EMAIL_RE = re.compile(
    r"(?<![\w.+-])"
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
    r"(?![\w.+-])",
    re.IGNORECASE,
)

PHONE_RE = re.compile(
    r"(?<!\w)"
    r"(?:\+?1[\s.-]?)?"
    r"(?:\(\d{3}\)|\d{3})"
    r"[\s.-]?"
    r"\d{3}"
    r"[\s.-]?"
    r"\d{4}"
    r"(?!\w)"
)

DISCORD_TIMESTAMP_RE = re.compile(r"<t:\d{1,12}(?::[A-Za-z])?>")
GAME_SCORE_RE = re.compile(r"\b\d+\s*v(?:s\.?|ersus)?\s*\d+\b", re.IGNORECASE)

STREET_SUFFIX_RE = (
    r"street|st|avenue|ave|road|rd|drive|dr|lane|ln|court|ct|circle|cir|"
    r"boulevard|blvd|terrace|ter|trail|trl|parkway|pkwy|"
    r"highway|hwy|route|rte|apartment|apt|suite|ste|unit"
)

ADDRESS_RE = re.compile(
    r"(?<!\w)"
    r"(?P<number>\d{1,6})\s+"
    r"(?P<street_name>(?:[A-Z0-9][A-Z0-9'.-]*\s+){1,6})"
    rf"(?P<suffix>{STREET_SUFFIX_RE})"
    r"(?:\.|\b)"
    r"(?:\s+(?:apt|apartment|suite|ste|unit|#)\s*[A-Z0-9-]+)?",
    re.IGNORECASE,
)

AMBIGUOUS_ADDRESS_RE = re.compile(
    r"(?<!\w)"
    r"(?P<number>\d{2,6})\s+"
    r"(?P<street_name>(?:[A-Z0-9][A-Z0-9'.-]*\s+){1,2})"
    r"(?P<suffix>way|place|pl)"
    r"(?:\.|\b)"
    r"(?:\s+(?:apt|apartment|suite|ste|unit|#)\s*[A-Z0-9-]+)?",
    re.IGNORECASE,
)

CONVERSATIONAL_ADDRESS_WORDS = {
    "a",
    "an",
    "and",
    "another",
    "are",
    "back",
    "be",
    "been",
    "brings",
    "brought",
    "complete",
    "content",
    "days",
    "did",
    "do",
    "does",
    "down",
    "full",
    "get",
    "gets",
    "give",
    "gives",
    "going",
    "got",
    "had",
    "has",
    "have",
    "hours",
    "hrs",
    "if",
    "in",
    "is",
    "left",
    "me",
    "miles",
    "mins",
    "minutes",
    "my",
    "on",
    "only",
    "seconds",
    "that",
    "the",
    "things",
    "this",
    "to",
    "today",
    "version",
    "was",
    "we",
    "were",
    "which",
    "you",
    "your",
}


class DoxxingDetector(commands.Cog):
    """Delete messages containing likely private info and timeout the sender."""

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def is_likely_address_match(match: re.Match[str]) -> bool:
        street_name = match.group("street_name")
        street_words = [
            word.strip(" .'-").lower()
            for word in street_name.split()
            if word.strip(" .'-")
        ]
        if any(word in CONVERSATIONAL_ADDRESS_WORDS for word in street_words):
            return False
        return True

    @staticmethod
    def has_address(content: str) -> bool:
        address_matches = ADDRESS_RE.finditer(content)
        ambiguous_matches = AMBIGUOUS_ADDRESS_RE.finditer(content)
        return any(
            DoxxingDetector.is_likely_address_match(match)
            for match in [*address_matches, *ambiguous_matches]
        )

    @staticmethod
    def find_doxxing_types(content: str) -> list[str]:
        matches = []
        searchable_content = DISCORD_TIMESTAMP_RE.sub(" ", content)
        searchable_content = GAME_SCORE_RE.sub(" ", searchable_content)

        if EMAIL_RE.search(searchable_content):
            matches.append("email")
        if PHONE_RE.search(searchable_content):
            matches.append("phone number")
        if DoxxingDetector.has_address(searchable_content):
            matches.append("address")

        return matches

    @staticmethod
    def can_timeout(target: discord.Member, me: discord.Member) -> bool:
        if target == me:
            return False
        if target.guild_permissions.administrator:
            return False
        if DoxxingDetector.has_timeout_exempt_role(target):
            return False
        return me.guild_permissions.moderate_members and me.top_role > target.top_role

    @staticmethod
    def spoiler_text(content: str) -> str:
        if not content:
            return "[no text content]"
        escaped = content.replace("|", "\\|")
        return f"||{escaped[:1020]}||"

    @staticmethod
    def has_timeout_exempt_role(member: discord.Member) -> bool:
        return any(role.id in EXEMPT_ROLE_IDS for role in member.roles)

    @staticmethod
    async def notify_author(message: discord.Message) -> str | None:
        try:
            await message.author.send(AUTO_FLAG_DM)
        except discord.Forbidden:
            return "Could not DM the user."
        except discord.HTTPException as exc:
            return f"Failed to DM the user: {exc}"
        return None

    async def log_detection(
        self,
        message: discord.Message,
        match_types: list[str],
        deleted: bool,
        timed_out: bool,
        dm_sent: bool,
        error: str | None = None,
    ):
        guild = message.guild
        if guild is None:
            return

        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel is None:
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if log_channel is None:
            return

        embed = discord.Embed(
            title="Doxxing content removed",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="User", value=f"{message.author.mention} (`{message.author.id}`)", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Detected", value=", ".join(match_types), inline=True)
        embed.add_field(name="Deleted", value="Yes" if deleted else "No", inline=True)
        embed.add_field(name="Timed out", value="Yes" if timed_out else "No", inline=True)
        embed.add_field(name="DM sent", value="Yes" if dm_sent else "No", inline=True)
        embed.add_field(
            name="Message",
            value=self.spoiler_text(message.content),
            inline=False,
        )
        if error:
            embed.add_field(name="Error", value=error[:1024], inline=False)

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if not isinstance(message.author, discord.Member):
            return

        match_types = self.find_doxxing_types(message.content)
        if not match_types:
            return

        deleted = False
        timed_out = False
        dm_sent = False
        errors = []

        dm_error = await self.notify_author(message)
        if dm_error:
            errors.append(dm_error)
        else:
            dm_sent = True

        try:
            await message.delete()
            deleted = True
        except discord.Forbidden:
            errors.append("Missing permission to delete the message.")
        except discord.HTTPException as exc:
            errors.append(f"Failed to delete message: {exc}")

        me = message.guild.me or message.guild.get_member(self.bot.user.id)
        if me and self.can_timeout(message.author, me):
            until = discord.utils.utcnow() + TIMEOUT_DURATION
            try:
                await message.author.timeout(
                    until,
                    reason="Posted likely private personal information.",
                )
                timed_out = True
            except discord.Forbidden:
                errors.append("Missing permission or role hierarchy to timeout the user.")
            except discord.HTTPException as exc:
                errors.append(f"Failed to timeout user: {exc}")
        else:
            errors.append("Cannot timeout this user due to permissions or role hierarchy.")

        await self.log_detection(
            message,
            match_types,
            deleted,
            timed_out,
            dm_sent,
            "; ".join(errors) if errors else None,
        )


async def setup(bot):
    await bot.add_cog(DoxxingDetector(bot))
