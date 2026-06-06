import datetime
import io
import re
from typing import Optional, List, Tuple

import discord
from discord.ext import commands

# Utility: format None/empty values nicely
def _nick(val: Optional[str]) -> str:
    if val is None:
        return "None"
    if val.strip() == "":
        return '""'  # empty string
    return val[:64] + ("…" if len(val) > 64 else "")

def _roles(roles: Optional[List[discord.Role]]) -> str:
    if not roles:
        return "None"
    return ", ".join([r.name for r in roles])

def _filename_safe(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "server"

class Mod_Detector(commands.Cog):
    """Search the guild audit log for nickname or role changes affecting a given user."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------
    # Nickname history command
    # ------------------------
    @commands.command(name="modnick", help="Show nickname changes for a user.")
    async def mod_nick(self, ctx: commands.Context, user: Optional[discord.User] = None, *, user_id: Optional[str] = None):
        await self._audit_nick(ctx, user, user_id)

    # ------------------------
    # Role changes command (target-based)
    # ------------------------
    @commands.command(name="modroles", help="Show role changes made TO a user.")
    async def mod_roles(self, ctx: commands.Context, user: Optional[discord.User] = None, *, user_id: Optional[str] = None):
        await self._audit_roles(ctx, user, user_id)

    # ------------------------
    # Role actions command (actor-based)
    # ------------------------
    @commands.command(name="modactions", help="Show all role changes a user has performed on others.")
    async def mod_actions(self, ctx: commands.Context, user: Optional[discord.User] = None, *, user_id: Optional[str] = None):
        await self._audit_actions(ctx, user, user_id)

    # ------------------------
    # Recent ban report command
    # ------------------------
    @commands.command(name="modbans", aliases=["banreport", "modbanreport"], help="Generate a text file of bans from the last 30 days.")
    async def mod_bans(self, ctx: commands.Context):
        await self._audit_recent_bans(ctx)

    # ------------------------
    # Internal helpers
    # ------------------------
    async def _get_target_id(self, ctx: commands.Context, user: Optional[discord.User], user_id: Optional[str]) -> Optional[int]:
        if user:
            return user.id
        if user_id:
            try:
                return int(user_id)
            except ValueError:
                await ctx.send("❌ Invalid numeric Discord ID.")
                return None
        await ctx.send("❌ Please provide a user mention or a raw user ID.")
        return None

    async def _audit_nick(self, ctx: commands.Context, user, user_id):
        target_id = await self._get_target_id(ctx, user, user_id)
        if target_id is None:
            return

        guild = ctx.guild
        if guild is None:
            return await ctx.send("❌ This command can only be used in a server.")

        me = guild.me or guild.get_member(self.bot.user.id)
        if not me or not me.guild_permissions.view_audit_log:
            return await ctx.send("❌ I need the **View Audit Log** permission to search nickname changes.")

        status_msg = await ctx.send("🔍 Searching the **full** audit log for nickname changes — this may take a moment on large servers…")

        matches: List[Tuple[discord.AuditLogEntry, Optional[str], Optional[str]]] = []
        try:
            async for entry in guild.audit_logs(limit=None, action=discord.AuditLogAction.member_update):
                if not entry.target or getattr(entry.target, "id", None) != target_id:
                    continue
                before_nick = getattr(entry.changes.before, "nick", None)
                after_nick = getattr(entry.changes.after, "nick", None)
                if before_nick == after_nick:
                    continue
                matches.append((entry, before_nick, after_nick))
        except discord.Forbidden:
            return await ctx.send("❌ Cannot access audit logs. Check my permissions.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Discord API error: `{e}`")

        await status_msg.edit(content=f"✅ Audit log scan complete — found **{len(matches)}** nickname change(s).")

        if not matches:
            return

        PAGE_SIZE = 10
        pages = [matches[i:i + PAGE_SIZE] for i in range(0, len(matches), PAGE_SIZE)]
        target_display = f"<@{target_id}>" if guild.get_member(target_id) else f"{target_id}"

        for page_index, page in enumerate(pages, start=1):
            embed = discord.Embed(
                title=f"Nickname changes for {target_display}",
                description=f"Audit log results (page {page_index}/{len(pages)})",
                color=discord.Color.blurple()
            )
            for entry, before, after in page:
                actor = entry.user.mention if entry.user else "Unknown"
                when = discord.utils.format_dt(entry.created_at, style="R")
                reason = entry.reason or "No reason provided"
                embed.add_field(
                    name=f"Changed by {actor} • {when}",
                    value=f"**Before:** {_nick(before)}\n**After:** {_nick(after)}\n**Reason:** {reason}",
                    inline=False
                )
            await ctx.send(embed=embed)

    async def _audit_roles(self, ctx: commands.Context, user, user_id):
        target_id = await self._get_target_id(ctx, user, user_id)
        if target_id is None:
            return

        guild = ctx.guild
        if guild is None:
            return await ctx.send("❌ This command can only be used in a server.")

        me = guild.me or guild.get_member(self.bot.user.id)
        if not me or not me.guild_permissions.view_audit_log:
            return await ctx.send("❌ I need the **View Audit Log** permission to search role changes.")

        status_msg = await ctx.send("🔍 Searching the **full** audit log for role changes — this may take a moment on large servers…")

        matches: List[Tuple[discord.AuditLogEntry, List[discord.Role], List[discord.Role]]] = []
        try:
            async for entry in guild.audit_logs(limit=None, action=discord.AuditLogAction.member_update):
                if not entry.target or getattr(entry.target, "id", None) != target_id:
                    continue
                before_roles = getattr(entry.changes.before, "roles", [])
                after_roles = getattr(entry.changes.after, "roles", [])
                added = [r for r in after_roles if r not in before_roles]
                removed = [r for r in before_roles if r not in after_roles]
                if not added and not removed:
                    continue
                matches.append((entry, added, removed))
        except discord.Forbidden:
            return await ctx.send("❌ Cannot access audit logs. Check my permissions.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Discord API error: `{e}`")

        await status_msg.edit(content=f"✅ Audit log scan complete — found **{len(matches)}** role change(s).")

        if not matches:
            return

        PAGE_SIZE = 10
        pages = [matches[i:i + PAGE_SIZE] for i in range(0, len(matches), PAGE_SIZE)]
        target_display = f"<@{target_id}>" if guild.get_member(target_id) else f"{target_id}"

        for page_index, page in enumerate(pages, start=1):
            embed = discord.Embed(
                title=f"Role changes for {target_display}",
                description=f"Audit log results (page {page_index}/{len(pages)})",
                color=discord.Color.green()
            )
            for entry, added, removed in page:
                actor = entry.user.mention if entry.user else "Unknown"
                when = discord.utils.format_dt(entry.created_at, style="R")
                reason = entry.reason or "No reason provided"
                embed.add_field(
                    name=f"Changed by {actor} • {when}",
                    value=f"**Added:** {_roles(added)}\n**Removed:** {_roles(removed)}\n**Reason:** {reason}",
                    inline=False
                )
            await ctx.send(embed=embed)

    async def _audit_actions(self, ctx: commands.Context, user, user_id):
        """Search audit log by actor — show all role changes a user performed on others."""
        actor_id = await self._get_target_id(ctx, user, user_id)
        if actor_id is None:
            return

        guild = ctx.guild
        if guild is None:
            return await ctx.send("❌ This command can only be used in a server.")

        me = guild.me or guild.get_member(self.bot.user.id)
        if not me or not me.guild_permissions.view_audit_log:
            return await ctx.send("❌ I need the **View Audit Log** permission to search role changes.")

        actor_display = f"<@{actor_id}>" if guild.get_member(actor_id) else f"{actor_id}"
        status_msg = await ctx.send(f"🔍 Searching the **full** audit log for role changes performed by {actor_display} — this may take a moment…")

        # Each match: (entry, target_display, added_roles, removed_roles)
        matches: List[Tuple[discord.AuditLogEntry, str, List[discord.Role], List[discord.Role]]] = []
        try:
            async for entry in guild.audit_logs(limit=None, action=discord.AuditLogAction.member_update):
                # Filter by who performed the action, not who it was done to
                if not entry.user or entry.user.id != actor_id:
                    continue
                before_roles = getattr(entry.changes.before, "roles", [])
                after_roles = getattr(entry.changes.after, "roles", [])
                added = [r for r in after_roles if r not in before_roles]
                removed = [r for r in before_roles if r not in after_roles]
                if not added and not removed:
                    continue
                # Resolve the target of the action
                target_id = getattr(entry.target, "id", None)
                target_str = f"<@{target_id}>" if target_id and guild.get_member(target_id) else (str(target_id) if target_id else "Unknown")
                matches.append((entry, target_str, added, removed))
        except discord.Forbidden:
            return await ctx.send("❌ Cannot access audit logs. Check my permissions.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Discord API error: `{e}`")

        await status_msg.edit(content=f"✅ Audit log scan complete — {actor_display} performed **{len(matches)}** role change(s) on others.")

        if not matches:
            return

        PAGE_SIZE = 10
        pages = [matches[i:i + PAGE_SIZE] for i in range(0, len(matches), PAGE_SIZE)]

        for page_index, page in enumerate(pages, start=1):
            embed = discord.Embed(
                title=f"Role actions performed by {actor_display}",
                description=f"Audit log results (page {page_index}/{len(pages)})",
                color=discord.Color.orange()
            )
            for entry, target_str, added, removed in page:
                when = discord.utils.format_dt(entry.created_at, style="R")
                reason = entry.reason or "No reason provided"
                embed.add_field(
                    name=f"Target: {target_str} • {when}",
                    value=f"**Added:** {_roles(added)}\n**Removed:** {_roles(removed)}\n**Reason:** {reason}",
                    inline=False
                )
            await ctx.send(embed=embed)

    async def _audit_recent_bans(self, ctx: commands.Context):
        guild = ctx.guild
        if guild is None:
            return await ctx.send("❌ This command can only be used in a server.")

        me = guild.me or guild.get_member(self.bot.user.id)
        if not me or not me.guild_permissions.view_audit_log:
            return await ctx.send("❌ I need the **View Audit Log** permission to search bans.")

        now = datetime.datetime.now(datetime.timezone.utc)
        since = now - datetime.timedelta(days=30)
        status_msg = await ctx.send("🔍 Searching ban audit logs from the last 30 days...")

        matches: List[discord.AuditLogEntry] = []
        try:
            async for entry in guild.audit_logs(limit=None, action=discord.AuditLogAction.ban, after=since):
                if entry.created_at < since:
                    continue
                matches.append(entry)
        except discord.Forbidden:
            return await ctx.send("❌ Cannot access audit logs. Check my permissions.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Discord API error: `{e}`")

        matches.sort(key=lambda entry: entry.created_at, reverse=True)
        report = self._format_ban_report(guild, matches, since, now)
        file_bytes = io.BytesIO(report.encode("utf-8"))
        filename = f"{_filename_safe(guild.name)[:32]}_bans_last_30_days.txt"

        await status_msg.edit(content=f"✅ Found **{len(matches)}** ban(s) from the last 30 days.")
        await ctx.send(file=discord.File(file_bytes, filename=filename))

    def _format_ban_report(
        self,
        guild: discord.Guild,
        entries: List[discord.AuditLogEntry],
        since: datetime.datetime,
        now: datetime.datetime,
    ) -> str:
        lines = [
            f"Ban Report - {guild.name}",
            f"Window: {since.strftime('%Y-%m-%d %H:%M:%S UTC')} to {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Total bans: {len(entries)}",
            "",
        ]

        if not entries:
            lines.append("No ban audit log entries found in the last 30 days.")
            return "\n".join(lines)

        for index, entry in enumerate(entries, start=1):
            target = entry.target
            moderator = entry.user
            target_name = str(target) if target else "Unknown user"
            target_id = getattr(target, "id", "Unknown ID")
            moderator_name = str(moderator) if moderator else "Unknown moderator"
            moderator_id = getattr(moderator, "id", "Unknown ID")
            reason = entry.reason or "No reason provided"

            lines.extend(
                [
                    f"{index}. {target_name} ({target_id})",
                    f"   Banned at: {entry.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    f"   Banned by: {moderator_name} ({moderator_id})",
                    f"   Reason: {reason}",
                    "",
                ]
            )

        return "\n".join(lines)

async def setup(bot: commands.Bot):
    await bot.add_cog(Mod_Detector(bot))
