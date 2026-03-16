import subprocess
from pathlib import Path

from core.app_paths import APP_ROOT


def build_bootstrap_command(*, project_name: str, repo_root: Path = APP_ROOT) -> str:
    return f'cd "{repo_root}" && python3 scripts/bootstrap_munpia_session.py {project_name}'


def launch_bootstrap_terminal(*, project_name: str, repo_root: Path = APP_ROOT) -> tuple[bool, str]:
    command = build_bootstrap_command(project_name=project_name, repo_root=repo_root)
    try:
        subprocess.Popen(
            [
                "cmd.exe",
                "/c",
                "start",
                "",
                "wsl.exe",
                "bash",
                "-lc",
                command,
            ]
        )
    except Exception as exc:
        return False, f"새 터미널 실행에 실패했습니다. 아래 명령을 직접 실행하세요. {exc}"
    return True, "새 터미널에서 문피아 세션 저장을 시작했습니다."
