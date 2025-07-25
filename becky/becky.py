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

        # Fetch audit log entries as an async iterator
        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban):
                user = entry.target
                reason = entry.reason or ""

                if user.id in seen_ids:
                    continue  # Prevent duplicate unban attempts
                seen_ids.add(user.id)

                if any(keyword in reason.lower() for keyword in keywords):
                    # Check if user is currently banned
                    banned_user_ids = set()
                    async for ban_entry in guild.bans():
                        banned_user_ids.add(ban_entry.user.id)
                    
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

        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to view the audit log.")
        except Exception as e:
            await ctx.send(f"❌ An unexpected error occurred: {e}")


async def setup(bot):
    await bot.add_cog(Becky(bot))

