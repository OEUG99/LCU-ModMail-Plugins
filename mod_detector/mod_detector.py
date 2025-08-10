import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Tuple

# Utility: format None/empty values nicely
def _nick(val: Optional[str]) -> str:
    if val is None:
        return "None"
    if val.strip() == "":
        return "“”"  # empty string
    # Limit display to avoid super-wide embeds
    return val[:64] + ("…" if len(val) > 64 else "")

class Mod_Detector(commands.Cog):
    """
    Search the guild audit log for nickname changes affecting a given user.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Slash command group (optional—keeps things tidy if you add more later)
    nick_group = app_commands.Group(
        name="mod_nick",
        description="Nickname tools",
        guild_only=True
    )

    @nick_group.command(name="history", description="Show nickname changes for a user (from the guild audit log).")
    @app_commands.describe(
        user="The user to search for (mention or select), OR leave blank and provide a raw user ID.",
        user_id="Raw Discord ID to search for, if the user isn't in the server / not selectable.",
        limit="How many audit log entries to check (max 200). Default: 100"
    )
    async def nick_history(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.User] = None,
        user_id: Optional[str] = None,
        limit: Optional[int] = 100
    ):
        # Basic guards
        if interaction.guild is None:
            return await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )

        # Normalize/validate target ID
        target_id: Optional[int] = None
        if user is not None:
            target_id = user.id
        elif user_id is not None:
            try:
                target_id = int(user_id)
            except ValueError:
                return await interaction.response.send_message(
                    "That doesn't look like a valid numeric Discord ID.", ephemeral=True
                )
        else:
            return await interaction.response.send_message(
                "Please provide a user or a raw user ID.", ephemeral=True
            )

        # Clamp limit
        if limit is None:
            limit = 100
        limit = max(1, min(200, limit))

        # Permission check (helps give a friendly error before the API does)
        me = interaction.guild.me or interaction.guild.get_member(self.bot.user.id)
        if me is None or not interaction.guild.me.guild_permissions.view_audit_log:
            return await interaction.response.send_message(
                "I need the **View Audit Log** permission to search nickname changes.", ephemeral=True
            )

        await interaction.response.defer(thinking=True, ephemeral=True)

        guild: discord.Guild = interaction.guild

        # Collect matching entries
        matches: List[Tuple[discord.AuditLogEntry, Optional[str], Optional[str]]] = []

        try:
            async for entry in guild.audit_logs(
                limit=limit,
                action=discord.AuditLogAction.member_update
            ):
                # Only keep entries where the target matches the requested ID
                if not entry.target or getattr(entry.target, "id", None) != target_id:
                    continue

                # Only keep those where the "nick" field changed
                # entry.changes.before/after are AuditLogDiff; getattr returns None if nick wasn't touched
                before_nick = getattr(entry.changes.before, "nick", None)
                after_nick = getattr(entry.changes.after, "nick", None)

                # If nick didn't actually change, skip
                if before_nick == after_nick:
                    continue

                matches.append((entry, before_nick, after_nick))

        except discord.Forbidden:
            return await interaction.followup.send(
                "I couldn't access the audit log. Please ensure I have **View Audit Log**.", ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.followup.send(
                f"Discord API error while reading the audit log: `{e}`", ephemeral=True
            )

        if not matches:
            return await interaction.followup.send(
                "No nickname changes found for that ID in the recent audit logs I checked.", ephemeral=True
            )

        # Build a concise embed (paginate if needed)
        # We'll show up to 10 per embed page
        PAGE_SIZE = 10
        pages = [matches[i:i + PAGE_SIZE] for i in range(0, len(matches), PAGE_SIZE)]

        embeds: List[discord.Embed] = []
        target_display = f"<@{target_id}>" if interaction.guild.get_member(target_id) else f"{target_id}"

        for page_index, page in enumerate(pages, start=1):
            embed = discord.Embed(
                title=f"Nickname changes for {target_display}",
                description=f"Results from the guild audit log (page {page_index}/{len(pages)}).",
                color=discord.Color.blurple()
            )
            for entry, before_nick, after_nick in page:
                actor = entry.user.mention if entry.user else "Unknown"
                when = discord.utils.format_dt(entry.created_at, style="R")  # relative timestamp
                reason = entry.reason if entry.reason else "No reason provided"

                embed.add_field(
                    name=f"Changed by {actor} • {when}",
                    value=(
                        f"**Before:** {discord.utils.escape_markdown(_nick(before_nick))}\n"
                        f"**After:**  {discord.utils.escape_markdown(_nick(after_nick))}\n"
                        f"**Reason:** {discord.utils.escape_markdown(reason)}"
                    ),
                    inline=False
                )
            embeds.append(embed)

        # If one page, just send it; if multiple, send the first and attach others as followups
        if len(embeds) == 1:
            await interaction.followup.send(embed=embeds[0], ephemeral=True)
        else:
            # Send first page
            await interaction.followup.send(embed=embeds[0], ephemeral=True)
            # Send the rest as additional ephemeral messages (simple, no buttons)
            for emb in embeds[1:]:
                await interaction.followup.send(embed=emb, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Mod_Detector(bot))
