import unittest
import datetime
from types import SimpleNamespace

import discord

from doxxing_detector.doxxing_detector import (
    AUTO_FLAG_DM,
    DoxxingDetector,
    EXEMPT_FORWARD_SOURCE_CHANNEL_IDS,
    EXEMPT_ROLE_IDS,
    FORWARD_SOURCE_GUILD_ID,
    LOG_CHANNEL_ID,
    TIMEOUT_DURATION,
)


class DoxxingDetectorTest(unittest.TestCase):
    def test_auto_timeout_duration_is_three_hours(self):
        self.assertEqual(TIMEOUT_DURATION, datetime.timedelta(hours=3))

    def test_common_phrase_with_place_is_not_an_address(self):
        content = (
            "Can someone please tell me that once you hit 30 everything clicks "
            "into place and it finally starts to feel like your life isn't 2 "
            "seconds and a minor inconvenience away from totally falling apart"
        )

        self.assertEqual(DoxxingDetector.find_doxxing_types(content), [])

    def test_common_phrase_with_way_is_not_an_address(self):
        content = "What the use? Is a 3 v 1 that way"

        self.assertEqual(DoxxingDetector.find_doxxing_types(content), [])
        self.assertEqual(DoxxingDetector.find_doxxing_types(f"{content} <---"), [])

    def test_travel_duration_to_drive_is_not_an_address(self):
        self.assertEqual(
            DoxxingDetector.find_doxxing_types("I have another 18 hours to drive"),
            [],
        )
        self.assertEqual(
            DoxxingDetector.find_doxxing_types("Only 45 minutes left to drive"),
            [],
        )

    def test_180_full_circle_idiom_is_not_an_address(self):
        content = (
            "Good shit, showing a complete 180 brings things full circle. Gives range. "
            'Content. Gives "which version are we going to get today" if you get a show.'
        )

        self.assertEqual(DoxxingDetector.find_doxxing_types(content), [])

    def test_conversational_number_suffix_phrases_are_not_addresses(self):
        examples = [
            "I have 4 hours left on the road",
            "We still have 5 miles down the road",
            "That is 10 minutes down the street",
            "He did a 180 in court",
            "That case took 3 days in court",
            "Went from 0 to 100 and back full circle",
        ]

        for content in examples:
            with self.subTest(content=content):
                self.assertEqual(DoxxingDetector.find_doxxing_types(content), [])

    def test_discord_timestamp_is_not_a_phone_number(self):
        self.assertEqual(DoxxingDetector.find_doxxing_types("<t:1778777152:f>"), [])
        self.assertEqual(
            DoxxingDetector.find_doxxing_types("Reminder is <t:1778777152:f>"),
            [],
        )
        self.assertEqual(
            DoxxingDetector.find_doxxing_types(
                "<t:1778777349:S> <t:1778777352:F> <t:1778777355:R>"
            ),
            [],
        )

    def test_ad_tracking_url_is_not_a_phone_number(self):
        content = (
            "https://mycarpe.com/products/clinical-grade-antiperspirant-underarm-regimen?"
            "nbt=nb%3Aadwords%3Ag%3A11548931703%3A113426630580%3A477343178126"
            "&nb_adtype=pla&nb_kwd=&nb_ti=pla-2382843030958&nb_mi=105166672"
            "&nb_pc=online&nb_pi=34802563547269&nb_ppi=2382843030958"
            "&nb_placement=&nb_li_ms=&nb_lp_ms=&nb_fii=&nb_ap=&nb_mt="
            "&tw_source=google&tw_adid=477343178126&tw_campaign=11548931703"
            "&gad_source=1&gad_campaignid=11548931703"
            "&gclid=Cj0KCQjwzqXQBhD2ARIsAKrIeU9V5rANjsDVDJoRWVdK16UMNpw0Yd_"
            "ULGgqZUEILqI3mVpINCrWDsIaAroaEALw_wcB"
        )

        self.assertEqual(DoxxingDetector.find_doxxing_types(content), [])

    def test_image_url_filename_digits_are_not_a_phone_number(self):
        content = (
            "https://hips.hearstapps.com/hmg-prod/images/"
            "michael-jackson-prepares-to-enter-the-santa-barbara-county-news-photo-1681237854.jpg"
            "?crop=1.00xw:0.852xh;0,0.0564xh&resize=980:* THIS IS A WHITE MAN"
        )

        self.assertEqual(DoxxingDetector.find_doxxing_types(content), [])

    def test_phone_number_outside_url_query_is_still_detected(self):
        content = (
            "https://example.com/products?campaign=11548931703 "
            "my number is 555-123-4567"
        )

        self.assertIn("phone number", DoxxingDetector.find_doxxing_types(content))

    def test_detects_common_address_formats(self):
        self.assertIn("address", DoxxingDetector.find_doxxing_types("123 Main Street"))
        self.assertIn("address", DoxxingDetector.find_doxxing_types("123 Oak Place"))
        self.assertIn("address", DoxxingDetector.find_doxxing_types("456 River Way"))
        self.assertIn("address", DoxxingDetector.find_doxxing_types("45 River Way"))

    def test_search_content_includes_forwarded_message_snapshot_text(self):
        message = SimpleNamespace(
            content="",
            embeds=[],
            attachments=[],
            message_snapshots=[
                SimpleNamespace(content="my number is 555-123-4567", embeds=[], attachments=[]),
            ],
        )

        searchable = DoxxingDetector.message_search_content(message)

        self.assertIn("phone number", DoxxingDetector.find_doxxing_types(searchable))

    def test_search_content_includes_raw_forwarded_snapshot_payload_text(self):
        message = {
            "content": "",
            "embeds": [],
            "attachments": [],
            "message_snapshots": [
                {
                    "content": "my number is 555-123-4567",
                    "embeds": [],
                    "attachments": [],
                },
            ],
        }

        searchable = DoxxingDetector.message_search_content(message)

        self.assertIn("phone number", DoxxingDetector.find_doxxing_types(searchable))

    def test_search_content_includes_gateway_wrapped_snapshot_payload_text(self):
        message = {
            "content": "",
            "embeds": [],
            "attachments": [],
            "message_snapshots": [
                {
                    "message": {
                        "content": "my number is 555-123-4567",
                        "embeds": [],
                        "attachments": [],
                    },
                },
            ],
        }

        searchable = DoxxingDetector.message_search_content(message)

        self.assertIn("phone number", DoxxingDetector.find_doxxing_types(searchable))

    def test_search_content_includes_forwarded_embed_text(self):
        embed = SimpleNamespace(
            title="Contact",
            description="email me at person@example.com",
            fields=[],
        )
        message = SimpleNamespace(
            content="",
            embeds=[],
            attachments=[],
            message_snapshots=[
                SimpleNamespace(content="", embeds=[embed], attachments=[]),
            ],
        )

        searchable = DoxxingDetector.message_search_content(message)

        self.assertIn("email", DoxxingDetector.find_doxxing_types(searchable))

    def test_search_content_includes_forwarded_attachment_text(self):
        message = SimpleNamespace(
            content="",
            embeds=[],
            attachments=[],
            message_snapshots=[
                SimpleNamespace(
                    content="",
                    embeds=[],
                    attachments=[
                        SimpleNamespace(
                            filename="contact.txt",
                            description="email me at person@example.com",
                            url="https://cdn.discordapp.com/attachments/contact.txt",
                            proxy_url="",
                        ),
                    ],
                ),
            ],
        )

        searchable = DoxxingDetector.message_search_content(message)

        self.assertIn("email", DoxxingDetector.find_doxxing_types(searchable))

    def test_forward_reference_detection_accepts_enum_and_raw_value(self):
        self.assertTrue(
            DoxxingDetector.is_forward_reference(
                SimpleNamespace(type=discord.MessageReferenceType.forward)
            )
        )
        self.assertTrue(
            DoxxingDetector.is_forward_reference(
                SimpleNamespace(type=discord.MessageReferenceType.forward.value)
            )
        )
        self.assertTrue(
            DoxxingDetector.is_forward_reference(
                {"type": discord.MessageReferenceType.forward.value}
            )
        )

    def test_forward_message_detection_accepts_snapshots(self):
        message = SimpleNamespace(
            message_snapshots=[
                SimpleNamespace(content="my number is 555-123-4567", embeds=[]),
            ],
            reference=None,
        )

        self.assertTrue(DoxxingDetector.is_forward_message(message))

    def test_forward_message_detection_uses_snapshots_not_reference(self):
        message = SimpleNamespace(
            message_snapshots=[],
            reference=SimpleNamespace(type=discord.MessageReferenceType.forward),
        )

        self.assertFalse(DoxxingDetector.is_forward_message(message))

    def test_member_with_exempt_role_is_timeout_exempt(self):
        member = SimpleNamespace(
            guild_permissions=SimpleNamespace(administrator=False),
            roles=[SimpleNamespace(id=next(iter(EXEMPT_ROLE_IDS)))],
        )

        self.assertTrue(DoxxingDetector.has_timeout_exempt_role(member))

    def test_forward_reference_channel_id_accepts_forward_reference(self):
        message = SimpleNamespace(
            reference=SimpleNamespace(
                type=discord.MessageReferenceType.forward,
                channel_id=1494751503834022040,
            ),
        )

        self.assertEqual(DoxxingDetector.forward_reference_channel_id(message), 1494751503834022040)

    def test_forward_reference_channel_id_ignores_missing_reference(self):
        message = SimpleNamespace(
            channel=SimpleNamespace(id=LOG_CHANNEL_ID),
            reference=None,
        )

        self.assertIsNone(DoxxingDetector.forward_reference_channel_id(message))


