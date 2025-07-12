import discord
from discord.ext import commands
import datetime

HOST_ID = 1324176164918525982
DISCONNECT_DURATION = datetime.timedelta(hours=48)

class HostCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.kick_targets = {}  # {(user_id, channel_id): expiration_time}

    @commands.command(name="vcban")
    async def vcban(self, ctx, channel: discord.VoiceChannel, member: discord.Member):
        """Host-only: Automatically disconnects a user from a specific voice channel for 48 hours."""

        if ctx.author.id != HOST_ID:
            await ctx.send("Only the host can use this command.")
            return

        expire_time = datetime.datetime.utcnow() + DISCONNECT_DURATION
        self.kick_targets[(member.id, channel.id)] = expire_time

        await ctx.send(
            f"{member.mention} will be auto-kicked from voice channel **{channel.name}** for the next 48 hours."
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or member.id == HOST_ID:
            return

        now = datetime.datetime.utcnow()

        if after.channel and isinstance(after.channel, discord.VoiceChannel):
            key = (member.id, after.channel.id)
            expire_time = self.kick_targets.get(key)

            if expire_time and now <= expire_time:
                try:
                    await member.move_to(None)
                    print(f"Auto-kicked {member} from VC: {after.channel.name}")
                except discord.Forbidden:
                    print(f"Missing permission to kick {member}.")
                except discord.HTTPException as e:
                    print(f"Failed to kick {member}: {e}")
            elif expire_time and now > expire_time:
                del self.kick_targets[key]  # cleanup

async def setup(bot):
    await bot.add_cog(HostCommands(bot))
