import discord
from discord.ext import commands
from typing import Optional, List, Tuple

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
    # Role changes command
    # ------------------------
    @commands.command(name="modroles", help="Show role changes for a user.")
    async def mod_roles(self, ctx: commands.Context, user: Optional[discord.User] = None, *, user_id: Optional[str] = None):
        await self._audit_roles(ctx, user, user_id)

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

        # Build embeds (paginate if needed)
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

        # Build embeds
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

async def setup(bot: commands.Bot):
    await bot.add_cog(Mod_Detector(bot))