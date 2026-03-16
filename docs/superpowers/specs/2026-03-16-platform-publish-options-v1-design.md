# Platform Publish Options V1 Design

## Goal

Close the remaining phase-3 adapter gap by introducing an explicit `set_publish_options(...)` boundary between packaging and episode upload.

## Context

The top-level design expects platform adapters to expose:

- `login(credentials)`
- `ensure_work(mapping)`
- `upload_episode(payload)`
- `set_publish_options(payload)`
- `verify_publication(expected)`

`_2` already has:

- `Publish Packager`
- upload adapters
- post-upload verification

But publish options are still implicit:

- `visibility` is partially consumed inside `upload_episode`
- `publish_mode` and `reserved_at` are only packaged, not adapter-bound
- executor never calls a publish-options API

## Scope

This slice adds:

- `set_publish_options(payload)` to the adapter contract
- executor sequencing: `set_publish_options(...)` before `upload_episode(...)`
- minimal adapter-side option validation and carry-through

This slice intentionally does not add:

- full live reserved scheduling support on both platforms
- post-schedule polling
- separate schedule confirmation UI

## Recommendation

Use a pending-options boundary inside each adapter.

That means:

- executor passes a normalized options payload to `set_publish_options(...)`
- adapter validates and stores pending options in memory
- `upload_episode(...)` applies the stored options during submission

This is smaller and safer than splitting editor-open and submit into two separate transport phases.

## Architecture

### `core/platform_clients/base.py`

Add abstract method:

```python
def set_publish_options(self, payload: dict) -> PlatformActionResult:
    ...
```

### `core/platform_clients/munpia.py`

Add:

- `_pending_publish_options` state
- `set_publish_options(...)` validation

V1 behavior:

- accept `immediate/public`
- accept `immediate/private`
- reject `reserved` as `requires_user_action`

`upload_episode(...)` should apply visibility from pending options rather than reading the request directly.

### `core/platform_clients/novelpia.py`

Add:

- `_pending_publish_options` state
- `set_publish_options(...)` validation

V1 behavior:

- accept `immediate/public`
- accept `immediate/private`
- reject `reserved` as `requires_user_action`

This keeps phase 3 honest: the option boundary exists, and unsupported schedule modes fail explicitly instead of being silently ignored.

### `core/publishing_executor.py`

Change flow to:

1. `client.login()`
2. `client.ensure_work(...)`
3. `client.set_publish_options({...})`
4. `client.upload_episode(...)`
5. `client.verify_publication(...)`

Persist the normalized option payload into `platform_results[platform]["publish_options"]`.

## Decision Rules

- missing or malformed option payload => `requires_user_action`
- unsupported `reserved` mode => `requires_user_action`
- supported immediate modes continue normally

## Testing

### `tests/test_platform_client_base.py`

- base client exposes `set_publish_options`

### `tests/test_munpia_client.py`

- `set_publish_options` accepts immediate/private
- `set_publish_options` rejects reserved
- `upload_episode` uses stored visibility options

### `tests/test_novelpia_client.py`

- `set_publish_options` accepts immediate/private
- `set_publish_options` rejects reserved
- `upload_episode` uses stored visibility options

### `tests/test_publishing_executor.py`

- executor calls `set_publish_options` before upload
- unsupported reserved mode marks platform failed before upload

## Result

This slice turns publish options from passive metadata into a real adapter boundary and closes a major remaining phase-3 gap without overcommitting to full reserved scheduling support.
