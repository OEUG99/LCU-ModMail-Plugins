import discord
from discord.ext import commands
from discord import app_commands
from discord import Interaction, InteractionResponse

class DocketManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Role and channel IDs
    HOST_ROLE_ID = 1324176164918525982
    MOD_ROLE_ID = 1229552048672870420
    SUPPORT_FEED_CHANNEL_ID = 1385085325851885709

    DOCKET_ROLES = {
        'cafe': 1333090527490609202,
        'dolls': 1377038061892010066,
        'rewind': 1324410455032205322,
        'live': 1297257623548199023,
        'tech': 1391996231449972837,
        'test': 1393624162840346825,
        'nerds': 1393626339705356298,
        'balls': 1393627528882815047,
        'aussy': 1393681143454503075,
    }

    def has_permissions(self, member: discord.Member) -> bool:
        role_ids = [role.id for role in member.roles]
        return self.HOST_ROLE_ID in role_ids or self.MOD_ROLE_ID in role_ids

    @app_commands.command(name="assign_docket", description="Assign a docket role to a user (Host/Mod only).")
    @app_commands.describe(
        member="The member to assign the role to.",
        docket_type="The docket type to assign."
    )
    @app_commands.choices(docket_type=[
        app_commands.Choice(name="Cafe", value="cafe"),
        app_commands.Choice(name="Dolls", value="dolls"),
        app_commands.Choice(name="Rewind", value="rewind"),
        app_commands.Choice(name="Live", value="live"),
        app_commands.Choice(name="Tech", value="tech"),
        app_commands.Choice(name="Test", value="test"),
        app_commands.Choice(name="Nerds", value="nerds"),
        app_commands.Choice(name="Balls", value="balls"),
        app_commands.Choice(name="Aussy", value="aussy"),
    ])
    async def assign_docket(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        docket_type: app_commands.Choice[str]
    ):
        if not self.has_permissions(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
            return

        role_id = self.DOCKET_ROLES[docket_type.value]
        role = interaction.guild.get_role(role_id)

        if role in member.roles:
            await interaction.response.send_message(f"⚠️ {member.mention} already has the **{role.name}** role.", ephemeral=True)
            return

        await member.add_roles(role, reason=f"Assigned by {interaction.user}")
        await interaction.response.send_message(f"✅ Assigned **{role.name}** to {member.mention}.", ephemeral=True)

        support_channel = interaction.guild.get_channel(self.SUPPORT_FEED_CHANNEL_ID)
        if support_channel:
            await support_channel.send(
                f"🟢 {interaction.user.mention} **assigned** {role.name} to {member.mention}."
            )

    @app_commands.command(name="remove_docket", description="Remove a docket role from a user (Host/Mod only).")
    @app_commands.describe(
        member="The member to remove the role from.",
        docket_type="The docket type to remove."
    )
    @app_commands.choices(docket_type=[
        app_commands.Choice(name="Cafe", value="cafe"),
        app_commands.Choice(name="Dolls", value="dolls"),
        app_commands.Choice(name="Rewind", value="rewind"),
        app_commands.Choice(name="Live", value="live"),
        app_commands.Choice(name="Tech", value="tech"),
        app_commands.Choice(name="Test", value="test"),
        app_commands.Choice(name="Nerds", value="nerds"),
        app_commands.Choice(name="Balls", value="balls"),
        app_commands.Choice(name="Aussy", value="aussy"),
    ])
    async def remove_docket(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        docket_type: app_commands.Choice[str]
    ):
        if not self.has_permissions(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
            return

        role_id = self.DOCKET_ROLES[docket_type.value]
        role = interaction.guild.get_role(role_id)

        if role not in member.roles:
            await interaction.response.send_message(f"⚠️ {member.mention} does not have the **{role.name}** role.", ephemeral=True)
            return

        await member.remove_roles(role, reason=f"Removed by {interaction.user}")
        await interaction.response.send_message(f"✅ Removed **{role.name}** from {member.mention}.", ephemeral=True)

        support_channel = interaction.guild.get_channel(self.SUPPORT_FEED_CHANNEL_ID)
        if support_channel:
            await support_channel.send(
                f"🔴 {interaction.user.mention} **removed** {role.name} from {member.mention}."
            )

    @app_commands.command(name="audit",
                          description="Remove all roles from a member (requires Manage Roles permission).")
    @app_commands.describe(member="The member to remove all roles from.")
    async def remove_all_roles(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ You do not have permission to use this command. (Manage Roles required)", ephemeral=True)
            return

        if member == interaction.user:
            await interaction.response.send_message("❌ You cannot remove your own roles.", ephemeral=True)
            return

        # Exclude the @everyone role
        roles_to_remove = [role for role in member.roles if role != interaction.guild.default_role]

        if not roles_to_remove:
            await interaction.response.send_message(f"⚠️ {member.mention} already has no roles to remove.",
                                                    ephemeral=True)
            return

        await member.remove_roles(*roles_to_remove, reason=f"All roles removed by {interaction.user}")
        await interaction.response.send_message(f"Auditing all roles from {member.mention}.", ephemeral=False)

        # Optional: Log the action in the support feed channel
        support_channel = interaction.guild.get_channel(self.SUPPORT_FEED_CHANNEL_ID)
        if support_channel:
            await support_channel.send(
                f"🟠 {interaction.user.mention} **removed all roles** from {member.mention} for audit."
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(DocketManager(bot))

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
