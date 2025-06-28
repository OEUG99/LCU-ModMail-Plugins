import discord
from discord.ext import commands


class TrollReactor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_user_ids = set()
        self.emoji = '🤡'  # Just the clown emoji
        self.reaction_counts = {}  # Dictionary to track reactions {user_id: reaction_count}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.author.id not in self.target_user_ids:
            return

        try:
            # Add the reaction
            await message.add_reaction(self.emoji)

            # Increment the reaction count
            if message.author.id not in self.reaction_counts:
                self.reaction_counts[message.author.id] = 0
            self.reaction_counts[message.author.id] += 1

            # Check if the reaction count has reached 10
            if self.reaction_counts[message.author.id] >= 10:
                self.target_user_ids.remove(message.author.id)  # Remove the user from the troll list
                del self.reaction_counts[message.author.id]  # Reset their reaction count
                await message.channel.send(f"Trolling for {message.author} has been disabled after 10 reactions!")
        except discord.HTTPException:
            pass

    @commands.command(name="trolladd")
    @commands.has_permissions(manage_messages=True)
    async def add_user(self, ctx, user: discord.User):
        """Add a user to the troll list."""

        # Delete the user's command
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        if user.id in self.target_user_ids:
            await ctx.send(f"{user} is already on the list.")
        else:
            self.target_user_ids.add(user.id)
            await ctx.send(f"{user} will pay for their crimes.")

    @commands.command(name="trollremove")
    @commands.has_permissions(manage_messages=True)
    async def remove_user(self, ctx, user: discord.User):

        # Delete the user's command
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        """Remove a user from the troll list."""
        if user.id not in self.target_user_ids:
            await ctx.send(f"{user} is not on the list.")
        else:
            self.target_user_ids.remove(user.id)
            if user.id in self.reaction_counts:
                del self.reaction_counts[user.id]  # Clean up their reaction count if it exists
            await ctx.send(f"Removed {user} from the list.")


async def setup(bot):
    await bot.add_cog(TrollReactor(bot))

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
