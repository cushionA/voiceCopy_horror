#!/usr/bin/env python3
"""
Audio Asset Index Manager
音声ライブラリのインデックス作成・更新・検索を行う。

Usage:
  python tools/asset-index.py build               # フルスキャン（インデックス作成）
  python tools/asset-index.py update              # 差分更新
  python tools/asset-index.py search <query>      # キーワード検索
  python tools/asset-index.py stats               # 統計情報
"""
import json
import os
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "asset-gen.json"

AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".aiff", ".flac"}


def load_config():
    if not CONFIG_PATH.exists():
        print(f"Error: config/asset-gen.json not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_index_path(config):
    return PROJECT_ROOT / config.get("index_path", "config/audio-index.json")


def scan_library(lib_config):
    """指定ライブラリをスキャンし、ファイルエントリのリストを返す。"""
    root = Path(lib_config["path"])
    lib_name = lib_config["name"]
    entries = []

    if not root.exists():
        print(f"Warning: Library path does not exist: {root}", file=sys.stderr)
        return entries

    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in AUDIO_EXTENSIONS:
                continue
            full_path = Path(dirpath) / fname
            rel_path = full_path.relative_to(root)
            folder = str(rel_path.parent) if str(rel_path.parent) != "." else ""
            name_no_ext = os.path.splitext(fname)[0]
            size_kb = round(full_path.stat().st_size / 1024, 1)
            mtime = full_path.stat().st_mtime

            entries.append({
                "path": str(full_path).replace("\\", "/"),
                "rel_path": str(rel_path).replace("\\", "/"),
                "library": lib_name,
                "folder": folder.replace("\\", "/"),
                "name": name_no_ext,
                "ext": ext,
                "size_kb": size_kb,
                "mtime": mtime,
            })

    return entries


def build_index(config):
    """全ライブラリをフルスキャンしてインデックスを作成。"""
    now = datetime.now(timezone.utc).isoformat()
    libraries = []
    all_files = []

    for lib in config.get("audio_libraries", []):
        print(f"Scanning: {lib['name']} ({lib['path']})...")
        entries = scan_library(lib)
        libraries.append({
            "name": lib["name"],
            "root": lib["path"],
            "file_count": len(entries),
        })
        all_files.extend(entries)

    index = {
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "libraries": libraries,
        "files": all_files,
    }

    index_path = get_index_path(config)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    total = len(all_files)
    print(f"Index built: {total} files from {len(libraries)} libraries")
    print(f"Saved to: {index_path}")
    return index


def load_index(config):
    index_path = get_index_path(config)
    if not index_path.exists():
        print("Error: Index not found. Run 'build' first.", file=sys.stderr)
        sys.exit(1)
    with open(index_path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_index(config):
    """差分更新: 新規追加・削除を検出してインデックスを更新。"""
    index = load_index(config)
    existing_paths = {f["path"] for f in index["files"]}
    existing_by_path = {f["path"]: f for f in index["files"]}

    added = 0
    removed = 0
    current_paths = set()

    for lib in config.get("audio_libraries", []):
        entries = scan_library(lib)
        for entry in entries:
            current_paths.add(entry["path"])
            if entry["path"] not in existing_paths:
                index["files"].append(entry)
                added += 1
            elif entry["mtime"] > existing_by_path[entry["path"]].get("mtime", 0):
                # ファイルが更新されている場合、エントリを更新
                old_entry = existing_by_path[entry["path"]]
                old_entry.update(entry)

    # 削除されたファイルを除去
    new_files = []
    for f in index["files"]:
        if f["path"] in current_paths:
            new_files.append(f)
        else:
            removed += 1
    index["files"] = new_files

    # ライブラリ統計を更新
    lib_counts = {}
    for f in index["files"]:
        lib_counts[f["library"]] = lib_counts.get(f["library"], 0) + 1
    for lib_info in index["libraries"]:
        lib_info["file_count"] = lib_counts.get(lib_info["name"], 0)

    index["updated_at"] = datetime.now(timezone.utc).isoformat()

    index_path = get_index_path(config)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"Index updated: +{added} added, -{removed} removed")
    print(f"Total files: {len(index['files'])}")


def search_index(config, query):
    """キーワード検索して候補を返す（最大20件）。"""
    index = load_index(config)
    keywords = re.split(r"[\s　]+", query.lower().strip())

    scored = []
    for entry in index["files"]:
        searchable = f"{entry['name']} {entry['folder']} {entry['library']}".lower()
        score = 0
        matched = 0
        for kw in keywords:
            if kw in searchable:
                matched += 1
                # ファイル名の完全一致に高スコア
                if kw in entry["name"].lower():
                    score += 3
                # フォルダ名マッチ
                elif kw in entry["folder"].lower():
                    score += 1
                else:
                    score += 0.5

        if matched == 0:
            continue

        # 全キーワードがマッチしたら大幅ボーナス
        if matched == len(keywords):
            score += 5

        scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [entry for _, entry in scored[:20]]

    # JSON出力（LLM向け）
    output = {
        "query": query,
        "total_matches": len(scored),
        "showing": len(results),
        "results": results,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return results


def show_stats(config):
    """インデックスの統計情報を表示。"""
    index = load_index(config)

    print("=== Audio Index Stats ===")
    print(f"Version: {index['version']}")
    print(f"Created: {index['created_at']}")
    print(f"Updated: {index['updated_at']}")
    print(f"Total files: {len(index['files'])}")
    print()

    for lib in index["libraries"]:
        print(f"  {lib['name']}: {lib['file_count']} files ({lib['root']})")

    # 拡張子別集計
    ext_counts = {}
    for f in index["files"]:
        ext_counts[f["ext"]] = ext_counts.get(f["ext"], 0) + 1
    print("\nBy extension:")
    for ext, count in sorted(ext_counts.items()):
        print(f"  {ext}: {count}")

    # フォルダ別集計（トップレベル）
    folder_counts = {}
    for f in index["files"]:
        top_folder = f["folder"].split("/")[0] if f["folder"] else "(root)"
        folder_counts[top_folder] = folder_counts.get(top_folder, 0) + 1
    print("\nTop-level folders:")
    for folder, count in sorted(folder_counts.items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f"  {folder}: {count}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    config = load_config()
    cmd = sys.argv[1]

    if cmd == "build":
        build_index(config)
    elif cmd == "update":
        update_index(config)
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: asset-index.py search <query>", file=sys.stderr)
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        search_index(config, query)
    elif cmd == "stats":
        show_stats(config)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
