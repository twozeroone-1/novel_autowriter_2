import json
import os
import re
from pathlib import Path

from dotenv import dotenv_values

try:
    import keyring
except ModuleNotFoundError:
    keyring = None

from core.app_paths import ENV_FILE_PATH
from core.file_utils import remove_env_key, update_env_file


SERVICE_NAME = "novel-autowriter-publishing"


def has_secure_storage() -> bool:
    if keyring is None:
        return False
    try:
        backend = keyring.get_keyring()
    except Exception:
        return False
    backend_name = backend.__class__.__name__.lower()
    backend_module = backend.__class__.__module__.lower()
    return "fail" not in backend_name and ".fail" not in backend_module


def save_platform_credentials(
    project_name: str,
    platform_name: str,
    username: str,
    password: str,
    env_path: Path = ENV_FILE_PATH,
) -> tuple[bool, str]:
    normalized_username = username.strip()
    normalized_password = password.strip()
    if not normalized_username or not normalized_password:
        return False, "아이디와 비밀번호를 모두 입력해 주세요."
    if not has_secure_storage():
        username_key, password_key = _project_scoped_env_keys(project_name, platform_name)
        update_env_file(env_path, username_key, normalized_username)
        update_env_file(env_path, password_key, normalized_password)
        os.environ[username_key] = normalized_username
        os.environ[password_key] = normalized_password
        return True, ".env fallback에 플랫폼 계정을 저장했습니다."

    payload = json.dumps(
        {
            "username": normalized_username,
            "password": normalized_password,
        },
        ensure_ascii=False,
    )
    try:
        keyring.set_password(SERVICE_NAME, _account_name(project_name, platform_name), payload)
    except Exception as exc:
        return False, f"보안 저장소에 저장하지 못했습니다. {exc}"
    return True, "플랫폼 계정을 보안 저장소에 저장했습니다."


def load_platform_credentials(project_name: str, platform_name: str) -> dict[str, str]:
    secure_payload = _load_secure_credentials(project_name, platform_name)
    if _is_complete_credential_payload(secure_payload):
        return secure_payload

    env_payload = _load_env_credentials(project_name, platform_name)
    if _is_complete_credential_payload(env_payload):
        return env_payload

    return {"username": "", "password": ""}


def clear_platform_credentials(
    project_name: str,
    platform_name: str,
    env_path: Path = ENV_FILE_PATH,
) -> tuple[bool, str]:
    username_key, password_key = _project_scoped_env_keys(project_name, platform_name)
    remove_env_key(env_path, username_key)
    remove_env_key(env_path, password_key)
    os.environ.pop(username_key, None)
    os.environ.pop(password_key, None)

    if not has_secure_storage():
        return True, ".env fallback에서 플랫폼 계정을 삭제했습니다."
    try:
        keyring.delete_password(SERVICE_NAME, _account_name(project_name, platform_name))
    except Exception as exc:
        return False, f"보안 저장소에서 삭제하지 못했습니다. {exc}"
    return True, "플랫폼 계정을 보안 저장소에서 삭제했습니다."


def _account_name(project_name: str, platform_name: str) -> str:
    return f"{project_name.strip()}:{platform_name.strip()}:credentials"


def _load_secure_credentials(project_name: str, platform_name: str) -> dict[str, str]:
    if not has_secure_storage():
        return {"username": "", "password": ""}
    try:
        raw_payload = keyring.get_password(SERVICE_NAME, _account_name(project_name, platform_name))
    except Exception:
        return {"username": "", "password": ""}
    if not raw_payload:
        return {"username": "", "password": ""}

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return {"username": "", "password": ""}

    return {
        "username": str(payload.get("username", "")).strip(),
        "password": str(payload.get("password", "")).strip(),
    }


def _load_env_credentials(project_name: str, platform_name: str) -> dict[str, str]:
    file_env = _load_env_file_values()
    scoped_username_key, scoped_password_key = _project_scoped_env_keys(project_name, platform_name)
    scoped_payload = {
        "username": os.environ.get(scoped_username_key, file_env.get(scoped_username_key, "")).strip(),
        "password": os.environ.get(scoped_password_key, file_env.get(scoped_password_key, "")).strip(),
    }
    if _is_complete_credential_payload(scoped_payload):
        return scoped_payload

    platform_key = _normalize_env_token(platform_name)
    global_username_key = f"NOVEL_AUTOWRITER_{platform_key}_USERNAME"
    global_password_key = f"NOVEL_AUTOWRITER_{platform_key}_PASSWORD"
    return {
        "username": os.environ.get(global_username_key, file_env.get(global_username_key, "")).strip(),
        "password": os.environ.get(global_password_key, file_env.get(global_password_key, "")).strip(),
    }


def _normalize_env_token(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", str(value).strip().upper())
    normalized = normalized.strip("_")
    return normalized or "DEFAULT"


def _project_scoped_env_keys(project_name: str, platform_name: str) -> tuple[str, str]:
    project_key = _normalize_env_token(project_name)
    platform_key = _normalize_env_token(platform_name)
    return (
        f"NOVEL_AUTOWRITER_{project_key}_{platform_key}_USERNAME",
        f"NOVEL_AUTOWRITER_{project_key}_{platform_key}_PASSWORD",
    )


def _load_env_file_values() -> dict[str, str]:
    if not ENV_FILE_PATH.exists():
        return {}
    return {str(key): str(value) for key, value in dotenv_values(ENV_FILE_PATH).items() if value is not None}


def _is_complete_credential_payload(payload: dict[str, str]) -> bool:
    return bool(payload.get("username", "").strip() and payload.get("password", "").strip())
