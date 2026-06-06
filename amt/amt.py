import discord
from discord.ext import commands


class AMT(commands.Cog, name="AMT"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="unboop")
    @commands.has_permissions(ban_members=True)
    async def check_unban(self, ctx):
        """Unbans users if their ban reason contains 'amt' or 'boop' (case-insensitive)."""
        await self._unban_by_reason_keywords(ctx, ["amt", "boop"])

    @commands.command(name="unstakesaucey")
    @commands.has_permissions(ban_members=True)
    async def unban_stakesaucey(self, ctx):
        """Unbans users if their ban reason contains 'Stakesaucey' or 'The HotDog Revival'."""
        await self._unban_by_reason_keywords(ctx, ["Stakesaucey", "The HotDog Revival", "Rastovia"])

    @commands.command(name="unassociated")
    @commands.has_permissions(ban_members=True)
    async def unban_associated_server(self, ctx):
        """Unbans users if their ban reason contains 'Associated Server'."""
        await self._unban_by_reason_keywords(ctx, ["Associated Server"])

    async def _unban_by_reason_keywords(self, ctx, keywords):
        guild = ctx.guild
        if guild is None:
            await ctx.send("❌ This command can only be used in a server.")
            return

        log_channel_id = 1396533397706379274
        log_channel = guild.get_channel(log_channel_id)
        unbanned = []
        lowered_keywords = [keyword.lower() for keyword in keywords]

        await ctx.send("🔍 Scanning all current bans. This may take a moment...")

        try:
            async for ban_entry in guild.bans(limit=None):
                user = ban_entry.user
                reason = ban_entry.reason or ""
                if any(keyword in reason.lower() for keyword in lowered_keywords):
                    try:
                        await guild.unban(user, reason="Auto-unbanned: matched keyword in ban reason.")
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
                await ctx.send("🚫 No currently banned users found with matching ban reasons.")

        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to view or remove bans.")
        except Exception as e:
            await ctx.send(f"❌ An unexpected error occurred: {e}")


async def setup(bot):
    await bot.add_cog(AMT(bot))
