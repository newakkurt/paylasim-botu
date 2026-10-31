import unittest

from repurpose_content import make_platform_variants


class RepurposeContentTests(unittest.TestCase):
    def test_builds_distinct_platform_drafts(self):
        calls = []

        def fake_ask(prompt, as_json=True, tier="strong"):
            calls.append(prompt)
            return (
                '{"instagram_caption":"A surprising nature fact worth saving. '
                'What detail stood out to you? #Nature",'
                '"linkedin_post":"Nature offers practical lessons in resilience. '
                'This example is a reminder to protect habitats. What can we learn?"}'
            )

        result = make_platform_variants(
            {
                "text": "A verified nature fact with enough detail to repurpose safely.",
                "src": {"url": "https://example.org/source"},
            },
            fake_ask,
        )
        self.assertEqual(len(calls), 1)
        self.assertIn("instagram_caption", result)
        self.assertIn("linkedin_post", result)
        self.assertNotEqual(result["instagram_caption"], result["linkedin_post"])

    def test_fallback_when_model_fails(self):
        def broken_ask(*args, **kwargs):
            raise RuntimeError("model unavailable")

        result = make_platform_variants(
            {"text": "A sufficiently detailed approved nature fact for a safe fallback caption."},
            broken_ask,
        )
        self.assertIn("#Nature", result["instagram_caption"])
        self.assertIn("natural world", result["linkedin_post"])


if __name__ == "__main__":
    unittest.main()
