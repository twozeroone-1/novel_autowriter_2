# Project Settings Lightweight V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `작품 설정` 화면을 status-first 기준선 관리 화면으로 더 분명하게 만들고, `PREVIOUS SUMMARY`와 보조 도구를 접힌 보조 관리 영역으로 내린다.

**Architecture:** `ui/workspace.py`의 상단 상태 요약과 핵심 4문서 편집은 유지하되, 하단 보조 섹션을 별도 expander로 묶는다. 테스트는 `tests/test_ui_helpers.py`에서 렌더 순서와 보조 섹션 구성을 잠그고, 구현은 기존 helper를 재사용하는 최소 변경으로 제한한다.

**Tech Stack:** Python, Streamlit, unittest

---

## Chunk 1: Red-Green for Project Settings Lightweight UI

### Task 1: Add failing tests for lightweight project settings layout

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/tests/test_ui_helpers.py`
- Modify: `/mnt/c/Users/W/novel_autowriter_2/ui/workspace.py`

- [ ] **Step 1: Write the failing test**

Add tests that assert:
- `render_project_settings_tab(...)` emits a `2. 보조 관리` container after the advanced editor
- `PREVIOUS SUMMARY`, `structured_store`, `characters`, `diagnostics` are rendered from inside that secondary area
- supporting copy mentions `기준선 관리` or equivalent lightweight guidance

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_ui_helpers.TestUiHelpers.test_render_project_settings_tab_groups_supporting_sections_under_secondary_management -v
```

Expected: FAIL because `workspace.py` does not yet render the new secondary management area.

- [ ] **Step 3: Write minimal implementation**

Update `render_project_settings_tab(...)` to:
- keep the existing top summary and warning/action sections
- leave `1. 고급 편집` for the four core documents
- add `2. 보조 관리` expander
- move `PREVIOUS SUMMARY`, structured store overview, character management, diagnostics into that expander
- add short guidance copy describing these as supporting tools

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_ui_helpers -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/c/Users/W/novel_autowriter_2 add \
  docs/superpowers/specs/2026-03-16-project-settings-lightweight-v1-design.md \
  docs/superpowers/plans/2026-03-16-project-settings-lightweight-v1.md \
  tests/test_ui_helpers.py \
  ui/workspace.py
git -C /mnt/c/Users/W/novel_autowriter_2 commit -m "feat: slim down project settings screen"
```

## Chunk 2: Verification

### Task 2: Run focused verification for workspace UI

**Files:**
- Verify: `/mnt/c/Users/W/novel_autowriter_2/ui/workspace.py`
- Verify: `/mnt/c/Users/W/novel_autowriter_2/tests/test_ui_helpers.py`

- [ ] **Step 1: Run focused UI tests**

```bash
python3 -m unittest tests.test_ui_helpers tests.test_operations_dashboard tests.test_episode_workflow tests.test_publishing_ui -v
```

Expected: PASS

- [ ] **Step 2: Run compile check**

```bash
python3 -m py_compile \
  ui/workspace.py \
  tests/test_ui_helpers.py
```

Expected: no output

- [ ] **Step 3: Run diff check**

```bash
git -C /mnt/c/Users/W/novel_autowriter_2 diff --check -- \
  ui/workspace.py \
  tests/test_ui_helpers.py \
  docs/superpowers/specs/2026-03-16-project-settings-lightweight-v1-design.md \
  docs/superpowers/plans/2026-03-16-project-settings-lightweight-v1.md
```

Expected: no output
