from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands, Interaction
import re
import time

ALLOWED_ROLE_NAMES = ["Mod", "Owner", "Host"]
MEDAL_EMOJIS = {"🥇", "🥈", "🥉"}

EMOJI_PATTERN = re.compile(
    r'['
    r'\U0001F600-\U0001F64F'
    r'\U0001F300-\U0001F5FF'
    r'\U0001F680-\U0001F6FF'
    r'\U0001F1E0-\U0001F1FF'
    r'\u2702-\u27B0'
    r'\u24C2-\U0001F251'
    r']',
    flags=re.UNICODE
)


class EmojiNick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    def has_allowed_role(self, member: discord.Member) -> bool:
        return any(role.name in ALLOWED_ROLE_NAMES for role in member.roles)

    def is_mod_role(self, member: discord.Member) -> bool:
        return any(role.name == "Mod" or "Owner" or "Host" for role in member.roles)

    def split_nickname(self, name: str):
        parts = name.strip().split()
        base = []
        custom = None
        medal = None

        for part in parts:
            if part in MEDAL_EMOJIS:
                medal = part
            elif EMOJI_PATTERN.fullmatch(part):
                custom = part
            else:
                base.append(part)

        return " ".join(base), custom, medal

    def rebuild_nickname(self, base: str, emoji: str | None, medal: str | None):
        parts = [base]
        if emoji:
            parts.append(emoji)
        if medal:
            parts.append(medal)
        return " ".join(parts).strip()

    @app_commands.command(name="setemoji", description="Set a custom emoji in a nickname.")
    @app_commands.describe(emoji="The emoji you want to add", member="The member to modify (optional)")
    async def setemoji(self, interaction: Interaction, emoji: str, member: discord.Member = None):
        target = member or interaction.user
        is_self = target.id == interaction.user.id

        COOLDOWN_USER = 300
        COOLDOWN_MOD = 0

        user_id = interaction.user.id
        now = time.time()
        cooldown_time = COOLDOWN_MOD if self.is_mod_role(interaction.user) else COOLDOWN_USER
        last_used = self.cooldowns.get(user_id, 0)
        elapsed = now - last_used

        if elapsed < cooldown_time:
            wait = int(cooldown_time - elapsed)
            await interaction.response.send_message(
                f"⏳ You're on cooldown! Try again in `{wait}` seconds.",
                ephemeral=True
            )
            return

        self.cooldowns[user_id] = now

        emoji = emoji.strip()
        if not EMOJI_PATTERN.fullmatch(emoji):
            await interaction.response.send_message("❌ Please provide exactly one valid emoji.", ephemeral=True)
            return

        if not is_self and not interaction.user.guild_permissions.manage_nicknames:
            await interaction.response.send_message("❌ You don’t have permission to change other users’ nicknames.",
                                                    ephemeral=True)
            return

        if is_self and not self.has_allowed_role(interaction.user):
            await interaction.response.send_message("❌ You don’t have the required role to use this command.",
                                                    ephemeral=True)
            return

        base, _, medal = self.split_nickname(target.display_name)
        new_nick = self.rebuild_nickname(base, emoji, medal)

        try:
            await target.edit(nick=new_nick[:32])
            await interaction.response.send_message(f"✅ Updated {target.mention}'s nickname to `{new_nick}`",
                                                    ephemeral=not is_self)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don’t have permission to change that user’s nickname.",
                                                    ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Error: {e}", ephemeral=True)

    @app_commands.command(name="rmemoji", description="Remove the custom emoji from a nickname.")
    @app_commands.describe(member="The member to modify (optional)")
    async def removeemoji(self, interaction: Interaction, member: discord.Member = None):
        target = member or interaction.user
        is_self = target.id == interaction.user.id

        if not is_self and not interaction.user.guild_permissions.manage_nicknames:
            await interaction.response.send_message("❌ You don’t have permission to change other users’ nicknames.",
                                                    ephemeral=True)
            return

        base, _, medal = self.split_nickname(target.display_name)
        new_nick = self.rebuild_nickname(base, None, medal)

        try:
            await target.edit(nick=new_nick[:32])
            await interaction.response.send_message(f"✅ Removed emoji from {target.mention}'s nickname.",
                                                    ephemeral=not is_self)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don’t have permission to change that user’s nickname.",
                                                    ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Error: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if self.has_allowed_role(before) and not self.has_allowed_role(after):
            base, _, medal = self.split_nickname(after.display_name)
            new_nick = self.rebuild_nickname(base, None, medal)
            try:
                await after.edit(nick=new_nick[:32])
            except (discord.Forbidden, Exception):
                pass

    async def cog_load(self):
        guild = discord.Object(id=1384789639746949150)
        self.bot.tree.add_command(self.setemoji, guild=guild)


async def setup(bot):
    await bot.add_cog(EmojiNick(bot))
