import unittest
import datetime
from types import SimpleNamespace

from doxxing_detector.doxxing_detector import AUTO_FLAG_DM, DoxxingDetector, EXEMPT_ROLE_IDS, TIMEOUT_DURATION


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
            message_snapshots=[
                SimpleNamespace(content="my number is 555-123-4567", embeds=[]),
            ],
        )

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
            message_snapshots=[
                SimpleNamespace(content="", embeds=[embed]),
            ],
        )

        searchable = DoxxingDetector.message_search_content(message)

        self.assertIn("email", DoxxingDetector.find_doxxing_types(searchable))

    def test_member_with_exempt_role_is_timeout_exempt(self):
        member = SimpleNamespace(
            guild_permissions=SimpleNamespace(administrator=False),
            roles=[SimpleNamespace(id=next(iter(EXEMPT_ROLE_IDS)))],
        )

        self.assertTrue(DoxxingDetector.has_timeout_exempt_role(member))


class DoxxingDetectorAsyncTest(unittest.IsolatedAsyncioTestCase):
    async def test_notify_author_sends_auto_flag_dm(self):
        sent_messages = []

        async def send_dm(content):
            sent_messages.append(content)

        message = SimpleNamespace(author=SimpleNamespace(send=send_dm))

        self.assertIsNone(await DoxxingDetector.notify_author(message))
        self.assertEqual(sent_messages, [AUTO_FLAG_DM])


if __name__ == "__main__":
    unittest.main()