class DoxxingDetectorAsyncTest(unittest.IsolatedAsyncioTestCase):
    async def test_notify_author_sends_auto_flag_dm(self):
        sent_messages = []

        async def send_dm(content):
            sent_messages.append(content)

        message = SimpleNamespace(author=SimpleNamespace(send=send_dm))

        self.assertIsNone(await DoxxingDetector.notify_author(message))
        self.assertEqual(sent_messages, [AUTO_FLAG_DM])

    async def test_forward_reference_fetch_content_is_scanned(self):
        class FakeChannel:
            async def fetch_message(self, message_id):
                self.fetched_message_id = message_id
                return SimpleNamespace(
                    content="my address is 123 Main Street",
                    embeds=[],
                    attachments=[],
                    message_snapshots=[],
                    reference=None,
                )

        channel = FakeChannel()
        bot = SimpleNamespace(get_channel=lambda channel_id: channel)
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            content="forward wrapper text",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            reference=SimpleNamespace(
                type=discord.MessageReferenceType.forward,
                channel_id=456,
                message_id=789,
                resolved=None,
                cached_message=None,
            ),
        )

        searchable = await detector.message_search_content_with_forward_fetch(message)

        self.assertEqual(channel.fetched_message_id, 789)
        self.assertIn("address", DoxxingDetector.find_doxxing_types(searchable))

    async def test_reference_message_id_without_channel_is_unresolved(self):
        bot = SimpleNamespace(get_channel=lambda channel_id: None)
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            content="",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            reference=SimpleNamespace(
                type=None,
                channel_id=None,
                message_id=789,
                resolved=None,
                cached_message=None,
            ),
        )

        searchable = await detector.message_search_content_with_forward_fetch(message)
        error = await detector.unresolved_reference_error(message)

        self.assertEqual(searchable, "")
        self.assertIn("no reference_channel_id", error)

    async def test_reference_without_channel_uses_refetched_message_snapshots(self):
        class FakeChannel:
            id = 456

            async def fetch_message(self, message_id):
                self.fetched_message_id = message_id
                return SimpleNamespace(
                    content="",
                    embeds=[],
                    attachments=[],
                    message_snapshots=[
                        SimpleNamespace(
                            content="my number is 555-123-4567",
                            embeds=[],
                            attachments=[],
                        ),
                    ],
                    reference=None,
                )

        channel = FakeChannel()
        bot = SimpleNamespace(get_channel=lambda channel_id: None)
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            id=123,
            content="",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            channel=channel,
            reference=SimpleNamespace(
                type=None,
                channel_id=None,
                message_id=789,
                resolved=None,
                cached_message=None,
            ),
        )

        searchable = await detector.message_search_content_with_forward_fetch(message)
        error = await detector.unresolved_reference_error(message)

        self.assertEqual(channel.fetched_message_id, 123)
        self.assertIn("phone number", DoxxingDetector.find_doxxing_types(searchable))
        self.assertIsNone(error)

    async def test_reference_with_wrong_channel_id_falls_back_to_guild_search(self):
        class OtherChannel:
            id = 999

            async def fetch_message(self, message_id):
                self.fetched_message_id = message_id
                return SimpleNamespace(
                    content="email me at person@example.com",
                    embeds=[],
                    attachments=[],
                    message_snapshots=[],
                    reference=None,
                )

        other_channel = OtherChannel()
        guild = SimpleNamespace(
            text_channels=[other_channel],
            threads=[],
            channels=[],
        )
        bot = SimpleNamespace(get_channel=lambda channel_id: None)
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            content="",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            channel=SimpleNamespace(id=456),
            guild=guild,
            reference=SimpleNamespace(
                type=None,
                channel_id=456,
                message_id=789,
                resolved=None,
                cached_message=None,
            ),
        )

        searchable = await detector.message_search_content_with_forward_fetch(message)

        self.assertEqual(other_channel.fetched_message_id, 789)
        self.assertIn("email", DoxxingDetector.find_doxxing_types(searchable))

    async def test_reference_with_channel_reports_unresolved_when_unfetchable(self):
        bot = SimpleNamespace(get_channel=lambda channel_id: None)
        detector = DoxxingDetector(bot)
        guild = SimpleNamespace(text_channels=[], threads=[], channels=[])
        message = SimpleNamespace(
            content="",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            channel=SimpleNamespace(id=456),
            guild=guild,
            reference=SimpleNamespace(
                type=None,
                channel_id=456,
                message_id=789,
                resolved=None,
                cached_message=None,
            ),
        )

        error = await detector.unresolved_reference_error(message)

        self.assertIn("was not found in any other readable guild channel", error)

    async def test_reference_with_channel_loaded_empty_message_is_not_unresolved(self):
        class FakeChannel:
            id = 456

            async def fetch_message(self, message_id):
                return SimpleNamespace(
                    content="",
                    embeds=[],
                    attachments=[],
                    message_snapshots=[],
                    reference=None,
                )

        channel = FakeChannel()
        bot = SimpleNamespace(get_channel=lambda channel_id: channel)
        detector = DoxxingDetector(bot)
        guild = SimpleNamespace(text_channels=[channel], threads=[], channels=[])
        message = SimpleNamespace(
            content="",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            channel=SimpleNamespace(id=111),
            guild=guild,
            reference=SimpleNamespace(
                type=None,
                channel_id=456,
                message_id=789,
                resolved=None,
                cached_message=None,
            ),
        )

        error = await detector.unresolved_reference_error(message)

        self.assertIsNone(error)

    async def test_delete_unscannable_reference_message_deletes_and_logs(self):
        sent_embeds = []

        async def send_log(embed):
            sent_embeds.append(embed)

        deleted = []

        async def delete_message():
            deleted.append(True)

        log_channel = SimpleNamespace(send=send_log)
        guild = SimpleNamespace(get_channel=lambda channel_id: log_channel)
        bot = SimpleNamespace(get_channel=lambda channel_id: log_channel)
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            guild=guild,
            author=SimpleNamespace(mention="@user", id=123),
            channel=SimpleNamespace(mention="#general", id=456),
            reference=SimpleNamespace(type=None, channel_id=456, message_id=789),
            delete=delete_message,
        )

        await detector.delete_unscannable_reference_message(message, "not fetchable")

        self.assertEqual(deleted, [True])
        self.assertEqual(len(sent_embeds), 1)
        self.assertEqual(sent_embeds[0].title, "Unscannable referenced message removed")

    async def test_on_message_scans_refetched_forward_snapshots(self):
        sent_embeds = []
        sent_dms = []
        deleted = []

        async def send_log(embed):
            sent_embeds.append(embed)

        async def send_dm(content):
            sent_dms.append(content)

        async def delete_message():
            deleted.append(True)

        class FakeChannel:
            id = 456
            mention = "#general"

            async def fetch_message(self, message_id):
                self.fetched_message_id = message_id
                return SimpleNamespace(
                    content="",
                    embeds=[],
                    attachments=[],
                    message_snapshots=[
                        SimpleNamespace(
                            content="my number is 555-123-4567",
                            embeds=[],
                            attachments=[],
                        ),
                    ],
                    reference=None,
                )

        channel = FakeChannel()
        log_channel = SimpleNamespace(send=send_log)
        guild = SimpleNamespace(
            get_channel=lambda channel_id: log_channel,
            get_member=lambda member_id: None,
            me=None,
        )
        bot = SimpleNamespace(get_channel=lambda channel_id: log_channel, user=SimpleNamespace(id=999))
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            id=123,
            guild=guild,
            author=SimpleNamespace(bot=False, mention="@user", id=321, send=send_dm),
            channel=channel,
            content="",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            reference=SimpleNamespace(type=None, channel_id=None, message_id=789),
            delete=delete_message,
        )

        await detector.on_message(message)

        self.assertEqual(channel.fetched_message_id, 123)
        self.assertEqual(deleted, [True])
        self.assertEqual(sent_dms, [AUTO_FLAG_DM])
        self.assertEqual(sent_embeds[-1].title, "Doxxing content removed")

    async def test_on_message_ignores_log_message_without_forward_reference(self):
        deleted = []

        async def delete_message():
            deleted.append(True)

        bot = SimpleNamespace(get_channel=lambda channel_id: None)
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            guild=SimpleNamespace(),
            author=SimpleNamespace(bot=True),
            channel=SimpleNamespace(id=LOG_CHANNEL_ID),
            reference=None,
            delete=delete_message,
        )

        await detector.on_message(message)

        self.assertEqual(deleted, [])

    async def test_on_message_ignores_forward_from_source_server_channel(self):
        deleted = []

        async def delete_message():
            deleted.append(True)

        source_channel = SimpleNamespace(
            id=1494751503834022040,
            guild=SimpleNamespace(id=FORWARD_SOURCE_GUILD_ID),
        )
        source_guild = SimpleNamespace(
            id=FORWARD_SOURCE_GUILD_ID,
            get_channel=lambda channel_id: source_channel if channel_id == source_channel.id else None,
            text_channels=[],
            threads=[],
            channels=[],
        )
        bot = SimpleNamespace(
            get_channel=lambda channel_id: source_channel,
            get_guild=lambda guild_id: source_guild if guild_id == FORWARD_SOURCE_GUILD_ID else None,
        )
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            guild=SimpleNamespace(id=999),
            author=SimpleNamespace(bot=True),
            channel=SimpleNamespace(id=LOG_CHANNEL_ID),
            content="forwarded message wrapper",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            reference=SimpleNamespace(
                type=discord.MessageReferenceType.forward,
                channel_id=source_channel.id,
                message_id=123,
                resolved=None,
                cached_message=None,
            ),
            delete=delete_message,
        )

        await detector.on_message(message)

        self.assertEqual(deleted, [])

    async def test_on_message_ignores_forward_from_exempt_source_channel(self):
        deleted = []

        async def delete_message():
            deleted.append(True)

        exempt_channel_id = next(iter(EXEMPT_FORWARD_SOURCE_CHANNEL_IDS))
        bot = SimpleNamespace(
            get_channel=lambda channel_id: None,
            get_guild=lambda guild_id: None,
        )
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            guild=SimpleNamespace(id=999),
            author=SimpleNamespace(bot=True),
            channel=SimpleNamespace(id=LOG_CHANNEL_ID),
            content="forwarded message wrapper",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            reference=SimpleNamespace(
                type=discord.MessageReferenceType.forward,
                channel_id=exempt_channel_id,
                message_id=123,
                resolved=None,
                cached_message=None,
            ),
            delete=delete_message,
        )

        await detector.on_message(message)

        self.assertEqual(deleted, [])

    async def test_on_message_ignores_forward_from_exempt_role_author(self):
        deleted = []

        async def delete_message():
            deleted.append(True)

        outside_channel = SimpleNamespace(
            id=123,
            guild=SimpleNamespace(id=999),
        )
        bot = SimpleNamespace(
            get_channel=lambda channel_id: outside_channel if channel_id == outside_channel.id else None,
            get_guild=lambda guild_id: None,
        )
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            guild=SimpleNamespace(id=999),
            author=SimpleNamespace(
                bot=False,
                roles=[SimpleNamespace(id=next(iter(EXEMPT_ROLE_IDS)))],
            ),
            channel=SimpleNamespace(id=LOG_CHANNEL_ID),
            content="forwarded message wrapper",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            reference=SimpleNamespace(
                type=discord.MessageReferenceType.forward,
                channel_id=outside_channel.id,
                message_id=123,
                resolved=None,
                cached_message=None,
            ),
            delete=delete_message,
        )

        await detector.on_message(message)

        self.assertEqual(deleted, [])

    async def test_on_message_deletes_forward_from_outside_source_server(self):
        deleted = []
        timed_out = []

        async def delete_message():
            deleted.append(True)

        async def timeout_member(until, reason=None):
            timed_out.append((until, reason))

        outside_channel = SimpleNamespace(
            id=123,
            guild=SimpleNamespace(id=999),
        )
        bot = SimpleNamespace(
            get_channel=lambda channel_id: outside_channel if channel_id == outside_channel.id else None,
            get_guild=lambda guild_id: None,
        )
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            guild=SimpleNamespace(),
            author=SimpleNamespace(
                bot=False,
                guild_permissions=SimpleNamespace(administrator=False),
                roles=[],
                timeout=timeout_member,
            ),
            channel=SimpleNamespace(id=LOG_CHANNEL_ID),
            content="forwarded message wrapper",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            reference=SimpleNamespace(
                type=discord.MessageReferenceType.forward,
                channel_id=outside_channel.id,
                message_id=456,
                resolved=None,
                cached_message=None,
            ),
            delete=delete_message,
        )

        await detector.on_message(message)

        self.assertEqual(deleted, [True])
        self.assertEqual(timed_out, [])

    async def test_on_message_times_out_forward_from_outside_server_with_doxxing_content(self):
        sent_embeds = []
        sent_dms = []
        deleted = []
        timed_out = []

        async def send_log(embed):
            sent_embeds.append(embed)

        async def send_dm(content):
            sent_dms.append(content)

        async def delete_message():
            deleted.append(True)

        async def timeout_member(until, reason=None):
            timed_out.append((until, reason))

        author = SimpleNamespace(
            bot=False,
            mention="@user",
            id=321,
            send=send_dm,
            guild_permissions=SimpleNamespace(administrator=False),
            roles=[],
            timeout=timeout_member,
        )
        me = SimpleNamespace(
            guild_permissions=SimpleNamespace(moderate_members=True),
            top_role=2,
        )
        author.top_role = 1
        log_channel = SimpleNamespace(send=send_log)
        guild = SimpleNamespace(
            get_channel=lambda channel_id: log_channel,
            get_member=lambda member_id: None,
            me=me,
        )
        outside_channel = SimpleNamespace(
            id=123,
            guild=SimpleNamespace(id=999),
        )
        bot = SimpleNamespace(
            get_channel=lambda channel_id: outside_channel if channel_id == outside_channel.id else log_channel,
            get_guild=lambda guild_id: None,
            user=SimpleNamespace(id=999),
        )
        detector = DoxxingDetector(bot)
        message = SimpleNamespace(
            guild=guild,
            author=author,
            channel=SimpleNamespace(id=LOG_CHANNEL_ID, mention="#log"),
            content="my number is 555-123-4567",
            embeds=[],
            attachments=[],
            message_snapshots=[],
            reference=SimpleNamespace(
                type=discord.MessageReferenceType.forward,
                channel_id=outside_channel.id,
                message_id=456,
                resolved=None,
                cached_message=None,
            ),
            delete=delete_message,
        )

        await detector.on_message(message)

        self.assertEqual(deleted, [True])
        self.assertEqual(sent_dms, [AUTO_FLAG_DM])
        self.assertEqual(len(timed_out), 1)
        self.assertEqual(timed_out[0][1], "Posted likely private personal information.")
        self.assertEqual(sent_embeds[-1].title, "Doxxing content removed")


if __name__ == "__main__":
    unittest.main()
