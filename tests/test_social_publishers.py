import unittest
from datetime import date
import linkedin_bot
import youtube_bot

class LinkedInPublisherTests(unittest.TestCase):
    def test_daily_fact_selection_is_stable(self):
        facts = ["fact one", "fact two", "fact three"]
        day = date(2026, 11, 11)
        self.assertEqual(linkedin_bot.select_daily_fact(facts, day), facts[day.toordinal() % 3])
    def test_post_contains_source_fact_and_is_bounded(self):
        fact = "Octopuses have three hearts and blue blood."
        post = linkedin_bot.format_linkedin_post(fact)
        self.assertIn(fact, post)
        self.assertLessEqual(len(post), 3000)
        self.assertIn("#Nature", post)
    def test_linkedin_payload_is_public_member_post(self):
        payload = linkedin_bot.build_post_payload("urn:li:person:abc", "A nature fact")
        self.assertEqual(payload["author"], "urn:li:person:abc")
        self.assertEqual(payload["lifecycleState"], "PUBLISHED")
        self.assertEqual(payload["visibility"], "PUBLIC")

class YouTubePublisherTests(unittest.TestCase):
    def test_portrait_video_selection_prefers_vertical_files(self):
        class Response:
            def raise_for_status(self): pass
            def json(self):
                return {"videos": [{"id": 12, "duration": 30, "video_files": [
                    {"link": "https://example.com/landscape.mp4", "width": 1280, "height": 720},
                    {"link": "https://example.com/portrait.mp4", "width": 720, "height": 1280}]}]}
        original = youtube_bot.requests.get
        original_key = youtube_bot.PEXELS_API_KEY
        youtube_bot.PEXELS_API_KEY = "test-key"
        youtube_bot.requests.get = lambda *args, **kwargs: Response()
        try:
            selected = youtube_bot.fetch_portrait_video("forest")
        finally:
            youtube_bot.requests.get = original
            youtube_bot.PEXELS_API_KEY = original_key
        self.assertEqual(selected["url"], "https://example.com/portrait.mp4")
    def test_long_video_is_not_selected(self):
        class Response:
            def raise_for_status(self): pass
            def json(self):
                return {"videos": [{"id": 13, "duration": 240, "video_files": [
                    {"link": "https://example.com/portrait.mp4", "width": 720, "height": 1280}]}]}
        original = youtube_bot.requests.get
        original_key = youtube_bot.PEXELS_API_KEY
        youtube_bot.PEXELS_API_KEY = "test-key"
        youtube_bot.requests.get = lambda *args, **kwargs: Response()
        try:
            with self.assertRaises(RuntimeError):
                youtube_bot.fetch_portrait_video("forest")
        finally:
            youtube_bot.requests.get = original
            youtube_bot.PEXELS_API_KEY = original_key

if __name__ == "__main__":
    unittest.main()
