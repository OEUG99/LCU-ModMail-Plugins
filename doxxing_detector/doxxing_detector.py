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
HTTP_URL_RE = re.compile(r"\bhttps?://[^\s<>()]+", re.IGNORECASE)

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
        self._warned_missing_message_content_intent = False
        self._warned_empty_forward_snapshot_content = False

    def get_log_channel(self, guild: discord.Guild | None = None):
        log_channel = guild.get_channel(LOG_CHANNEL_ID) if guild is not None else None
        if log_channel is None:
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        return log_channel

    async def send_log_embed(self, embed: discord.Embed, guild: discord.Guild | None = None):
        log_channel = self.get_log_channel(guild)
        if log_channel is None or not hasattr(log_channel, "send"):
            return

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass

    async def warn_missing_message_content_intent(self, guild: discord.Guild | None = None):
        if self._warned_missing_message_content_intent:
            return
        self._warned_missing_message_content_intent = True
        embed = discord.Embed(
            title="Doxxing detector warning",
            description=(
                "`message_content` intent is disabled. Discord will hide normal "
                "message text and forwarded snapshot content."
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        await self.send_log_embed(embed, guild)

    def has_message_content_intent(self) -> bool:
        return getattr(getattr(self.bot, "intents", None), "message_content", True)

    async def log_forward_debug(self, message: discord.Message, searchable_content: str):
        reference = getattr(message, "reference", None)
        snapshots = getattr(message, "message_snapshots", [])
        if reference is None and not snapshots:
            return

        snapshot_lengths = [
            len(getattr(snapshot, "content", "") or "")
            for snapshot in snapshots
        ]
        snapshot_embed_counts = [
            len(getattr(snapshot, "embeds", []) or [])
            for snapshot in snapshots
        ]
        embed = discord.Embed(
            title="Doxxing forward debug",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Message ID", value=str(getattr(message, "id", None)), inline=True)
        embed.add_field(name="Author ID", value=str(getattr(getattr(message, "author", None), "id", None)), inline=True)
        embed.add_field(name="Reference type", value=str(getattr(reference, "type", None)), inline=False)
        embed.add_field(name="Snapshots", value=str(len(snapshots)), inline=True)
        embed.add_field(name="Snapshot content lengths", value=str(snapshot_lengths), inline=True)
        embed.add_field(name="Snapshot embed counts", value=str(snapshot_embed_counts), inline=True)
        embed.add_field(name="Searchable length", value=str(len(searchable_content)), inline=True)
        if searchable_content:
            embed.add_field(name="Searchable content", value=self.spoiler_text(searchable_content), inline=False)

        await self.send_log_embed(embed, getattr(message, "guild", None))

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.has_message_content_intent():
            await self.warn_missing_message_content_intent()

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
    def strip_http_urls(content: str) -> str:
        def strip_url(match: re.Match[str]) -> str:
            url = match.group(0)
            trailing = ""
            while url and url[-1] in ".,!?;:":
                trailing = url[-1] + trailing
                url = url[:-1]

            return " " + trailing

        return HTTP_URL_RE.sub(strip_url, content)

    @staticmethod
    def find_doxxing_types(content: str) -> list[str]:
        matches = []
        searchable_content = DISCORD_TIMESTAMP_RE.sub(" ", content)
        searchable_content = GAME_SCORE_RE.sub(" ", searchable_content)
        searchable_content = DoxxingDetector.strip_http_urls(searchable_content)

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
    def embed_text(embed: discord.Embed) -> str:
        parts = [
            getattr(embed, "title", None),
            getattr(embed, "description", None),
        ]
        parts.extend(
            value
            for value in (
                getattr(field, "value", None)
                for field in getattr(embed, "fields", [])
            )
            if value
        )
        author = getattr(embed, "author", None)
        footer = getattr(embed, "footer", None)
        parts.extend(
            value
            for value in [
                getattr(author, "name", None),
                getattr(footer, "text", None),
            ]
            if value
        )
        return "\n".join(part for part in parts if part)

    @staticmethod
    def is_forward_reference(reference) -> bool:
        reference_type = getattr(reference, "type", None)
        return (
            reference_type is discord.MessageReferenceType.forward
            or reference_type == discord.MessageReferenceType.forward
            or reference_type == discord.MessageReferenceType.forward.value
        )

    @classmethod
    def message_search_content(cls, message: discord.Message, seen: set[int] | None = None) -> str:
        if seen is None:
            seen = set()

        message_id = id(message)
        if message_id in seen:
            return ""
        seen.add(message_id)

        parts = [getattr(message, "content", "")]

        for embed in getattr(message, "embeds", []):
            parts.append(cls.embed_text(embed))

        for snapshot in getattr(message, "message_snapshots", []):
            parts.append(getattr(snapshot, "content", ""))
            for embed in getattr(snapshot, "embeds", []):
                parts.append(cls.embed_text(embed))

        reference = getattr(message, "reference", None)
        if reference is not None and cls.is_forward_reference(reference):
            resolved = getattr(reference, "resolved", None)
            if isinstance(resolved, discord.Message):
                parts.append(cls.message_search_content(resolved, seen))

            cached_message = getattr(reference, "cached_message", None)
            if isinstance(cached_message, discord.Message):
                parts.append(cls.message_search_content(cached_message, seen))

        return "\n".join(part for part in parts if part)

    async def fetch_forwarded_message_content(self, message: discord.Message) -> str:
        reference = getattr(message, "reference", None)
        if reference is None or not self.is_forward_reference(reference):
            return ""
        if not reference.channel_id or not reference.message_id:
            return ""

        channel = self.bot.get_channel(reference.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(reference.channel_id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                return ""

        fetch_message = getattr(channel, "fetch_message", None)
        if fetch_message is None:
            return ""

        try:
            forwarded_message = await fetch_message(reference.message_id)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            return ""

        return self.message_search_content(forwarded_message)

    async def message_search_content_with_forward_fetch(self, message: discord.Message) -> str:
        if not self.has_message_content_intent():
            await self.warn_missing_message_content_intent(getattr(message, "guild", None))

        content = self.message_search_content(message)
        snapshots = getattr(message, "message_snapshots", [])
        if (
            snapshots
            and not any(getattr(snapshot, "content", "") for snapshot in snapshots)
            and not self._warned_empty_forward_snapshot_content
        ):
            self._warned_empty_forward_snapshot_content = True
            embed = discord.Embed(
                title="Doxxing detector warning",
                description=(
                    "Received forwarded message snapshots, but Discord sent empty "
                    "snapshot content. Confirm the Message Content privileged intent "
                    "is enabled in code and in the Discord Developer Portal."
                ),
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow(),
            )
            await self.send_log_embed(embed, getattr(message, "guild", None))

        fetched_content = await self.fetch_forwarded_message_content(message)
        searchable_content = "\n".join(part for part in [content, fetched_content] if part)
        await self.log_forward_debug(message, searchable_content)
        return searchable_content

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

        log_channel = self.get_log_channel(guild)
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
            value=self.spoiler_text(await self.message_search_content_with_forward_fetch(message)),
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

        searchable_content = await self.message_search_content_with_forward_fetch(message)
        match_types = self.find_doxxing_types(searchable_content)
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
