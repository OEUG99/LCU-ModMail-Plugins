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
    DOCKET_MANAGER_ROLE_ID = 1426719967914491925
    SUPPORT_FEED_CHANNEL_ID = 1385085325851885709

    DOCKET_ROLES = {
        'alpha': 1428931652217995437,
        'aussy': 1393681143454503075,
        'babe': 1430931252734857360,
        'balls': 1393627528882815047,
        'bus': 1391996231449972837,
        'cafe': 1333090527490609202,
        'cash': 1428928960913473611,
        'chubby': 1394720080759226519,
        'crypt': 1428929891604365363,
        'fire': 1430930643964924035,
        'live': 1297257623548199023,
        'nerds': 1393626339705356298,
        'nuts': 1377038061892010066,
        'pit': 1428930626953805834,
        'queens': 1320513143574761473,
        'rain': 1430931976180727838,
        'reaper': 1407036219111506112,
        'rebel': 1428931106555822121,
        'rewind': 1324410455032205322,
        'test': 1393624162840346825,
        'wild': 1430931598148112459,
    }

    def has_permissions(self, member: discord.Member) -> bool:
        role_ids = [role.id for role in member.roles]
        return self.HOST_ROLE_ID in role_ids or self.MOD_ROLE_ID in role_ids or self.DOCKET_MANAGER_ROLE_ID in role_ids

    @app_commands.command(name="assign_docket", description="Assign a docket role to a user (Host/Mod only).")
    @app_commands.describe(
        member="The member to assign the role to.",
        docket_type="The docket type to assign."
    )
    @app_commands.choices(docket_type=[
        app_commands.Choice(name="Alpha", value="alpha"),
        app_commands.Choice(name="Aussy", value="aussy"),
        app_commands.Choice(name="Babe", value="babe"),
        app_commands.Choice(name="Balls", value="balls"),
        app_commands.Choice(name="Bus", value="bus"),
        app_commands.Choice(name="Cafe", value="cafe"),
        app_commands.Choice(name="Cash", value="cash"),
        app_commands.Choice(name="Chubby", value="chubby"),
        app_commands.Choice(name="Crypt", value="crypt"),
        app_commands.Choice(name="Fire", value="fire"),
        app_commands.Choice(name="Live", value="live"),
        app_commands.Choice(name="Nerds", value="nerds"),
        app_commands.Choice(name="Nuts", value="nuts"),
        app_commands.Choice(name="Pit", value="pit"),
        app_commands.Choice(name="Queens", value="queens"),
        app_commands.Choice(name="Rain", value="rain"),
        app_commands.Choice(name="Reaper", value="reaper"),
        app_commands.Choice(name="Rebel", value="rebel"),
        app_commands.Choice(name="Rewind", value="rewind"),
        app_commands.Choice(name="Test", value="test"),
        app_commands.Choice(name="Wild", value="wild"),
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
        app_commands.Choice(name="Alpha", value="alpha"),
        app_commands.Choice(name="Aussy", value="aussy"),
        app_commands.Choice(name="Babe", value="babe"),
        app_commands.Choice(name="Balls", value="balls"),
        app_commands.Choice(name="Bus", value="bus"),
        app_commands.Choice(name="Cafe", value="cafe"),
        app_commands.Choice(name="Cash", value="cash"),
        app_commands.Choice(name="Chubby", value="chubby"),
        app_commands.Choice(name="Crypt", value="crypt"),
        app_commands.Choice(name="Fire", value="fire"),
        app_commands.Choice(name="Live", value="live"),
        app_commands.Choice(name="Nerds", value="nerds"),
        app_commands.Choice(name="Nuts", value="nuts"),
        app_commands.Choice(name="Pit", value="pit"),
        app_commands.Choice(name="Queens", value="queens"),
        app_commands.Choice(name="Rain", value="rain"),
        app_commands.Choice(name="Reaper", value="reaper"),
        app_commands.Choice(name="Rebel", value="rebel"),
        app_commands.Choice(name="Rewind", value="rewind"),
        app_commands.Choice(name="Test", value="test"),
        app_commands.Choice(name="Wild", value="wild"),
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
