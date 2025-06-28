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

    import asyncio

    @commands.command(name="bomb")
    @commands.has_permissions(manage_messages=True)
    async def bomb(self, ctx, countdown: int = 5):
        """
        Starts a bomb countdown in the chat and deletes the last 15 messages (excluding the countdown message).
        Args:
            countdown (int): The number of seconds for the countdown (default is 5).
        """
        if countdown < 1:
            await ctx.send("The countdown must be at least 1 second!")
            return

        # Delete the user's command
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        # Start the countdown message with the bomb emoji
        bomb_message = await ctx.send(f"💣 The bomb is ticking... {countdown} seconds remaining!")

        # Perform the countdown
        for remaining in range(countdown - 1, -1, -1):
            await asyncio.sleep(1)
            if remaining > 0:
                await bomb_message.edit(content=f"💣 The bomb is ticking... {remaining} seconds remaining!")
            else:
                # Final explosion message
                await bomb_message.edit(content="💥 BOOM! The bomb has exploded!")

        # Delete the last 15 messages in the chat excluding the bomb message
        def check(message):
            # Exclude the bomb message
            return message.id != bomb_message.id

        try:
            deleted = await ctx.channel.purge(limit=15, check=check)
            print(f"Deleted {len(deleted)} messages.")
        except discord.HTTPException as e:
            print(f"Failed to delete messages: {e}")


async def setup(bot):
    await bot.add_cog(TrollReactor(bot))

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
