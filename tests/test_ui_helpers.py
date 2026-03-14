import tempfile
import types
import unittest
from contextlib import nullcontext
from pathlib import Path
import sys
from unittest.mock import patch


if "streamlit" not in sys.modules:
    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.session_state = {}
    streamlit_stub.set_page_config = lambda *args, **kwargs: None

    def _cache_resource(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    streamlit_stub.cache_resource = _cache_resource
    sys.modules["streamlit"] = streamlit_stub

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub

from core.token_budget import get_field_stats
import ui.app as app_module
from ui.app import (
    PROJECT_SETTINGS_SUBSECTION_LABELS,
    PROJECT_STATE_KEYS,
    PROJECT_TAB_LABELS,
    load_project_textareas,
    normalize_project_name,
)
from ui.chapters import (
    build_chapter_context_defaults,
    build_session_bound_text_area_kwargs,
    build_workflow_steps,
    persist_chapter_context_update,
    render_generation_budget_panel,
    select_context_update_value,
)
from ui.workspace import (
    ProjectFieldSpec,
    apply_pending_project_textarea_updates,
    build_canon_store_summary,
    build_project_field_panels,
    build_release_policy_summary,
    persist_workspace_field,
    persist_workspace_settings,
    resolve_summary_suggestion_source,
    summarize_text_preview,
)


class TestUiHelpers(unittest.TestCase):
    def setUp(self):
        self.specs = (
            ProjectFieldSpec(
                section_title="1. STORY BIBLE",
                subtitle="World and serialization goal",
                guide_text="700-1500 chars",
                input_label="",
                config_key="worldview",
                textarea_key="ta_worldview",
                height=250,
                actions=(),
            ),
            ProjectFieldSpec(
                section_title="2. STYLE GUIDE",
                subtitle="Voice and prose rules",
                guide_text="200-600 chars",
                input_label="",
                config_key="tone_and_manner",
                textarea_key="ta_tone",
                height=250,
                actions=(),
            ),
            ProjectFieldSpec(
                section_title="3. CONTINUITY",
                subtitle="Fixed canon and relationships",
                guide_text="300-900 chars",
                input_label="",
                config_key="continuity",
                textarea_key="ta_continuity",
                height=250,
                actions=(),
            ),
            ProjectFieldSpec(
                section_title="4. STATE",
                subtitle="Current status and emotions",
                guide_text="150-500 chars",
                input_label="",
                config_key="state",
                textarea_key="ta_state",
                height=250,
                actions=(),
            ),
        )

    def test_normalize_project_name_collapses_spaces(self):
        normalized, error = normalize_project_name("  my   project   name  ")

        self.assertEqual(normalized, "my project name")
        self.assertIsNone(error)

    def test_normalize_project_name_rejects_reserved_name(self):
        normalized, error = normalize_project_name("default_project")

        self.assertIsNone(normalized)
        self.assertIsNotNone(error)

    def test_normalize_project_name_rejects_sample_name(self):
        normalized, error = normalize_project_name("sample")

        self.assertIsNone(normalized)
        self.assertIsNotNone(error)

    def test_normalize_project_name_rejects_path_characters(self):
        normalized, error = normalize_project_name("bad/name")

        self.assertIsNone(normalized)
        self.assertIsNotNone(error)

    def test_build_project_field_panels_marks_first_attention_panel_expanded(self):
        config = {
            "worldview": "",
            "tone_and_manner": "Third-person limited, concise sentences.",
            "continuity": "The school chair never meets the hero directly.",
            "state": "The hero just lost the first duel.",
        }

        panels = build_project_field_panels(self.specs, get_field_stats(config), config)

        self.assertEqual(len(panels), 4)
        self.assertIn("비어 있음", panels[0].expander_label)
        self.assertEqual(panels[0].preview_text, "아직 작성되지 않았습니다.")
        self.assertTrue(panels[0].expanded)
        self.assertFalse(panels[1].expanded)

    def test_build_project_field_panels_truncates_preview_and_keeps_healthy_panels_collapsed(self):
        config = {
            "worldview": (
                "The protagonist enters school with lost memories. "
                "The school is tied to a hidden organization, and each discipline uses a different device. "
                "The story goal is to reveal the power structure of the school and the hero's missing past."
            ),
            "tone_and_manner": "Third-person limited, concise prose, balanced dialogue.",
            "continuity": "The chair and the hero cannot meet directly.",
            "state": "The protagonist won the first field test.",
        }

        panels = build_project_field_panels(self.specs, get_field_stats(config), config)

        self.assertTrue(panels[0].preview_text.endswith("..."))
        self.assertLessEqual(len(panels[0].preview_text), 93)
        self.assertFalse(any(panel.expanded for panel in panels))

    def test_summarize_text_preview_strips_simple_markdown(self):
        preview = summarize_text_preview("# Title\n**Bold** text with `code`", max_chars=50)

        self.assertEqual(preview, "Title Bold text with code")

    def test_build_workflow_steps_marks_done_current_and_upcoming(self):
        steps = build_workflow_steps(
            ("Select draft", "Generate report", "Save revised draft"),
            current_step=1,
        )

        self.assertEqual([step.state for step in steps], ["완료", "현재 단계", "다음 단계"])
        self.assertEqual(
            [step.label for step in steps],
            ["Select draft", "Generate report", "Save revised draft"],
        )

    def test_build_session_bound_text_area_kwargs_uses_value_when_widget_state_missing(self):
        kwargs = build_session_bound_text_area_kwargs("edited_draft", "new draft", {})

        self.assertEqual(kwargs, {"key": "edited_draft", "value": "new draft"})

    def test_build_session_bound_text_area_kwargs_omits_value_when_widget_state_exists(self):
        kwargs = build_session_bound_text_area_kwargs(
            "edited_draft",
            "new draft",
            {"edited_draft": "user edited draft"},
        )

        self.assertEqual(kwargs, {"key": "edited_draft"})

    def test_select_context_update_value_prefers_ai_suggestion(self):
        selected = select_context_update_value("new state", "old state")

        self.assertEqual(selected, "new state")

    def test_select_context_update_value_falls_back_to_current_config(self):
        selected = select_context_update_value("", "old state")

        self.assertEqual(selected, "old state")

    def test_build_chapter_context_defaults_prefers_ai_suggestions(self):
        defaults = build_chapter_context_defaults(
            suggested_state="new state",
            suggested_summary="new summary",
            current_snapshot={
                "state": "old state",
                "summary_of_previous": "old summary",
            },
        )

        self.assertEqual(defaults["state"], "new state")
        self.assertEqual(defaults["summary_of_previous"], "new summary")

    def test_build_chapter_context_defaults_falls_back_to_current_snapshot(self):
        defaults = build_chapter_context_defaults(
            suggested_state="",
            suggested_summary="",
            current_snapshot={
                "state": "old state",
                "summary_of_previous": "old summary",
            },
        )

        self.assertEqual(defaults["state"], "old state")
        self.assertEqual(defaults["summary_of_previous"], "old summary")

    def test_persist_chapter_context_update_routes_state_and_summary_separately(self):
        class FakeContext:
            def __init__(self):
                self.calls = []

            def save_state(self, value):
                self.calls.append(("state", value))

            def save_previous_summary(self, value):
                self.calls.append(("summary", value))

        context = FakeContext()

        result = persist_chapter_context_update(
            context,
            state="latest state",
            summary_of_previous="latest summary",
        )

        self.assertEqual(
            context.calls,
            [
                ("state", "latest state"),
                ("summary", "latest summary"),
            ],
        )
        self.assertEqual(
            result,
            {
                "state": "latest state",
                "summary_of_previous": "latest summary",
            },
        )

    def test_render_generation_budget_panel_reads_workspace_snapshot_for_budget_guidance(self):
        class FakeStreamlit:
            def __init__(self):
                self.session_state = {}

            def expander(self, *args, **kwargs):
                return nullcontext()

            def caption(self, *args, **kwargs):
                return None

            def metric(self, *args, **kwargs):
                return None

            def dataframe(self, *args, **kwargs):
                return None

            def write(self, *args, **kwargs):
                return None

            def button(self, *args, **kwargs):
                return False

            def error(self, *args, **kwargs):
                return None

            def info(self, *args, **kwargs):
                return None

        class FakeContext:
            def __init__(self):
                self.workspace_calls = 0
                self.config_calls = 0

            def get_workspace_settings(self):
                self.workspace_calls += 1
                return {
                    "worldview": "world",
                    "tone_and_manner": "style",
                    "continuity": "rules",
                    "state": "state",
                    "summary_of_previous": "summary",
                }

            def get_config(self):
                self.config_calls += 1
                raise AssertionError("budget guidance should not read get_config")

            def build_generation_prompt(self, *args, **kwargs):
                return "prompt"

        fake_context = FakeContext()
        fake_generator = types.SimpleNamespace(ctx=fake_context)

        with patch.object(sys.modules["ui.chapters"], "st", FakeStreamlit()):
            render_generation_budget_panel(
                fake_generator,
                user_instruction="advance the plot",
                target_length=5000,
                use_plot=True,
                plot_strength="strict",
            )

        self.assertEqual(fake_context.workspace_calls, 1)
        self.assertEqual(fake_context.config_calls, 0)

    def test_resolve_summary_suggestion_source_prefers_pasted_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            latest_path = Path(tmpdir) / "2화.md"
            latest_path.write_text("latest chapter text", encoding="utf-8")

            source_text, source_label = resolve_summary_suggestion_source("pasted text", latest_path)

        self.assertEqual(source_text, "pasted text")
        self.assertEqual(source_label, "붙여넣은 텍스트")

    def test_resolve_summary_suggestion_source_falls_back_to_latest_saved_chapter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            latest_path = Path(tmpdir) / "2화.md"
            latest_path.write_text("latest chapter text", encoding="utf-8")

            source_text, source_label = resolve_summary_suggestion_source("", latest_path)

        self.assertEqual(source_text, "latest chapter text")
        self.assertEqual(source_label, "최근 저장 원고: 2화.md")

    def test_resolve_summary_suggestion_source_returns_empty_when_no_input_exists(self):
        source_text, source_label = resolve_summary_suggestion_source("", None)

        self.assertEqual(source_text, "")
        self.assertEqual(source_label, "")

    def test_project_state_keys_include_workspace_state_source_text(self):
        self.assertIn("workspace_state_source_text", PROJECT_STATE_KEYS)

    def test_project_state_keys_include_project_settings_subsection(self):
        self.assertIn("project_settings_subsection", PROJECT_STATE_KEYS)

    def test_project_state_keys_include_publishing_controls(self):
        self.assertIn("publishing_enabled", PROJECT_STATE_KEYS)
        self.assertIn("publishing_selected_job_id", PROJECT_STATE_KEYS)

    def test_project_state_keys_include_plot_controls_for_review_and_automation(self):
        self.assertIn("review_use_plot", PROJECT_STATE_KEYS)
        self.assertIn("review_plot_strength", PROJECT_STATE_KEYS)
        self.assertIn("auto_use_plot", PROJECT_STATE_KEYS)
        self.assertIn("auto_plot_strength", PROJECT_STATE_KEYS)
        self.assertIn("automation_use_plot", PROJECT_STATE_KEYS)
        self.assertIn("automation_plot_strength", PROJECT_STATE_KEYS)

    def test_project_tab_labels_follow_grouped_order(self):
        self.assertEqual(
            PROJECT_TAB_LABELS,
            (
                "[1] 프로젝트 통합 설정",
                "[2] 회차 생성",
                "[3] 원고 검수",
                "[4] 반자동 연재 모드",
                "[5] 자동화 연재 모드",
                "[6] 외부 플랫폼 업로드",
            ),
        )

    def test_project_settings_subsection_labels_follow_secondary_navigation_order(self):
        self.assertEqual(
            PROJECT_SETTINGS_SUBSECTION_LABELS,
            (
                "기본 설정",
                "아이디어/제목",
                "대형 플롯",
            ),
        )

    def test_build_canon_store_summary_counts_structured_sections(self):
        summary = build_canon_store_summary(
            {
                "people": {"Hero": {"mood": "alert"}, "Mentor": {"status": "missing"}},
                "resources": {"cash": 10, "seal": "open"},
                "hooks": ["missing relic"],
                "timeline": ["ep_001", "ep_002", "ep_003"],
            }
        )

        self.assertEqual(summary.people_count, 2)
        self.assertEqual(summary.resources_count, 2)
        self.assertEqual(summary.hooks_count, 1)
        self.assertEqual(summary.timeline_count, 3)

    def test_build_release_policy_summary_lists_enabled_platforms(self):
        summary = build_release_policy_summary(
            {
                "global": {
                    "max_daily_releases": 2,
                    "burst_allowed": True,
                    "cooldown_failures": 3,
                },
                "platforms": {
                    "munpia": {"enabled": True, "default_times": ["07:00", "21:00"]},
                    "novelpia": {"enabled": False, "default_times": ["21:00"]},
                    "royalroad": {"enabled": True, "default_times": ["09:00"]},
                },
            }
        )

        self.assertEqual(summary.max_daily_releases, 2)
        self.assertTrue(summary.burst_allowed)
        self.assertEqual(summary.cooldown_failures, 3)
        self.assertEqual(summary.enabled_platforms, ("munpia", "royalroad"))

    def test_persist_workspace_field_routes_story_bible_updates_through_story_store(self):
        class FakeContext:
            def __init__(self):
                self.calls = []

            def save_story_bible_sections(self, **kwargs):
                self.calls.append(("story_bible", kwargs))

            def save_state(self, value):
                self.calls.append(("state", value))

            def save_previous_summary(self, value):
                self.calls.append(("summary", value))

        context = FakeContext()
        current_settings = {
            "worldview": "old world",
            "tone_and_manner": "old style",
            "continuity": "old rules",
            "state": "old state",
            "summary_of_previous": "old summary",
        }

        updated = persist_workspace_field(
            context,
            current_settings=current_settings,
            config_key="tone_and_manner",
            value="new style",
        )

        self.assertEqual(updated["tone_and_manner"], "new style")
        self.assertEqual(
            context.calls,
            [
                (
                    "story_bible",
                    {
                        "worldview": "old world",
                        "tone_and_manner": "new style",
                        "continuity": "old rules",
                    },
                )
            ],
        )

    def test_persist_workspace_field_routes_previous_summary_through_summary_boundary(self):
        class FakeContext:
            def __init__(self):
                self.calls = []

            def save_story_bible_sections(self, **kwargs):
                self.calls.append(("story_bible", kwargs))

            def save_state(self, value):
                self.calls.append(("state", value))

            def save_previous_summary(self, value):
                self.calls.append(("summary", value))

        context = FakeContext()
        current_settings = {
            "worldview": "old world",
            "tone_and_manner": "old style",
            "continuity": "old rules",
            "state": "old state",
            "summary_of_previous": "old summary",
        }

        updated = persist_workspace_field(
            context,
            current_settings=current_settings,
            config_key="summary_of_previous",
            value="new summary",
        )

        self.assertEqual(updated["summary_of_previous"], "new summary")
        self.assertEqual(context.calls, [("summary", "new summary")])

    def test_persist_workspace_settings_routes_story_bible_and_state_separately(self):
        class FakeContext:
            def __init__(self):
                self.calls = []

            def save_story_bible_sections(self, **kwargs):
                self.calls.append(("story_bible", kwargs))

            def save_state(self, value):
                self.calls.append(("state", value))

        context = FakeContext()
        updated = persist_workspace_settings(
            context,
            {
                "worldview": "new world",
                "tone_and_manner": "new style",
                "continuity": "new rules",
                "state": "new state",
            },
        )

        self.assertEqual(updated["state"], "new state")
        self.assertEqual(
            context.calls,
            [
                (
                    "story_bible",
                    {
                        "worldview": "new world",
                        "tone_and_manner": "new style",
                        "continuity": "new rules",
                    },
                ),
                ("state", "new state"),
            ],
        )

    def test_load_project_textareas_accepts_workspace_settings_snapshot(self):
        if not hasattr(app_module.st, "session_state") or not isinstance(app_module.st.session_state, dict):
            app_module.st.session_state = {}
        app_module.st.session_state.clear()

        load_project_textareas(
            {
                "worldview": "snapshot world",
                "tone_and_manner": "snapshot style",
                "continuity": "snapshot rules",
                "state": "snapshot state",
            }
        )

        self.assertEqual(app_module.st.session_state["ta_worldview"], "snapshot world")
        self.assertEqual(app_module.st.session_state["ta_tone"], "snapshot style")
        self.assertEqual(app_module.st.session_state["ta_continuity"], "snapshot rules")
        self.assertEqual(app_module.st.session_state["ta_state"], "snapshot state")

    def test_apply_pending_project_textarea_updates_applies_and_clears_pending_values(self):
        session_state = {
            "_pending_project_textarea_updates": {
                "ta_state": "new state",
                "ta_tone": "new tone",
            },
            "ta_state": "old state",
        }

        apply_pending_project_textarea_updates(session_state)

        self.assertEqual(session_state["ta_state"], "new state")
        self.assertEqual(session_state["ta_tone"], "new tone")
        self.assertNotIn("_pending_project_textarea_updates", session_state)

    def test_apply_pending_project_textarea_updates_noops_without_pending_values(self):
        session_state = {"ta_state": "old state"}

        apply_pending_project_textarea_updates(session_state)

        self.assertEqual(session_state, {"ta_state": "old state"})


if __name__ == "__main__":
    unittest.main()
