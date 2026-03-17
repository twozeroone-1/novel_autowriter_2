import unittest

from core.context_prompt_sections import build_generation_prompt, build_plot_block


class TestContextPromptSections(unittest.TestCase):
    def test_build_plot_block_returns_empty_when_plot_disabled(self):
        block = build_plot_block(plot_outline="stored plot", include_plot=False, plot_strength="balanced")

        self.assertEqual(block, "")

    def test_build_generation_prompt_includes_all_sections(self):
        prompt = build_generation_prompt(
            worldview_context="[STORY BIBLE]\nworld",
            continuity_context="[CONTINUITY]\nrules",
            canon_context="[CANON FACTS]\n{}",
            release_policy_context="[RELEASE POLICY]\n{}",

            character_context="[주요 등장인물 프로필]\n- lead",
            plot_block="[PLOT OUTLINE]\nplot",
            user_instruction="next episode",
            length_goal=5000,
        )

        self.assertIn("[STORY BIBLE]", prompt)
        self.assertIn("[RELEASE POLICY]", prompt)
        self.assertIn("[PLOT OUTLINE]", prompt)
        self.assertIn("next episode", prompt)
        self.assertIn("5000", prompt)


if __name__ == "__main__":
    unittest.main()
