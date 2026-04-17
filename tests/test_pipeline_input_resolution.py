import unittest

from fastapi import HTTPException

from backend.routes.pipeline import _resolve_research_input


class ResolveResearchInputTests(unittest.TestCase):
    def test_returns_plain_text_unchanged(self):
        text = "Study how transfer learning affects watermark persistence"
        self.assertEqual(_resolve_research_input(text), text)

    def test_preserves_strict_kaggle_url_as_text(self):
        url = "https://www.kaggle.com/competitions/titanic"
        self.assertEqual(_resolve_research_input(url), url)

    def test_text_with_embedded_kaggle_url_passes_through_unchanged(self):
        text = "Analyze this dataset too: https://www.kaggle.com/competitions/titanic"
        self.assertEqual(_resolve_research_input(text), text)

    def test_reads_existing_relative_file(self):
        resolved = _resolve_research_input("showcase/example_idea.md")
        self.assertTrue(resolved.startswith("Lorenz 吸引子可视化：4 张图讲清混沌"))

    def test_rejects_missing_path_like_input(self):
        with self.assertRaises(HTTPException) as ctx:
            _resolve_research_input("showcase/missing-idea.md")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("was not found", ctx.exception.detail)

    def test_text_with_embedded_file_path_stays_plain_text(self):
        text = "Please use showcase/missing-idea.md as background"
        self.assertEqual(_resolve_research_input(text), text)

    def test_sentence_ending_with_filename_like_token_stays_plain_text(self):
        text = "I think the final writeup should mention report.md"
        self.assertEqual(_resolve_research_input(text), text)


if __name__ == "__main__":
    unittest.main()
