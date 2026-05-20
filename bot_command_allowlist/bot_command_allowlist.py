import types

from discord.ext import commands


ALLOWED_BOT_IDS = {
    1311920513354043413,  # LOLCow Live Bot
}


class BotCommandAllowlist(commands.Cog):
    """Allow specific bot accounts to invoke prefix commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._previous_process_commands = bot.process_commands
        self._installed = False

        current = getattr(bot.process_commands, "__func__", bot.process_commands)
        if getattr(current, "_bot_command_allowlist_patch", False):
            return

        async def process_commands(bot_self, message):
            if message.author.bot:
                if message.author.id not in ALLOWED_BOT_IDS:
                    return

                ctx = await bot_self.get_context(message)
                await bot_self.invoke(ctx)
                return

            await self._previous_process_commands(message)

        process_commands._bot_command_allowlist_patch = True
        bot.process_commands = types.MethodType(process_commands, bot)
        self._installed = True

    def cog_unload(self):
        if not self._installed:
            return

        current = getattr(self.bot.process_commands, "__func__", self.bot.process_commands)
        if getattr(current, "_bot_command_allowlist_patch", False):
            self.bot.process_commands = self._previous_process_commands


async def setup(bot: commands.Bot):
    await bot.add_cog(BotCommandAllowlist(bot))
