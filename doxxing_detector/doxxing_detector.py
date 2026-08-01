from __future__ import annotations

import asyncio
import concurrent.futures
import datetime
import importlib.metadata as importlib_metadata
import os
import re
import shutil
import sys
import tempfile
import discord
from discord.ext import commands


TIMEOUT_DURATION = datetime.timedelta(hours=3)
LOG_CHANNEL_ID = 1497340655423324309
FORWARD_SOURCE_GUILD_ID = 1229546498677801070
EXEMPT_FORWARD_SOURCE_CHANNEL_IDS = {
    1450884163426189372,
}
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
ALWAYS_DELETE_FORWARD_ROLE_IDS = {
    1481877137118990420,
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
VIDEO_TIMESTAMP_RE = re.compile(r"(?<!\w)\d{1,2}:\d{2}(?::\d{2})?(?!\w)")
GAME_SCORE_RE = re.compile(r"\b\d+\s*v(?:s\.?|ersus)?\s*\d+\b", re.IGNORECASE)
RATING_RE = re.compile(r"(?<!\w)\d{1,2}/10(?!\w)")
HTTP_URL_RE = re.compile(r"\bhttps?://[^\s<>()]+", re.IGNORECASE)
FILE_TOKEN_RE = re.compile(
    r"(?<!\S)"
    r"\S+\."
    r"(?:avif|bmp|gif|heic|heif|jpeg|jpg|mov|mp4|png|webm|webp)"
    r"(?!\S)",
    re.IGNORECASE,
)
IMAGE_ATTACHMENT_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
IMAGE_ATTACHMENT_CONTENT_TYPES = {
    "image/avif",
    "image/bmp",
    "image/gif",
    "image/heic",
    "image/heif",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
}
MAX_OCR_ATTACHMENT_BYTES = 8 * 1024 * 1024
OCR_TIMEOUT_SECONDS = 45

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
    "hour",
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

HOUSING_DESCRIPTION_WORDS = {
    "bath",
    "bathroom",
    "bed",
    "bedroom",
    "br",
    "room",
    "studio",
}


class TesseractOcrEngine:
    def __init__(self, pytesseract_module):
        self.pytesseract = pytesseract_module
        tesseract_cmd = shutil.which("tesseract") or "/app/.apt/usr/bin/tesseract"
        if tesseract_cmd:
            self.pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def image_to_text(self, image_path: str) -> str:
        return self.pytesseract.image_to_string(image_path, config="--psm 6") or ""


class DoxxingDetector(commands.Cog):
    """Delete messages containing likely private info and timeout the sender."""

    def __init__(self, bot):
        self.bot = bot
        self._warned_missing_message_content_intent = False
        self._warned_empty_forward_snapshot_content = False
        self._warned_missing_ocr_dependencies = False
        self._warned_ocr_failure = False
        self._reference_fetch_cache = {}
        self._message_refetch_cache = {}
        self._attachment_ocr_cache = {}
        self._ocr_engine = None
        self._ocr_engine_lock = asyncio.Lock()
        self._ocr_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="doxxing-ocr",
        )
        self._ocr_dependency_error = None

    def get_log_channel(self, guild: discord.Guild | None = None):
        log_channel = guild.get_channel(LOG_CHANNEL_ID) if guild is not None else None
        if log_channel is None:
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        return log_channel

    def cog_unload(self):
        self._ocr_executor.shutdown(wait=False, cancel_futures=True)

    async def send_log_embed(self, embed: discord.Embed, guild: discord.Guild | None = None):
        log_channel = self.get_log_channel(guild)
        if log_channel is None or not hasattr(log_channel, "send"):
            return

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass

    @staticmethod
    def compact_text(content: str | None, limit: int = 260) -> str:
        if not content:
            return ""
        compacted = " ".join(str(content).split())
        if len(compacted) <= limit:
            return compacted
        return f"{compacted[:limit - 3]}..."

    @staticmethod
    async def send_text_chunks(ctx: commands.Context, content: str):
        chunk_limit = 1900
        chunks = [content[index:index + chunk_limit] for index in range(0, len(content), chunk_limit)]
        for chunk in chunks:
            await ctx.send(f"```text\n{chunk.replace('```', '` ` `')}\n```")

    def forward_debug_report_for_message(self, message: discord.Message, index: int) -> str:
        snapshots = self.forward_snapshots(message)
        raw_snapshots = self.sequence_field(message, "message_snapshots")
        reference = self.field_value(message, "reference")
        lines = [
            f"#{index} message_id={message.id}",
            f"author={message.author} author_id={getattr(message.author, 'id', None)} bot={getattr(message.author, 'bot', None)}",
            f"channel_id={getattr(message.channel, 'id', None)} type={getattr(message, 'type', None)}",
            f"content_len={len(message.content or '')} content={self.compact_text(message.content)!r}",
            f"embeds={len(message.embeds or [])} attachments={len(message.attachments or [])}",
            f"reference_type={self.field_value(reference, 'type')} reference_channel_id={self.field_value(reference, 'channel_id')} reference_message_id={self.field_value(reference, 'message_id')}",
            f"message_snapshots_attr_present={hasattr(message, 'message_snapshots')}",
            f"raw_snapshot_count={len(raw_snapshots)} normalized_snapshot_count={len(snapshots)}",
        ]

        if not snapshots:
            lines.append("snapshots=NONE")
            return "\n".join(lines)

        for snapshot_index, snapshot in enumerate(snapshots, start=1):
            snapshot_content = self.field_value(snapshot, "content", "")
            snapshot_embeds = self.sequence_field(snapshot, "embeds")
            snapshot_attachments = self.sequence_field(snapshot, "attachments")
            lines.extend(
                [
                    f"snapshot_{snapshot_index}_type={self.field_value(snapshot, 'type')}",
                    f"snapshot_{snapshot_index}_content_len={len(snapshot_content or '')}",
                    f"snapshot_{snapshot_index}_content={self.compact_text(snapshot_content)!r}",
                    f"snapshot_{snapshot_index}_embeds={len(snapshot_embeds)} attachments={len(snapshot_attachments)}",
                ]
            )
            for embed_index, embed in enumerate(snapshot_embeds, start=1):
                lines.append(
                    f"snapshot_{snapshot_index}_embed_{embed_index}_text={self.compact_text(self.embed_text(embed))!r}"
                )
            for attachment_index, attachment in enumerate(snapshot_attachments, start=1):
                lines.append(
                    f"snapshot_{snapshot_index}_attachment_{attachment_index}_text={self.compact_text(self.attachment_text(attachment))!r}"
                )

        return "\n".join(lines)

    @commands.command(name="scanforwardlogs")
    @commands.has_permissions(manage_messages=True)
    async def scan_forward_logs(self, ctx: commands.Context, limit: int = 5):
        """Dump forward snapshot fields from recent messages in the configured log channel."""
        limit = max(1, min(limit, 10))
        log_channel = self.get_log_channel(ctx.guild)
        if log_channel is None or not hasattr(log_channel, "history"):
            await ctx.send(f"Log channel `{LOG_CHANNEL_ID}` was not found or cannot be read.")
            return

        try:
            messages = [message async for message in log_channel.history(limit=limit)]
        except discord.Forbidden:
            await ctx.send(f"I do not have permission to read message history in `{LOG_CHANNEL_ID}`.")
            return
        except discord.HTTPException as exc:
            await ctx.send(f"Failed to read log channel history: `{exc}`")
            return

        if not messages:
            await ctx.send(f"No recent messages found in `{LOG_CHANNEL_ID}`.")
            return

        report = "\n\n".join(
            self.forward_debug_report_for_message(message, index)
            for index, message in enumerate(messages, start=1)
        )
        await self.send_text_chunks(ctx, report)

    @commands.command(name="ocr", aliases=["imageocr"])
    @commands.has_permissions(manage_messages=True)
    async def ocr_image(self, ctx: commands.Context):
        """Run OCR on an attached image and return the extracted text."""
        attachments = self.sequence_field(ctx.message, "attachments")
        image_attachment = next(
            (attachment for attachment in attachments if self.is_image_attachment(attachment)),
            None,
        )
        if image_attachment is None:
            await ctx.send("Attach an image to this command to run OCR.")
            return

        text = await self.ocr_attachment_text(image_attachment, ctx.guild)
        if not text:
            await ctx.send("No OCR text was found, or OCR failed. Check the doxxing detector warning log.")
            return

        await self.send_text_chunks(ctx, text)

    @commands.command(name="ocrstatus")
    @commands.has_permissions(manage_messages=True)
    async def ocr_status(self, ctx: commands.Context):
        """Report OCR dependency status for the running bot process."""
        await self.send_text_chunks(ctx, self.ocr_dependency_report())

    @commands.command(name="killbot", aliases=["shutdownbot"])
    @commands.has_permissions(administrator=True)
    async def kill_bot(self, ctx: commands.Context):
        """Shut down the bot. Server administrators only."""
        await ctx.send("Shutting down.")
        await self.bot.close()

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

    async def warn_missing_ocr_dependencies(
        self,
        error: Exception | None = None,
        guild: discord.Guild | None = None,
    ):
        if self._warned_missing_ocr_dependencies:
            return
        self._warned_missing_ocr_dependencies = True
        if error is not None:
            self._ocr_dependency_error = error
        error_text = ""
        if error is not None:
            error_text = f"\nError: `{type(error).__name__}: {str(error)[:700]}`"
        embed = discord.Embed(
            title="Doxxing detector warning",
            description=(
                "Image OCR is enabled in the scan path, but pytesseract could not be imported. "
                "Image attachment text will not be scanned."
                f"{error_text}\nRun `ocrstatus` for package details."
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        await self.send_log_embed(embed, guild)

    async def warn_ocr_failure(
        self,
        attachment: discord.Attachment | dict,
        error: Exception,
        guild: discord.Guild | None = None,
    ):
        if self._warned_ocr_failure:
            return
        self._warned_ocr_failure = True
        filename = self.field_value(attachment, "filename", "[unknown]")
        content_type = self.field_value(attachment, "content_type", "[unknown]")
        size = self.field_value(attachment, "size", "[unknown]")
        embed = discord.Embed(
            title="Doxxing detector warning",
            description=(
                "Image OCR failed for an attachment. Text message scanning is still running.\n"
                f"Attachment: `{filename}`\n"
                f"Content type: `{content_type}`\n"
                f"Size: `{size}`\n"
                f"Error: `{type(error).__name__}: {str(error)[:700]}`"
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        await self.send_log_embed(embed, guild)

    def has_message_content_intent(self) -> bool:
        return getattr(getattr(self.bot, "intents", None), "message_content", True)

    @classmethod
    def is_forward_message(cls, message: discord.Message) -> bool:
        return bool(cls.forward_snapshots(message))

    @classmethod
    def has_visible_message_content(cls, message: discord.Message) -> bool:
        return bool(
            cls.field_value(message, "content", "")
            or cls.sequence_field(message, "embeds")
            or cls.sequence_field(message, "attachments")
        )

    @classmethod
    def needs_reference_fetch_for_scan(cls, message: discord.Message) -> bool:
        reference = cls.field_value(message, "reference")
        if reference is None or not cls.field_value(reference, "message_id"):
            return False
        if not cls.field_value(reference, "channel_id"):
            return False
        if cls.is_forward_reference(reference):
            return True
        return not cls.has_visible_message_content(message) and not cls.forward_snapshots(message)

    @classmethod
    def has_message_id_without_reference_channel(cls, message: discord.Message) -> bool:
        reference = cls.field_value(message, "reference")
        return bool(
            reference is not None
            and cls.field_value(reference, "message_id")
            and not cls.field_value(reference, "channel_id")
        )

    @classmethod
    def may_need_current_message_refetch(cls, message: discord.Message) -> bool:
        return bool(
            cls.field_value(message, "id")
            and cls.field_value(message, "reference") is not None
            and not cls.forward_snapshots(message)
        )

    @classmethod
    def is_reference_like_message(cls, message: discord.Message) -> bool:
        return (
            cls.may_need_current_message_refetch(message)
            or cls.has_message_id_without_reference_channel(message)
            or cls.needs_reference_fetch_for_scan(message)
        )

    @classmethod
    def forward_reference_channel_id(cls, message: discord.Message) -> int | None:
        reference = cls.field_value(message, "reference")
        if reference is None or not cls.field_value(reference, "message_id"):
            return None

        channel_id = cls.field_value(reference, "channel_id")
        try:
            return int(channel_id)
        except (TypeError, ValueError):
            return None

    @classmethod
    def has_forward_like_reference(cls, message: discord.Message) -> bool:
        reference = cls.field_value(message, "reference")
        return bool(reference is not None and cls.field_value(reference, "message_id"))

    @classmethod
    def guild_has_channel_id(cls, guild, channel_id: int) -> bool:
        for method_name in ["get_channel_or_thread", "get_channel", "get_thread"]:
            method = getattr(guild, method_name, None)
            if method is not None and method(channel_id) is not None:
                return True

        channels = []
        channels.extend(cls.sequence_field(guild, "text_channels"))
        channels.extend(cls.sequence_field(guild, "threads"))
        channels.extend(cls.sequence_field(guild, "channels"))
        return any(cls.field_value(channel, "id") == channel_id for channel in channels)

    def get_forward_source_guild(self, message: discord.Message):
        guild = self.field_value(message, "guild")
        if self.field_value(guild, "id") == FORWARD_SOURCE_GUILD_ID:
            return guild

        get_guild = getattr(self.bot, "get_guild", None)
        return get_guild(FORWARD_SOURCE_GUILD_ID) if get_guild is not None else None

    async def should_delete_forward_from_outside_server(self, message: discord.Message) -> bool:
        if not self.has_forward_like_reference(message):
            return False
        author = self.field_value(message, "author")
        return self.has_always_delete_forward_role(author)

    async def log_forward_debug(self, message: discord.Message, searchable_content: str):
        reference = self.field_value(message, "reference")
        snapshots = self.forward_snapshots(message)
        if not self.is_forward_message(message):
            return

        snapshot_lengths = [len(self.field_value(snapshot, "content", "") or "") for snapshot in snapshots]
        snapshot_embed_counts = [len(self.sequence_field(snapshot, "embeds")) for snapshot in snapshots]
        embed = discord.Embed(
            title="Doxxing forward debug",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Message ID", value=str(getattr(message, "id", None)), inline=True)
        embed.add_field(name="Author ID", value=str(getattr(getattr(message, "author", None), "id", None)), inline=True)
        embed.add_field(name="Reference type", value=str(self.field_value(reference, "type")), inline=False)
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
        suffix = match.group("suffix").lower()
        street_words = [
            word.strip(" .'-").lower()
            for word in street_name.split()
            if word.strip(" .'-")
        ]
        if any(word in CONVERSATIONAL_ADDRESS_WORDS for word in street_words):
            return False
        if suffix in {"apartment", "apt", "unit"} and all(
            word in HOUSING_DESCRIPTION_WORDS for word in street_words
        ):
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
    def strip_file_tokens(content: str) -> str:
        return FILE_TOKEN_RE.sub(" ", content)

    @staticmethod
    def find_doxxing_types(content: str) -> list[str]:
        matches = []
        searchable_content = DISCORD_TIMESTAMP_RE.sub(" ", content)
        searchable_content = VIDEO_TIMESTAMP_RE.sub(" ", searchable_content)
        searchable_content = GAME_SCORE_RE.sub(" ", searchable_content)
        searchable_content = RATING_RE.sub(" ", searchable_content)
        searchable_content = DoxxingDetector.strip_http_urls(searchable_content)
        phone_searchable_content = DoxxingDetector.strip_file_tokens(searchable_content)

        if EMAIL_RE.search(searchable_content):
            matches.append("email")
        if PHONE_RE.search(phone_searchable_content):
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
    def field_value(item, name: str, default=None):
        if isinstance(item, dict):
            return item.get(name, default)
        return getattr(item, name, default)

    @classmethod
    def sequence_field(cls, item, name: str) -> list:
        value = cls.field_value(item, name, [])
        return value or []

    @classmethod
    def forward_snapshots(cls, message: discord.Message) -> list:
        return [
            cls.snapshot_payload(snapshot)
            for snapshot in cls.sequence_field(message, "message_snapshots")
        ]

    @classmethod
    def snapshot_payload(cls, snapshot):
        payload = cls.field_value(snapshot, "message")
        return payload if payload is not None else snapshot

    @staticmethod
    def spoiler_text(content: str) -> str:
        if not content:
            return "[no text content]"
        escaped = content.replace("|", "\\|")
        return f"||{escaped[:1020]}||"

    @classmethod
    def embed_text(cls, embed: discord.Embed | dict) -> str:
        if isinstance(embed, dict):
            fields = embed.get("fields", []) or []
            author = embed.get("author", {}) or {}
            footer = embed.get("footer", {}) or {}
            parts = [
                embed.get("title"),
                embed.get("description"),
                *(field.get("value") for field in fields if isinstance(field, dict)),
                author.get("name") if isinstance(author, dict) else None,
                footer.get("text") if isinstance(footer, dict) else None,
            ]
            return "\n".join(part for part in parts if part)

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

    async def fetch_current_message_content(self, message: discord.Message) -> tuple[str, str | None]:
        message_id = self.field_value(message, "id")
        channel = self.field_value(message, "channel")
        channel_id = self.field_value(channel, "id")
        if not message_id or channel is None:
            return "", "Message is missing id or channel."

        cache_key = (channel_id, message_id)
        if cache_key in self._message_refetch_cache:
            return self._message_refetch_cache[cache_key]

        fetch_message = getattr(channel, "fetch_message", None)
        if fetch_message is None:
            return "", f"Current channel `{channel_id}` does not support message fetch."

        try:
            fetched_message = await fetch_message(message_id)
        except discord.Forbidden:
            return "", f"Missing permission to refetch message `{message_id}` in channel `{channel_id}`."
        except discord.NotFound:
            return "", f"Message `{message_id}` was not found when refetching current channel `{channel_id}`."
        except discord.HTTPException as exc:
            return "", f"Failed to refetch message `{message_id}` in channel `{channel_id}`: {exc}"

        result = (await self.async_message_search_content(fetched_message), None)
        self._message_refetch_cache[cache_key] = result
        return result

    @classmethod
    def attachment_text(cls, attachment: discord.Attachment | dict) -> str:
        parts = [
            cls.field_value(attachment, "filename", ""),
            cls.field_value(attachment, "description", ""),
            cls.field_value(attachment, "title", ""),
            cls.field_value(attachment, "url", ""),
            cls.field_value(attachment, "proxy_url", ""),
        ]
        return "\n".join(part for part in parts if part)

    @classmethod
    def is_image_attachment(cls, attachment: discord.Attachment | dict) -> bool:
        content_type = (cls.field_value(attachment, "content_type", "") or "").split(";", 1)[0].lower()
        if content_type in IMAGE_ATTACHMENT_CONTENT_TYPES:
            return True

        filename = (cls.field_value(attachment, "filename", "") or "").lower()
        return any(filename.endswith(extension) for extension in IMAGE_ATTACHMENT_EXTENSIONS)

    @classmethod
    def attachment_ocr_cache_key(cls, attachment: discord.Attachment | dict):
        attachment_id = cls.field_value(attachment, "id")
        if attachment_id:
            return ("id", attachment_id)
        url = cls.field_value(attachment, "url") or cls.field_value(attachment, "proxy_url")
        if url:
            return ("url", url)
        return None

    async def ocr_attachment_text(
        self,
        attachment: discord.Attachment | dict,
        guild: discord.Guild | None = None,
    ) -> str:
        if not self.is_image_attachment(attachment):
            return ""

        size = self.field_value(attachment, "size")
        if size and size > MAX_OCR_ATTACHMENT_BYTES:
            return ""

        read_attachment = getattr(attachment, "read", None)
        if read_attachment is None:
            return ""

        cache_key = self.attachment_ocr_cache_key(attachment)
        if cache_key is not None and cache_key in self._attachment_ocr_cache:
            return self._attachment_ocr_cache[cache_key]

        try:
            image_bytes = await read_attachment()
            if not image_bytes:
                return ""
            text = await self.ocr_image_bytes(image_bytes)
        except ImportError as exc:
            await self.warn_missing_ocr_dependencies(exc, guild)
            return ""
        except asyncio.TimeoutError:
            await self.warn_ocr_failure(
                attachment,
                TimeoutError(f"OCR exceeded {OCR_TIMEOUT_SECONDS} seconds."),
                guild,
            )
            return ""
        except Exception as exc:
            await self.warn_ocr_failure(attachment, exc, guild)
            return ""

        text = " ".join(text.split())
        if cache_key is not None:
            self._attachment_ocr_cache[cache_key] = text
        return text

    def get_ocr_engine(self):
        if self._ocr_engine is None:
            self._ocr_engine = self.load_ocr_engine()
        return self._ocr_engine

    async def ocr_image_bytes(self, image_bytes: bytes) -> str:
        loop = asyncio.get_running_loop()
        if self._ocr_engine is None:
            async with self._ocr_engine_lock:
                if self._ocr_engine is None:
                    self._ocr_engine = await asyncio.wait_for(
                        loop.run_in_executor(self._ocr_executor, self.load_ocr_engine),
                        timeout=OCR_TIMEOUT_SECONDS,
                    )
        return await asyncio.wait_for(
            loop.run_in_executor(self._ocr_executor, self.image_bytes_to_text, image_bytes),
            timeout=OCR_TIMEOUT_SECONDS,
        )

    @staticmethod
    def load_ocr_engine():
        try:
            import pytesseract
        except ImportError as exc:
            raise ImportError(f"pytesseract: {exc}") from exc
        return TesseractOcrEngine(pytesseract)

    @staticmethod
    def package_version(package_name: str) -> str:
        try:
            return importlib_metadata.version(package_name)
        except importlib_metadata.PackageNotFoundError:
            return "not installed"

    def ocr_dependency_report(self) -> str:
        lines = [
            f"Python: {sys.version.split()[0]}",
            f"Executable: {sys.executable}",
            f"pytesseract: {self.package_version('pytesseract')}",
            f"Pillow: {self.package_version('Pillow')}",
            f"tesseract: {shutil.which('tesseract') or '[not on PATH]'}",
            f"heroku tesseract: {'present' if os.path.exists('/app/.apt/usr/bin/tesseract') else 'missing'}",
        ]

        try:
            import pytesseract
        except ImportError as exc:
            lines.append(f"pytesseract import: FAILED - {type(exc).__name__}: {exc}")
        else:
            lines.append(f"pytesseract import: OK - {getattr(pytesseract, '__file__', '[unknown path]')}")

        try:
            backend_name = self.ocr_backend_import_status()
        except ImportError as exc:
            lines.append(f"OCR import: FAILED - {exc}")
        else:
            lines.append(f"OCR import: OK - {backend_name}")

        if self._ocr_dependency_error is not None:
            error = self._ocr_dependency_error
            lines.append(f"Last OCR import error: {type(error).__name__}: {error}")

        return "\n".join(lines)

    @staticmethod
    def ocr_backend_import_status() -> str:
        try:
            import pytesseract
        except ImportError as exc:
            raise ImportError(f"pytesseract: {exc}") from exc
        return f"pytesseract {getattr(pytesseract, '__version__', '[unknown version]')}"

    def image_bytes_to_text(self, image_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".png") as image_file:
            image_file.write(image_bytes)
            image_file.flush()
            return self.get_ocr_engine().image_to_text(image_file.name)

    async def async_message_search_content(
        self,
        message: discord.Message,
        seen: set[int] | None = None,
    ) -> str:
        if seen is None:
            seen = set()

        message_id = id(message)
        if message_id in seen:
            return ""
        seen.add(message_id)

        parts = [self.field_value(message, "content", "")]
        guild = self.field_value(message, "guild")

        for embed in self.sequence_field(message, "embeds"):
            parts.append(self.embed_text(embed))

        for attachment in self.sequence_field(message, "attachments"):
            parts.append(self.attachment_text(attachment))
            if self.is_image_attachment(attachment):
                parts.append(await self.ocr_attachment_text(attachment, guild))

        for snapshot in self.forward_snapshots(message):
            parts.append(self.field_value(snapshot, "content", ""))
            for embed in self.sequence_field(snapshot, "embeds"):
                parts.append(self.embed_text(embed))
            for attachment in self.sequence_field(snapshot, "attachments"):
                parts.append(self.attachment_text(attachment))
                if self.is_image_attachment(attachment):
                    parts.append(await self.ocr_attachment_text(attachment, guild))

        reference = self.field_value(message, "reference")
        if reference is not None and self.is_forward_reference(reference):
            resolved = self.field_value(reference, "resolved")
            if isinstance(resolved, discord.Message):
                parts.append(await self.async_message_search_content(resolved, seen))

            cached_message = self.field_value(reference, "cached_message")
            if isinstance(cached_message, discord.Message):
                parts.append(await self.async_message_search_content(cached_message, seen))

        return "\n".join(part for part in parts if part)

    @staticmethod
    def is_forward_reference(reference) -> bool:
        reference_type = DoxxingDetector.field_value(reference, "type")
        forward_reference_type = getattr(getattr(discord, "MessageReferenceType", None), "forward", None)
        if forward_reference_type is not None and (
            reference_type is forward_reference_type
            or reference_type == forward_reference_type
            or reference_type == getattr(forward_reference_type, "value", None)
        ):
            return True

        reference_type_name = getattr(reference_type, "name", None)
        if reference_type_name == "forward" or reference_type == "forward":
            return True

        try:
            return int(reference_type) == 1
        except (TypeError, ValueError):
            return False

    @classmethod
    def message_search_content(cls, message: discord.Message, seen: set[int] | None = None) -> str:
        if seen is None:
            seen = set()

        message_id = id(message)
        if message_id in seen:
            return ""
        seen.add(message_id)

        parts = [cls.field_value(message, "content", "")]

        for embed in cls.sequence_field(message, "embeds"):
            parts.append(cls.embed_text(embed))

        for attachment in cls.sequence_field(message, "attachments"):
            parts.append(cls.attachment_text(attachment))

        for snapshot in cls.forward_snapshots(message):
            parts.append(cls.field_value(snapshot, "content", ""))
            for embed in cls.sequence_field(snapshot, "embeds"):
                parts.append(cls.embed_text(embed))
            for attachment in cls.sequence_field(snapshot, "attachments"):
                parts.append(cls.attachment_text(attachment))

        reference = cls.field_value(message, "reference")
        if reference is not None and cls.is_forward_reference(reference):
            resolved = cls.field_value(reference, "resolved")
            if isinstance(resolved, discord.Message):
                parts.append(cls.message_search_content(resolved, seen))

            cached_message = cls.field_value(reference, "cached_message")
            if isinstance(cached_message, discord.Message):
                parts.append(cls.message_search_content(cached_message, seen))

        return "\n".join(part for part in parts if part)

    async def fetch_message_content_from_channel(
        self,
        channel,
        channel_id,
        message_id,
    ) -> tuple[str, str | None]:
        fetch_message = getattr(channel, "fetch_message", None)
        if fetch_message is None:
            return "", f"Referenced channel `{channel_id}` does not support message fetch."

        try:
            referenced_message = await fetch_message(message_id)
        except discord.Forbidden:
            return "", f"Missing permission to fetch referenced message `{message_id}` in channel `{channel_id}`."
        except discord.NotFound:
            return "", f"Referenced message `{message_id}` was not found in channel `{channel_id}`."
        except discord.HTTPException as exc:
            return "", f"Failed to fetch referenced message `{message_id}` in channel `{channel_id}`: {exc}"

        return await self.async_message_search_content(referenced_message), None

    async def fetch_referenced_message_content(self, message: discord.Message) -> tuple[str, str | None]:
        reference = self.field_value(message, "reference")
        if reference is None:
            return "", "Message has no reference."
        channel_id = self.field_value(reference, "channel_id")
        message_id = self.field_value(reference, "message_id")
        if not message_id:
            return "", "Reference is missing message_id."
        cache_key = (id(message), channel_id, message_id)
        if cache_key in self._reference_fetch_cache:
            return self._reference_fetch_cache[cache_key]

        if not channel_id:
            result = await self.fetch_referenced_message_from_guild(message, message_id)
            self._reference_fetch_cache[cache_key] = result
            return result

        exact_error = None
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            fetch_channel = getattr(self.bot, "fetch_channel", None)
            if fetch_channel is None:
                exact_error = f"Could not find referenced channel `{channel_id}`."
            else:
                try:
                    channel = await fetch_channel(channel_id)
                except discord.Forbidden:
                    exact_error = f"Missing permission to fetch referenced channel `{channel_id}`."
                except discord.NotFound:
                    exact_error = f"Referenced channel `{channel_id}` was not found."
                except discord.HTTPException as exc:
                    exact_error = f"Failed to fetch referenced channel `{channel_id}`: {exc}"

        if channel is not None:
            result = await self.fetch_message_content_from_channel(channel, channel_id, message_id)
            if result[1] is None:
                self._reference_fetch_cache[cache_key] = result
                return result
            exact_error = result[1]

        result = await self.fetch_referenced_message_from_guild(
            message,
            message_id,
            skip_channel_ids={channel_id},
            prior_error=exact_error,
        )
        self._reference_fetch_cache[cache_key] = result
        return result

    async def fetch_referenced_message_from_guild(
        self,
        message: discord.Message,
        message_id: int,
        skip_channel_ids: set[int] | None = None,
        prior_error: str | None = None,
    ) -> tuple[str, str | None]:
        guild = self.field_value(message, "guild")
        if guild is None:
            return "", prior_error or "Reference is missing channel_id and the message has no guild."

        checked_channel_ids = set(skip_channel_ids or [])
        channels = []
        channels.extend(self.sequence_field(guild, "text_channels"))
        channels.extend(self.sequence_field(guild, "threads"))
        channels.extend(
            channel
            for channel in self.sequence_field(guild, "channels")
            if hasattr(channel, "fetch_message")
        )

        fetch_errors = []
        for channel in channels:
            channel_id = self.field_value(channel, "id")
            if channel_id in checked_channel_ids:
                continue
            checked_channel_ids.add(channel_id)

            fetch_message = getattr(channel, "fetch_message", None)
            if fetch_message is None:
                continue

            content, error = await self.fetch_message_content_from_channel(channel, channel_id, message_id)
            if error is None:
                return content, None
            if "not found" not in error and "Missing permission" not in error:
                fetch_errors.append(error)
                continue

        if fetch_errors:
            return "", f"Could not load referenced message `{message_id}` from guild channels: {'; '.join(fetch_errors)[:900]}"
        if prior_error:
            return "", f"{prior_error}; referenced message `{message_id}` was not found in any other readable guild channel."
        return "", f"Referenced message `{message_id}` was not found in any readable guild channel."

    async def fetch_forwarded_message_content(self, message: discord.Message) -> str:
        reference = self.field_value(message, "reference")
        if reference is None or not self.is_forward_reference(reference):
            return ""

        content, _error = await self.fetch_referenced_message_content(message)
        return content

    async def message_search_content_with_forward_fetch(self, message: discord.Message) -> str:
        if not self.has_message_content_intent():
            await self.warn_missing_message_content_intent(getattr(message, "guild", None))

        content = await self.async_message_search_content(message)
        refetched_content = ""
        if self.may_need_current_message_refetch(message):
            refetched_content, _error = await self.fetch_current_message_content(message)
        snapshots = self.forward_snapshots(message)
        if (
            snapshots
            and not any(self.field_value(snapshot, "content", "") for snapshot in snapshots)
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

        fetched_content = ""
        if not refetched_content and self.needs_reference_fetch_for_scan(message):
            fetched_content, _error = await self.fetch_referenced_message_content(message)
        searchable_content = "\n".join(part for part in [content, refetched_content, fetched_content] if part)
        await self.log_forward_debug(message, searchable_content)
        return searchable_content

    async def unresolved_reference_error(self, message: discord.Message) -> str | None:
        if self.may_need_current_message_refetch(message):
            refetched_content, _error = await self.fetch_current_message_content(message)
            if refetched_content:
                return None

        if self.has_message_id_without_reference_channel(message):
            reference = self.field_value(message, "reference")
            return (
                f"Message has reference_message_id `{self.field_value(reference, 'message_id')}` "
                "but no reference_channel_id."
            )
        if not self.needs_reference_fetch_for_scan(message):
            return None
        if self.has_visible_message_content(message):
            return None

        fetched_content, error = await self.fetch_referenced_message_content(message)
        if fetched_content or error is None:
            return None
        return error

    async def delete_unscannable_reference_message(self, message: discord.Message, error: str) -> None:
        deleted = False
        errors = [error]
        try:
            await message.delete()
            deleted = True
        except discord.Forbidden:
            errors.append("Missing permission to delete the message.")
        except discord.HTTPException as exc:
            errors.append(f"Failed to delete message: {exc}")

        await self.log_unscannable_reference(message, deleted, "; ".join(errors))

    @staticmethod
    async def delete_message(message: discord.Message) -> tuple[bool, str | None]:
        try:
            await message.delete()
            return True, None
        except discord.Forbidden:
            return False, "Missing permission to delete the message."
        except discord.HTTPException as exc:
            return False, f"Failed to delete message: {exc}"

    @staticmethod
    def has_timeout_exempt_role(member: discord.Member) -> bool:
        return any(role.id in EXEMPT_ROLE_IDS for role in getattr(member, "roles", []))

    @staticmethod
    def has_always_delete_forward_role(member: discord.Member) -> bool:
        return any(role.id in ALWAYS_DELETE_FORWARD_ROLE_IDS for role in getattr(member, "roles", []))

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

    async def log_unscannable_reference(
        self,
        message: discord.Message,
        deleted: bool,
        error: str,
    ):
        guild = message.guild
        if guild is None:
            return

        log_channel = self.get_log_channel(guild)
        if log_channel is None:
            return

        reference = self.field_value(message, "reference")
        channel = self.field_value(message, "channel")
        embed = discord.Embed(
            title="Unscannable referenced message removed",
            description=(
                "A message with no visible content referenced another message, "
                "but the referenced message could not be loaded for scanning."
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="User", value=f"{message.author.mention} (`{message.author.id}`)", inline=False)
        embed.add_field(name="Channel", value=self.field_value(channel, "mention", str(self.field_value(channel, "id", ""))), inline=True)
        embed.add_field(name="Deleted", value="Yes" if deleted else "No", inline=True)
        embed.add_field(name="Reference type", value=str(self.field_value(reference, "type")), inline=True)
        embed.add_field(name="Reference channel", value=str(self.field_value(reference, "channel_id")), inline=True)
        embed.add_field(name="Reference message", value=str(self.field_value(reference, "message_id")), inline=True)
        embed.add_field(name="Error", value=error[:1024], inline=False)

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return

        deleted = False
        delete_error = None
        if await self.should_delete_forward_from_outside_server(message):
            deleted, delete_error = await self.delete_message(message)
            searchable_content = await self.message_search_content_with_forward_fetch(message)
            match_types = self.find_doxxing_types(searchable_content)
            if not match_types:
                return
        else:
            searchable_content = None
            match_types = None

        is_forward_message = self.is_forward_message(message)
        is_reference_like_message = self.is_reference_like_message(message)
        if message.author.bot and not is_forward_message and not is_reference_like_message:
            return
        if not isinstance(message.author, discord.Member) and not is_forward_message and not is_reference_like_message:
            return

        if searchable_content is None:
            searchable_content = await self.message_search_content_with_forward_fetch(message)
        if match_types is None:
            match_types = self.find_doxxing_types(searchable_content)
        if not match_types:
            unresolved_reference_error = await self.unresolved_reference_error(message)
            if unresolved_reference_error:
                await self.delete_unscannable_reference_message(message, unresolved_reference_error)
            return

        timed_out = False
        dm_sent = False
        errors = [delete_error] if delete_error else []

        if message.author.bot:
            errors.append("Skipped DM because the forwarded message was authored by a bot.")
        else:
            dm_error = await self.notify_author(message)
            if dm_error:
                errors.append(dm_error)
            else:
                dm_sent = True

        if not deleted:
            deleted, delete_error = await self.delete_message(message)
            if delete_error:
                errors.append(delete_error)

        me = message.guild.me or message.guild.get_member(self.bot.user.id)
        if message.author.bot:
            errors.append("Skipped timeout because the forwarded message was authored by a bot.")
        elif me and self.can_timeout(message.author, me):
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
