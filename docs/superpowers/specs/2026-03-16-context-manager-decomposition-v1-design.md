# Context Manager Decomposition v1 Design

## Background

`_2` has already moved most project state into structured stores:

- `StoryBibleStore`
- `ContextStateStore`
- `PlotStore`
- `CanonStore`
- `ReleasePolicyStore`

But [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py) is still a large compatibility-heavy file that mixes several different responsibilities:

- legacy `config.json` shadow reads and writes
- structured store reads
- state and summary persistence
- character normalization and persistence
- prompt section assembly
- generation prompt formatting
- plot compatibility fallback logic

That file is now one of the largest core modules and has become the main place where old compatibility behavior and new structured boundaries still meet.

This matters for two reasons:

1. it is a maintenance risk on its own
2. it blocks later work by making every context-related change touch a single oversized file

The user concern is correct: the repo does not only *look* large because of docs; some core boundaries are still too wide.

## Goal

Reduce the effective responsibility of `ContextManager` without changing its public contract.

For v1, that means:

- keep `ContextManager` as the public facade used by `Generator`, `Reviewer`, and UI code
- split its internal concerns into smaller helpers
- preserve current file formats and compatibility behavior
- avoid unrelated UI refactors in the same slice

This is a cleanup slice, not a feature slice.

## Why This Slice

There are three cleanup tracks currently visible:

1. giant UI modules such as `workspace.py` and `chapters.py`
2. `ContextManager` and its shadow-compatibility logic
3. large runtime coordinators such as `publishing_runtime.py`

The recommended first sub-project is `ContextManager` decomposition because it is:

- core, not purely presentation
- shared by generation, review, and workspace flows
- already partly modernized, making it a good boundary to finish
- small enough to refactor without dragging in the whole UI

This is a better first cleanup slice than UI decomposition because it improves the foundation that later UI cleanup will depend on.

## Approaches

### Option 1. Leave `ContextManager` as-is and only delete dead code

Pros:

- smallest diff
- low immediate risk

Cons:

- does not solve the mixed-responsibility problem
- future changes still keep piling into the same file
- test growth remains concentrated in `tests/test_context_manager.py`

### Option 2. Extract internal helper modules and keep `ContextManager` as a facade

Pros:

- preserves current public API
- lowers local complexity
- keeps migration risk contained
- creates boundaries that can later be tested independently

Cons:

- some temporary duplication while boundaries settle
- requires careful test rebalancing

### Option 3. Replace `ContextManager` with several public services immediately

Pros:

- cleanest long-term architecture
- strongest separation by responsibility

Cons:

- too disruptive for the current codebase
- would force widespread call-site updates across generator, reviewer, UI, and tests
- not appropriate while other v1 features are still unfinished

This spec chooses option 2.

## Scope

### In scope

- split internal context responsibilities into smaller modules
- keep `ContextManager` public methods stable
- remove obvious dead code and compatibility clutter inside `context.py`
- rebalance tests so helper behavior is not all verified through one giant file

### Out of scope

- UI file decomposition
- planner redesign
- changing store file formats
- removing legacy shadow writes entirely
- changing prompt semantics
- marketing, translation, or publishing feature work

## Proposed Architecture

### Public boundary stays the same

`ContextManager` remains the public facade. Existing consumers should still use methods such as:

- `get_story_bible_settings()`
- `get_workspace_settings()`
- `save_story_bible_sections(...)`
- `save_state(...)`
- `save_previous_summary(...)`
- `get_worldview_context()`
- `get_continuity_context()`
- `get_state_context()`
- `build_generation_prompt(...)`

No broad call-site rewrite is part of this slice.

### Internal responsibilities to extract

The current file should be split into focused helpers under `core/`:

- `core/context_story_bible_shadow.py`
  - legacy `config.json` shadow normalization and write-through for story bible fields
- `core/context_state_shadow.py`
  - legacy shadow access for `state` and `summary_of_previous`
- `core/context_characters.py`
  - character normalization, validation, and persistence helpers
- `core/context_prompt_sections.py`
  - prompt section formatting for worldview, continuity, canon, release policy, state, and final prompt assembly
