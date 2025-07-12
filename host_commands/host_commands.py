import discord
from discord.ext import commands
import datetime

HOST_ROLE_ID = 1324176164918525982
MOD_ROLE_ID = 1229552048672870420
DISCONNECT_DURATION = datetime.timedelta(hours=48)

class HostCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.kick_targets = {}  # {(user_id, channel_id): expiration_time}

    def has_permission(self, member: discord.Member) -> bool:
        return any(role.id in (HOST_ROLE_ID, MOD_ROLE_ID) for role in member.roles)

    @commands.command(name="vcban")
    async def vcban(self, ctx, target: discord.Member):
        """Auto-kick a user from the VC you're currently in for 48 hours."""

        if not self.has_permission(ctx.author):
            await ctx.send("You don't have permission to use this command.")
            return

        # Check if the command author is in a VC
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You must be in a voice channel to use this command.")
            return

        vc = ctx.author.voice.channel
        expire_time = datetime.datetime.utcnow() + DISCONNECT_DURATION
        self.kick_targets[(target.id, vc.id)] = expire_time

        await ctx.send(
            f"{target.mention} will be auto-kicked from **{vc.name}** for the next 48 hours."
        )

        # kick the user after adding them to the list
        await target.move_to(None)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
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
                del self.kick_targets[key]  # cleanup expired

async def setup(bot):
    await bot.add_cog(HostCommands(bot))
