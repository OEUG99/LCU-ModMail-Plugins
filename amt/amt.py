import discord
from discord.ext import commands


class AMT(commands.Cog, name="AMT"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="unboop")
    @commands.has_permissions(ban_members=True, view_audit_log=True)
    async def check_unban(self, ctx):
        """Unbans users if the audit log shows a ban reason containing 'amt' or 'boop' (case-insensitive)."""
        await self._unban_by_reason_keywords(ctx, ["amt", "boop"])

    @commands.command(name="unstakesaucey")
    @commands.has_permissions(ban_members=True, view_audit_log=True)
    async def unban_stakesaucey(self, ctx):
        """Unbans users if the audit log shows a ban reason containing 'Stakesaucey' or 'The HotDog Revival'."""
        await self._unban_by_reason_keywords(ctx, ["Stakesaucey", "The HotDog Revival"])

    @commands.command(name="unassociated")
    @commands.has_permissions(ban_members=True, view_audit_log=True)
    async def unban_associated_server(self, ctx):
        """Unbans users if the audit log shows a ban reason containing 'Associated Server'."""
        await self._unban_by_reason_keywords(ctx, ["Associated Server"])

    async def _unban_by_reason_keywords(self, ctx, keywords):
        guild = ctx.guild
        if guild is None:
            await ctx.send("❌ This command can only be used in a server.")
            return

        log_channel_id = 1396533397706379274
        log_channel = guild.get_channel(log_channel_id)
        unbanned = []
        seen_ids = set()
        lowered_keywords = [keyword.lower() for keyword in keywords]

        await ctx.send("🔍 Scanning full audit log. This may take a moment...")

        # Fetch audit log entries as an async iterator
        try:
            banned_user_ids = set()
            async for ban_entry in guild.bans():
                banned_user_ids.add(ban_entry.user.id)

            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban):
                user = entry.target
                reason = entry.reason or ""

                if not user or user.id in seen_ids:
                    continue  # Prevent duplicate unban attempts
                seen_ids.add(user.id)

                if any(keyword in reason.lower() for keyword in lowered_keywords):
                    if user.id not in banned_user_ids:
                        continue  # Already unbanned or ban expired

                    try:
                        await guild.unban(user, reason="Auto-unbanned: matched keyword in audit log ban reason.")
                        banned_user_ids.remove(user.id)
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
    await bot.add_cog(AMT(bot))
