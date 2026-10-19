"""将 README 中的当前版本递增 1；历史说明中的版本号不变。"""
from pathlib import Path
import argparse
import re


def bump(readme: Path, dry_run: bool = False) -> tuple[int, int]:
    text = readme.read_text(encoding="utf-8")
    intro = re.search(r"当前版本是V(\d+)", text)
    progress = re.search(r"(## 【当前进度】\s*\n)V(\d+)\b", text)
    if not intro or not progress or intro[1] != progress[2]:
        raise ValueError("README 的当前版本和当前进度必须存在且一致")
    old = int(intro[1])
    new = old + 1
    text = re.sub(r"当前版本是V\d+", f"当前版本是V{new}", text, count=1)
    text = re.sub(r"(## 【当前进度】\s*\n)V\d+\b",
                  lambda m: m[1] + f"V{new}", text, count=1)
    if not dry_run:
        readme.write_text(text, encoding="utf-8")
    return old, new


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path,
                        default=Path(__file__).resolve().parents[1] / "README.md")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    old, new = bump(args.readme, args.dry_run)
    print(f"V{old} → V{new}" + ("（预览，未写入）" if args.dry_run else ""))
