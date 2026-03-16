import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.munpia_session_bootstrap import bootstrap_munpia_session
from core.platform_session_store import PlatformSessionStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a reusable Munpia manual-login session.")
    parser.add_argument("project_name", help="Project name under data/projects")
    args = parser.parse_args()

    state_path = PlatformSessionStore(args.project_name).session_state_path("munpia")
    saved_path = bootstrap_munpia_session(state_path=state_path)
    print(saved_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
