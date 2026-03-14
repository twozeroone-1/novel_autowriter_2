import unittest

from core.automator import Automator


class FakeContext:
    def __init__(self):
        self.apply_calls = []

    def apply_context_updates(self, *, state: str | None = None, summary_of_previous: str | None = None):
        self.apply_calls.append((state, summary_of_previous))
        return {
            "backup": {
                "state": "old state",
                "summary_of_previous": "old summary",
            },
            "applied": {
                "state": bool(state),
                "summary_of_previous": bool(summary_of_previous),
            },
        }


class FakeGenerator:
    def __init__(self):
        self.calls = []
        self.ctx = FakeContext()
        self.artifact_store = FakeArtifactStore()

    def create_chapter(
        self,
        instruction: str,
        target_length: int,
        include_plot: bool = False,
        plot_strength: str = "balanced",
    ) -> str:
        self.calls.append(("create_chapter", instruction, target_length, include_plot, plot_strength))
        return "draft text"

    def save_markdown_document(self, filename_title: str, content: str, heading_title: str | None = None) -> str:
        self.calls.append(("save_markdown_document", filename_title, content, heading_title))
        return f"/tmp/{filename_title}.md"

    def save_chapter(self, title: str, content: str) -> str:
        self.calls.append(("save_chapter", title, content))
        return f"/tmp/{title}.md"

    def save_chapter_bundle(self, title: str, content: str) -> dict:
        self.calls.append(("save_chapter_bundle", title, content))
        return {
            "path": f"/tmp/{title}.md",
            "episode": {"episode_id": "ep_001", "title": title},
        }

    def build_context_suggestions(self, chapter_content: str) -> dict[str, str]:
        self.calls.append(("build_context_suggestions", chapter_content))
        return {
            "new_state": "state text",
            "new_summary": "summary text",
        }

    def build_canon_update_candidate(self, chapter_content: str) -> dict:
        self.calls.append(("build_canon_update_candidate", chapter_content))
        return {
            "people": {"lead": {"mood": "angry"}},
            "resources": {},
            "hooks": ["new hook"],
            "timeline": [],
        }


class FakeReviewer:
    def __init__(self):
        self.calls = []

    def review_chapter(
        self,
        draft: str,
        include_plot: bool = False,
        plot_strength: str = "balanced",
    ) -> str:
        self.calls.append(("review_chapter", draft, include_plot, plot_strength))
        return "review report"

    def revise_draft(
        self,
        draft: str,
        report: str,
        include_plot: bool = False,
        plot_strength: str = "balanced",
    ) -> str:
        self.calls.append(("revise_draft", draft, report, include_plot, plot_strength))
        return "revised draft"


class FakeArtifactStore:
    def __init__(self):
        self.saved_updates = []

    def save_canon_update(self, episode_id: str, payload: dict) -> dict:
        self.saved_updates.append((episode_id, payload))
        return payload


