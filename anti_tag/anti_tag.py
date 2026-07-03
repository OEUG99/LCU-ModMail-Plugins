from __future__ import annotations

import datetime

import discord
from discord.ext import commands


PROTECTED_USER_ID = 95682374230089728
LOG_CHANNEL_ID = 1497340655423324309
TIMEOUT_DURATION = datetime.timedelta(hours=24)
TIMEOUT_MESSAGE = (
    "YOU HAVE BEEN TIMED OUT FOR 24 HOURS FOR TAGGING KEEM ON HIS "
    "WEDDING/HONEY MOON/CELEBRATION! Next time u do this, you will be timed out for a week"
)


class AntiTag(commands.Cog):
    """Timeout members who mention the protected user."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def mentions_protected_user(message: discord.Message) -> bool:
        return any(
            mentioned_user.id == PROTECTED_USER_ID
            for mentioned_user in getattr(message, "mentions", [])
        )

    async def get_log_channel(self, guild: discord.Guild):
        channel = guild.get_channel(LOG_CHANNEL_ID)
        if channel is None:
            channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(LOG_CHANNEL_ID)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                return None
        return channel

    @staticmethod
    def message_excerpt(message: discord.Message) -> str:
        content = " ".join((message.content or "").split())
        if not content:
            return "[no text content]"
        if len(content) > 1000:
            content = f"{content[:997]}..."
        return content.replace("|", "\\|")

    async def send_log(
        self,
        message: discord.Message,
        timed_out: bool,
        dm_sent: bool,
        error: str | None,
    ):
        channel = await self.get_log_channel(message.guild)
        if channel is None or not hasattr(channel, "send"):
            return

        embed = discord.Embed(
            title="Protected user mentioned",
            color=discord.Color.red() if timed_out else discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="User",
            value=f"{message.author.mention} (`{message.author.id}`)",
            inline=False,
        )
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Timeout", value="24 hours" if timed_out else "Failed", inline=True)
        embed.add_field(name="DM sent", value="Yes" if dm_sent else "No", inline=True)
        embed.add_field(
            name="Message",
            value=f"||{self.message_excerpt(message)}||\n[Jump to message]({message.jump_url})",
            inline=False,
        )
        if error:
            embed.add_field(name="Error", value=error[:1024], inline=False)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        if not self.mentions_protected_user(message):
            return

        timed_out = False
        dm_sent = False
        error = None
        try:
            await message.author.timeout(
                discord.utils.utcnow() + TIMEOUT_DURATION,
                reason=f"Mentioned protected user {PROTECTED_USER_ID}.",
            )
            timed_out = True
            try:
                await message.author.send(TIMEOUT_MESSAGE)
                dm_sent = True
            except discord.Forbidden:
                error = "The timeout succeeded, but the user has DMs disabled."
            except discord.HTTPException as exc:
                error = f"The timeout succeeded, but the DM failed: {exc}"
        except discord.Forbidden:
            error = "Missing Moderate Members permission or the user's role is too high."
        except discord.HTTPException as exc:
            error = f"Discord rejected the timeout: {exc}"
        except AttributeError:
            error = "The message author is not a server member and cannot be timed out."

        await self.send_log(message, timed_out, dm_sent, error)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiTag(bot))
