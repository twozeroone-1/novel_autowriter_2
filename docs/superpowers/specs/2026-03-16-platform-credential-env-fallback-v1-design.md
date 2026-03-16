# Platform Credential Env Fallback V1 Design

## Background

`publishing smoke test command v1` is implemented, but it cannot be used in the current Linux/WSL environment because:

- project publishing configs are currently sparse
- secure storage is unavailable (`has_secure_storage() == False`)
- `load_platform_credentials(...)` only reads from keyring-backed secure storage

That means the new smoke path can only report missing credentials, even when an operator could safely provide them through environment variables for a short-lived validation run.

For phases 1-4 closeout, this is now the most practical operational gap:

- the publishing runtime is ready enough to validate
- the adapter boundaries exist
- smoke command exists
- but there is no safe non-UI fallback when keyring is unavailable

## Goal

Allow publishing and smoke flows to load platform credentials from environment variables when secure storage is unavailable or empty.

This should:

- preserve keyring as the primary credential source
- avoid writing secrets to project JSON
- keep existing callers unchanged
- let smoke and publishing flows operate in environments without OS keyring support

## Approaches

### Option 1. Smoke-only environment variable support

Pros:

- smallest immediate change

Cons:

- publishing executor still cannot use the same fallback
- duplicates credential loading rules

### Option 2. Generic loader fallback in `platform_credentials`

Pros:

- one source of truth
- smoke and executor benefit automatically
- smallest change that improves operational behavior across the publishing path

Cons:

- adds a little naming/precedence logic to credential loading

### Option 3. Plaintext `.env` file parsing inside publishing modules

Pros:

- easy to reason about

Cons:

- spreads secret handling across modules
- weaker boundary than the existing credential store module

This spec chooses option 2.

## Scope

### In scope

- environment-based fallback in `load_platform_credentials(...)`
- documented variable naming
- precedence rules between keyring and environment values
- tests covering fallback behavior
- `.env.example` hints for platform credentials

### Out of scope

- changing `save_platform_credentials(...)` to write anywhere except secure storage
- UI redesign for credential entry
- encrypted file storage
- automatic config bootstrap for publishing projects

## Design

### 1. Source precedence

Credential loading order:

1. secure storage payload from keyring, if present and complete
2. project-scoped environment variables
3. platform-global environment variables
4. empty payload

This keeps keyring authoritative where available, while still enabling non-keyring environments.

### 2. Environment variable names

Support both scoped and global names.

Project-scoped:

- `NOVEL_AUTOWRITER_<PROJECT_KEY>_<PLATFORM>_USERNAME`
- `NOVEL_AUTOWRITER_<PROJECT_KEY>_<PLATFORM>_PASSWORD`

Platform-global:

- `NOVEL_AUTOWRITER_<PLATFORM>_USERNAME`
- `NOVEL_AUTOWRITER_<PLATFORM>_PASSWORD`

Normalization rules:

- project key is uppercase
- non-alphanumeric characters collapse to `_`
- leading/trailing `_` are trimmed

Examples:

- project `1`, platform `munpia`
  - `NOVEL_AUTOWRITER_1_MUNPIA_USERNAME`
  - `NOVEL_AUTOWRITER_1_MUNPIA_PASSWORD`
- any project, platform `novelpia`
  - `NOVEL_AUTOWRITER_NOVELPIA_USERNAME`
  - `NOVEL_AUTOWRITER_NOVELPIA_PASSWORD`

### 3. Loader behavior

`load_platform_credentials(project_name, platform_name)` remains the public API.

Its behavior becomes:

- try secure storage first
- if secure storage result is incomplete or empty, try env fallback
- only return a credential payload when both username and password exist
- otherwise return the existing empty payload shape

This avoids partial credentials leaking into callers.

### 4. Documentation and operator workflow

`.env.example` should document the supported platform credential variable names, but must not include real values.

This enables a workflow like:

1. set `NOVEL_AUTOWRITER_1_MUNPIA_USERNAME/PASSWORD`
2. set `NOVEL_AUTOWRITER_1_NOVELPIA_USERNAME/PASSWORD`
3. run smoke command

No other publishing code should need to know whether credentials came from keyring or env.

## Data Flow

1. smoke runner or publishing executor calls `load_platform_credentials(project, platform)`
2. loader tries keyring-backed secure storage
3. if empty/incomplete, loader checks project-scoped env vars
4. if still empty/incomplete, loader checks platform-global env vars
5. caller receives a normalized payload:
   - populated username/password
   - or empty strings for both fields

## Testing

- `tests/test_platform_credentials.py`
  - loads from keyring when secure storage contains credentials
  - falls back to env when secure storage is unavailable
  - prefers project-scoped env over platform-global env
  - returns empty payload when env credentials are partial
- `tests/test_publishing_smoke.py`
  - smoke runner can succeed when credentials are supplied through env fallback

## Non-goals

- storing platform credentials in `.env` automatically
- deleting env credentials through the app
- falling back to plaintext JSON
- changing publishing config shape
