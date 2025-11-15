"""打印当前 profile 配置（校验 YAML）."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.config import load_profile, get_settings  # noqa: E402


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else get_settings().ior_profile
    print(json.dumps(load_profile(name), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
