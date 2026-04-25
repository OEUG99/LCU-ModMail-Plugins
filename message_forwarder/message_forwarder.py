import discord
from discord.ext import commands
import aiohttp
import io

# Hardcoded forwarding mappings: {source_channel_id: dest_channel_id}
# Add your channel IDs here
FORWARDING_RULES = {
    # Example: 1234567890123456789: 9876543210987654321,
    # Add more mappings as needed
    1497343488482869381: 1497343226368098354, # Live VC
    1497452575690199093: 1497710952030670908, # Queens VC
    1497452973515739186: 1497711107324903749, # Bus VC
    1497453535405801602: 1497711307556655174, # Rewind VC
    1497453945180913755: 1497711428826697768, # Gold VC
    1497454074033868970: 1497711592031129731, # Nerds VC
    1497454329559519233: 1497711734754902096, # Cracked VC
    1497454364045082664: 1497711906037825627, # Gay VC
    1497454839100215408: 1497712369629925437, # Cafe VC
    1497454876312080385: 1497712509207969992, # Chubby VC
    1497454912383221790: 1497712657053257900, # Reaper VC
    1497455511472308385: 1497712934649069738, # Cash VC
    1497455545224003594: 1497713113678483607, # Nuts VC
    1497455585568882738: 1497713211552698448, # Alpha VC
    1497456189875687505: 1497713341114749069, # Crypt VC
    1497456214936911902: 1497713483092066416, # Pit VC
    1497456256548343828: 1497713925360324709, # Rebel VC
    1497456293856809071: 1497714103324770485, # Babe VC
    1497457244386889738: 1497714280202637502, # Wild VC
    1497457263084834967: 1497714528396509244, # Fire VC
    1497457288812695746: 1497714666049372161, # Rain VC
    1497457320215449610: 1497714921570435189, # Fluff VC
    1497457347495464960: 1497715045747130579, # Glass VC
    1497457381246894110: 1497715165137862716, # Jester VC
    1497457406806982736: 1497715284168151251, # Hero VC
}


class MessageForwarder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.forwarding_rules = FORWARDING_RULES
        # Fallback: All voice channel text chats forward to this thread
        self.vc_fallback_thread_id = 1497340830669734059

    async def download_attachment(self, attachment):
        """Download attachment bytes from Discord."""
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    return await resp.read()
                return None

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bot messages to prevent loops
        if message.author.bot:
            return

        # Determine destinations - can send to both mapped and fallback
        destinations = set()

        # Check hardcoded rules first
        if message.channel.id in self.forwarding_rules:
            destinations.add(self.forwarding_rules[message.channel.id])

        # Also add fallback for voice channels
        if isinstance(message.channel, discord.VoiceChannel):
            destinations.add(self.vc_fallback_thread_id)

        if not destinations:
            return

        # Process each destination
        for dest_channel_id in destinations:
            dest_channel = self.bot.get_channel(dest_channel_id)
            if not dest_channel:
                continue

            # Build the forwarded message embed
            embed = discord.Embed(
                description=message.content,
                timestamp=message.created_at,
                color=discord.Color.blurple()
            )
            embed.set_author(name=f"{message.author.name} ({message.author.id})", icon_url=message.author.display_avatar.url)
            embed.set_footer(text=f"From #{message.channel.name}")

            # Prepare files to re-upload (downloads and stores them)
            files_to_send = []
            if message.attachments:
                for attachment in message.attachments:
                    file_bytes = await self.download_attachment(attachment)
                    if file_bytes:
                        files_to_send.append(discord.File(
                            fp=io.BytesIO(file_bytes),
                            filename=attachment.filename,
                            spoiler=attachment.is_spoiler()
                        ))

            # Add note about original embeds if any
            if message.embeds:
                embed.add_field(name="📊 Embeds", value=f"{len(message.embeds)} embed(s) in original message", inline=False)

            try:
                # Send embed first
                await dest_channel.send(embed=embed)
                # Send attachments separately so they appear below
                if files_to_send:
                    await dest_channel.send(files=files_to_send)
            except discord.Forbidden:
                pass
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(MessageForwarder(bot))
