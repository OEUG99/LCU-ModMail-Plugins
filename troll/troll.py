import asyncio
import discord
from discord.ext import commands


class TrollReactor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_user_ids = set()
        self.emoji = '😷'
        self.reaction_counts = {}
        self.auto_delete_user_ids = set()  # NEW: For persistent deletion

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # NEW: Auto-delete mode
        if message.author.id in self.auto_delete_user_ids:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            return

        # Troll emoji reaction
        if message.author.id not in self.target_user_ids:
            return

        try:
            await message.add_reaction(self.emoji)

            if message.author.id not in self.reaction_counts:
                self.reaction_counts[message.author.id] = 0
            self.reaction_counts[message.author.id] += 1

            if self.reaction_counts[message.author.id] >= 10:
                self.target_user_ids.remove(message.author.id)
                del self.reaction_counts[message.author.id]
        except discord.HTTPException:
            pass

    @commands.command(name="trolladd")
    @commands.has_permissions(manage_messages=True)
    async def leaderboard(self, ctx):
        leaderboard = (
            "💰 **Leaderboard** 💰\n\n"
            "1. 🥇 **Milkers** - $9,999\n"
            "2. 🥈 **Court** - $8,750\n"
            "3. 🥉 **Dark** - $8,420\n"
            "4.    **Bolls** - $7,990\n"
            "5.    **DramaAlert** - $7,580"
        )
        await ctx.send(leaderboard)

    @commands.command(name="trolladd")
    @commands.has_permissions(manage_messages=True)
    async def add_user(self, ctx, user: discord.User, emoji=None):

        if emoji:
            self.emoji = emoji

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        if user.id in self.target_user_ids:
            msg = await ctx.send(f"{user} is already on the list.")
        else:
            self.target_user_ids.add(user.id)
            msg = await ctx.send(f"{user} will pay for their crimes.")
        await asyncio.sleep(5)
        await msg.delete()

    @commands.command(name="trollremove")
    @commands.has_permissions(manage_messages=True)
    async def remove_user(self, ctx, user: discord.User):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        if user.id not in self.target_user_ids:
            msg = await ctx.send(f"{user} is not on the list.")
        else:
            self.target_user_ids.remove(user.id)
            if user.id in self.reaction_counts:
                del self.reaction_counts[user.id]
            msg = await ctx.send(f"Removed {user} from the list.")
        await asyncio.sleep(5)
        await msg.delete()

    @commands.command(name="bomb")
    @commands.has_permissions(manage_messages=True)
    async def bomb(self, ctx, countdown: int = 5):
        if countdown < 1:
            await ctx.send("The countdown must be at least 1 second!")
            return

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        bomb_message = await ctx.send(f"💣 The bomb is ticking... {countdown} seconds remaining!")

        for remaining in range(countdown - 1, -1, -1):
            await asyncio.sleep(1)
            if remaining > 0:
                await bomb_message.edit(content=f"💣 The bomb is ticking... {remaining} seconds remaining!")
            else:
                await bomb_message.edit(content="💥 BOOM! The bomb has exploded!")

        def check(message):
            return message.id != bomb_message.id

        try:
            deleted = await ctx.channel.purge(limit=15, check=check)
            print(f"Deleted {len(deleted)} messages.")
        except discord.HTTPException as e:
            print(f"Failed to delete messages: {e}")

    @commands.command(name="deleteon")
    @commands.has_permissions(manage_messages=True)
    async def start_deleting(self, ctx, user: discord.User):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        self.auto_delete_user_ids.add(user.id)

    @commands.command(name="deleteoff")
    @commands.has_permissions(manage_messages=True)
    async def stop_deleting(self, ctx, user: discord.User):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        if user.id in self.auto_delete_user_ids:
            self.auto_delete_user_ids.remove(user.id)


async def setup(bot):
    await bot.add_cog(TrollReactor(bot))

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
