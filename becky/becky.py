import discord
from discord.ext import commands


class Becky(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="unboop")
    @commands.has_permissions(ban_members=True, view_audit_log=True)
    async def check_unban(self, ctx):
        """Unbans users if the audit log shows a ban reason containing 'becky' or 'boop' (case-insensitive)."""
        guild = ctx.guild
        keywords = ["becky", "boop"]
        log_channel_id = 1396533397706379274
        log_channel = guild.get_channel(log_channel_id)
        unbanned = []
        seen_ids = set()

        await ctx.send("🔍 Scanning full audit log. This may take a moment...")

        # Fetch audit log entries
        entries = guild.audit_logs(action=discord.AuditLogAction.ban)
        async for entry in entries:  # If supported, this avoids the 'async_generator' issue
            user = entry.target
            reason = entry.reason or ""

            if user.id in seen_ids:
                continue  # Prevent duplicate unban attempts
            seen_ids.add(user.id)

            if any(keyword in reason.lower() for keyword in keywords):
                bans = await guild.bans()
                banned_user_ids = [ban_entry.user.id for ban_entry in bans]
                if user.id not in banned_user_ids:
                    continue  # Already unbanned or ban expired

                try:
                    await guild.unban(user, reason="Auto-unbanned: matched keyword in audit log ban reason.")
                    unbanned.append((user, reason))
                    if log_channel:
                        await log_channel.send(  # Log the successful unban
                            f"🔓 **Unbanned**: {user} (`{user.id}`)\n📝 **Reason**: {reason}"
                        )
                except Exception as e:
                    await ctx.send(f"❌ Failed to unban {user}: {e}")

        # Report the final result back to the invoking user
        if unbanned:
            await ctx.send(f"✅ Unbanned {len(unbanned)} user(s).")
        else:
            await ctx.send("🚫 No users found in full audit log with matching ban reasons.")


async def setup(bot):
    await bot.add_cog(Becky(bot))