- optionally `core/context_plot_compat.py`
  - plot fallback and legacy plot shadow handling if that logic still makes `context.py` too wide

This is not a rule that every helper must be public. The point is to isolate responsibilities, not to create a new service layer.

## `ContextManager` After Refactor

After decomposition, [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py) should mainly do four things:

1. construct collaborators
2. expose the public facade methods
3. coordinate data from stores and helper modules
4. preserve compatibility behavior at one top-level boundary

It should no longer contain the detailed implementation of:

- character normalization rules
- raw shadow payload normalization
- prompt string composition internals
- plot shadow write-through logic bodies

That logic should live in the extracted helpers.

## Proposed Helper Boundaries

### Story Bible shadow helper

Owns:

- default shadow payload
- loading raw `config.json`
- normalizing story-bible shadow values
- writing story-bible shadow fields back without clobbering unrelated keys

Does not own:

- `StoryBibleStore` persistence semantics
- workspace state fields

### State shadow helper

Owns:

- fallback reads of `state` and `summary_of_previous`
- write-through of those fields into legacy `config.json`

Does not own:

- structured `ContextStateStore` persistence
- story-bible fields

### Character helper

Owns:

- character record validation
- normalization of `traits`
- bulk list normalization

Does not own:

- prompt formatting
- JSON file path setup

### Prompt section helper

Owns:

- formatting of worldview/continuity/canon/release policy/state sections
- assembly of the final generation prompt text
- optional plot block formatting

Does not own:

- raw store reads
- persistence

This separation is important because prompt composition changes often, while store compatibility logic should be stable.

## Testing Strategy

### Current problem

`tests/test_context_manager.py` is very large because it verifies both public behavior and internal normalization details through a single facade.

That is a code smell, not just a testing style preference.

### Proposed test split

Keep high-value facade tests in:

- `tests/test_context_manager.py`

Add focused tests for helpers:

- `tests/test_context_story_bible_shadow.py`
- `tests/test_context_state_shadow.py`
- `tests/test_context_characters.py`
- `tests/test_context_prompt_sections.py`

### What remains in `test_context_manager.py`

Only facade-level guarantees should stay there:

- public API shape
- correct use of structured stores over legacy fallback
- key integration flows such as `build_generation_prompt(...)`
- write-through behavior that crosses multiple helpers

### What moves out

Pure normalization details should move to helper-level tests, for example:

- invalid character filtering
- shadow payload type coercion
- prompt section formatting details
- plot compatibility helper behavior

This should shrink the context test file and make failures easier to interpret.

## Refactor Constraints

### Must preserve

- current on-disk file formats
- current `ContextManager` public method names
- compatibility reads from legacy `config.json` where tests already require fallback behavior
- structured-store precedence rules already enforced by current tests

### Must remove

- dead code such as the `if False:` block in `build_generation_prompt(...)`
- helper logic that can live entirely outside the facade

### Should avoid

- renaming files or APIs unrelated to the decomposition
- changing UI code in the same slice unless required to adapt imports

## Risks

### Risk 1. Hidden compatibility regressions

The file currently mixes modern and legacy behavior, so moving code can break fallback semantics.

Mitigation:

- keep facade integration tests
- move one responsibility at a time
- preserve existing regression tests before trimming any of them

### Risk 2. Too many tiny helper files

Over-splitting would replace one oversized file with noise.

Mitigation:

- group by responsibility, not by individual function
- prefer 3 to 5 meaningful helpers, not a file per method

### Risk 3. Prompt output drift

Prompt composition refactors can accidentally change generation behavior.

Mitigation:

- preserve prompt text via focused tests
- keep string assembly deterministic and centralized

## Success Criteria

This slice is successful when:

1. `ContextManager` public behavior is unchanged
2. `context.py` becomes materially smaller and more coordinator-like
3. helper modules own the previously mixed responsibilities
4. dead code is removed
5. context-related tests are split so failures point to the actual boundary that broke

## Recommendation

Implement `ContextManager decomposition v1` as the first cleanup-specific refactor slice.

This directly addresses the repo-size concern without derailing ongoing v1 feature work, and it improves one of the most central core boundaries before tackling the much larger UI files.
