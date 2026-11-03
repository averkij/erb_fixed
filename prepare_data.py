"""Download or copy pinned assets; model generation only needs the JSONL."""
import argparse
from pathlib import Path
import shutil
import urllib.request

from erb.common import append_jsonl, write_json
from erb.data import LOCK, archive_members, load_dataset, verify_file
import zipfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--source-dir", type=Path, help="Optional directory of already downloaded pinned files")
    p.add_argument("--jsonl-only", action="store_true")
    args = p.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    names = ["exec_repo_bench.jsonl"] + ([] if args.jsonl_only else ["repos.zip"])
    for name in names:
        dest = args.data_dir / name
        if not dest.exists():
            temp = dest.with_suffix(dest.suffix + ".part")
            if args.source_dir:
                source = args.source_dir / name
                verify_file(source, name)
                shutil.copyfile(source, temp)
            else:
                url = f"https://huggingface.co/datasets/{LOCK['repo']}/resolve/{LOCK['revision']}/{name}"
                with urllib.request.urlopen(url, timeout=120) as src, temp.open("wb") as out:
                    shutil.copyfileobj(src, out)
            verify_file(temp, name)
            temp.replace(dest)
        verify_file(dest, name)
    tasks = load_dataset(args.data_dir / names[0])
    clean = args.data_dir / "tasks.jsonl"
    temp = clean.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as f:
        for task in tasks:
            append_jsonl(f, task)
    temp.replace(clean)
    if not args.jsonl_only:
        with zipfile.ZipFile(args.data_dir / "repos.zip") as z:
            list(archive_members(z))
    write_json(args.data_dir / "prepared.json", {"lock": LOCK, "tasks": len(tasks), "assets": names})
    print(f"Prepared {len(tasks)} clean tasks: {clean}")


if __name__ == "__main__":
    main()