class RecordingStepContext:
    def __init__(self, messages: list[str], message: str):
        self.messages = messages
        self.message = message

    def __enter__(self):
        self.messages.append(self.message)
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestAutomator(unittest.TestCase):
    def test_run_single_cycle_uses_injected_services_and_reports_progress(self):
        generator = FakeGenerator()
        reviewer = FakeReviewer()
        automator = Automator(project_name="sample", generator=generator, reviewer=reviewer)
        messages: list[str] = []

        result = automator.run_single_cycle(
            chapter_title="Episode 1",
            instruction="scene instruction",
            target_length=3000,
            step_context=lambda message: RecordingStepContext(messages, message),
        )

        self.assertEqual(result["draft"], "draft text")
        self.assertEqual(result["review_report"], "review report")
        self.assertEqual(result["revised_draft"], "revised draft")
        self.assertEqual(result["new_state"], "state text")
        self.assertEqual(result["new_summary"], "summary text")
        self.assertEqual(result["canon_update"]["people"]["lead"]["mood"], "angry")
        self.assertEqual(len(messages), 8)
        self.assertEqual(generator.calls[0], ("create_chapter", "scene instruction", 3000, False, "balanced"))
        self.assertEqual(reviewer.calls[0], ("review_chapter", "draft text", False, "balanced"))
        self.assertEqual(reviewer.calls[1], ("revise_draft", "draft text", "review report", False, "balanced"))
        self.assertEqual(generator.calls[-3], ("save_chapter_bundle", "Episode 1", "revised draft"))
        self.assertEqual(generator.calls[-2], ("build_context_suggestions", "revised draft"))
        self.assertEqual(generator.calls[-1], ("build_canon_update_candidate", "revised draft"))
        self.assertEqual(generator.artifact_store.saved_updates, [("ep_001", result["canon_update"])])

    def test_run_single_cycle_passes_plot_options_to_generator(self):
        generator = FakeGenerator()
        reviewer = FakeReviewer()
        automator = Automator(project_name="sample", generator=generator, reviewer=reviewer)

        automator.run_single_cycle(
            chapter_title="Episode 1",
            instruction="scene instruction",
            target_length=3000,
            include_plot=True,
            plot_strength="strict",
        )

        self.assertEqual(generator.calls[0], ("create_chapter", "scene instruction", 3000, True, "strict"))
        self.assertEqual(reviewer.calls[0], ("review_chapter", "draft text", True, "strict"))
        self.assertEqual(reviewer.calls[1], ("revise_draft", "draft text", "review report", True, "strict"))

    def test_run_single_cycle_keeps_summary_error_in_result(self):
        generator = FakeGenerator()
        reviewer = FakeReviewer()
        automator = Automator(project_name="sample", generator=generator, reviewer=reviewer)

        def build_context_suggestions(_: str) -> dict[str, str]:
            return {
                "new_state": "state text",
                "summary_error": "summary failed",
            }

        generator.build_context_suggestions = build_context_suggestions  # type: ignore[method-assign]

        result = automator.run_single_cycle(
            chapter_title="Episode 1",
            instruction="scene instruction",
            target_length=1000,
        )

        self.assertEqual(result["draft"], "draft text")
        self.assertEqual(result["saved_path"], "/tmp/Episode 1.md")
        self.assertEqual(result["new_state"], "state text")
        self.assertEqual(result["summary_error"], "summary failed")
        self.assertIn("canon_update", result)

    def test_run_single_cycle_keeps_canon_update_error_without_failing_pipeline(self):
        generator = FakeGenerator()
        reviewer = FakeReviewer()
        automator = Automator(project_name="sample", generator=generator, reviewer=reviewer)

        def build_canon_update_candidate(_: str) -> dict:
            raise RuntimeError("canon boom")

        generator.build_canon_update_candidate = build_canon_update_candidate  # type: ignore[method-assign]

        result = automator.run_single_cycle(
            chapter_title="Episode 1",
            instruction="scene instruction",
            target_length=1000,
        )

        self.assertEqual(result["draft"], "draft text")
        self.assertEqual(result["saved_path"], "/tmp/Episode 1.md")
        self.assertEqual(result["new_state"], "state text")
        self.assertEqual(result["new_summary"], "summary text")
        self.assertEqual(result["canon_update_error"], "canon boom")
        self.assertNotIn("canon_update", result)
        self.assertEqual(generator.artifact_store.saved_updates, [])

    def test_apply_context_updates_delegates_to_generator_context(self):
        generator = FakeGenerator()
        reviewer = FakeReviewer()
        automator = Automator(project_name="sample", generator=generator, reviewer=reviewer)

        result = automator.apply_context_updates(
            state="new state",
            summary_of_previous="new summary",
        )

        self.assertEqual(generator.ctx.apply_calls, [("new state", "new summary")])
        self.assertTrue(result["applied"]["state"])
        self.assertTrue(result["applied"]["summary_of_previous"])


if __name__ == "__main__":
    unittest.main()
