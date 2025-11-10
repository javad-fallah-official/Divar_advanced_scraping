from __future__ import annotations

import os
from pathlib import Path
import zipapp


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    src_dir = project_root / "src"
    dist_dir = project_root / "dist"
    dist_dir.mkdir(exist_ok=True)
    target = dist_dir / "perf_opt.pyz"
    # Entry point maps to console script in CLI
    zipapp.create_archive(src_dir, target=target, interpreter="/usr/bin/env python3", main="perf_opt.cli:main")
    print(f"Created {target}")


if __name__ == "__main__":
    main()

