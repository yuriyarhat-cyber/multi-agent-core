"""Copy repository skills into a Codex skills directory."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """Return command-line arguments for the skill installer."""
    parser = argparse.ArgumentParser(
        description="Install repository skills into a Codex skills directory."
    )
    parser.add_argument(
        "--source",
        default=str(Path(__file__).resolve().parents[1] / "skills"),
        help="Path to the repository skills directory.",
    )
    parser.add_argument(
        "--target",
        default=str(Path.home() / ".codex" / "skills"),
        help="Path to the destination Codex skills directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing skill directories in the target.",
    )
    return parser.parse_args()


def copy_skill(source_dir: Path, target_dir: Path, force: bool) -> str:
    """Copy one skill directory into the target location."""
    destination = target_dir / source_dir.name
    if destination.exists():
        if not force:
            return f"skip {source_dir.name} (already exists)"
        shutil.rmtree(destination)
    shutil.copytree(source_dir, destination)
    return f"installed {source_dir.name}"


def main() -> int:
    """Install all repository skills into the requested Codex skills directory."""
    args = parse_args()
    source_root = Path(args.source).resolve()
    target_root = Path(args.target).resolve()

    if not source_root.exists():
        raise SystemExit(f"Source skills directory not found: {source_root}")

    target_root.mkdir(parents=True, exist_ok=True)
    skill_dirs = sorted(path for path in source_root.iterdir() if path.is_dir())
    if not skill_dirs:
        raise SystemExit(f"No skill directories found in: {source_root}")

    for skill_dir in skill_dirs:
        print(copy_skill(skill_dir, target_root, force=args.force))

    print(f"done: installed {len(skill_dirs)} skill(s) into {target_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
