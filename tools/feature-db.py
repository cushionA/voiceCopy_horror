#!/usr/bin/env python3
"""
Feature Log Database Manager
SQLite-based feature tracking for the game make pipeline.
Usage:
  python feature-db.py init                          # Initialize database
  python feature-db.py add <name> --tests <files> --impl <files> [--category system|content] [--section id] [--depends dep1 dep2]
  python feature-db.py update <name> --status <status> [--test-passed N] [--test-failed N]
  python feature-db.py get <name>                    # Get single feature
  python feature-db.py list [--status <status>] [--section <id>]  # List features
  python feature-db.py assets [--status pending|placed]  # List assets
  python feature-db.py bind <asset_id>               # Mark asset as placed
  python feature-db.py summary                       # Overall summary
"""
import sqlite3
import json
import sys
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'feature-log.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def _migrate_features_table(conn):
    """Add new columns to existing features table if they don't exist."""
    cursor = conn.execute("PRAGMA table_info(features)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    migrations = [
        ("category", "TEXT CHECK(category IN ('system', 'content'))"),
        ("section_id", "TEXT"),
        ("dependencies", "TEXT"),
    ]
    for col_name, col_def in migrations:
        if col_name not in existing_columns:
            conn.execute(f"ALTER TABLE features ADD COLUMN {col_name} {col_def}")
    conn.commit()

def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            status TEXT NOT NULL DEFAULT 'in_progress' CHECK(status IN ('in_progress', 'complete', 'failed')),
            category TEXT CHECK(category IN ('system', 'content')),
            section_id TEXT,
            dependencies TEXT,
            tests_passed INTEGER NOT NULL DEFAULT 0,
            tests_failed INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS feature_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL CHECK(file_type IN ('test', 'implementation')),
            FOREIGN KEY (feature_id) REFERENCES features(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pending_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT UNIQUE NOT NULL,
            feature_id INTEGER NOT NULL,
            asset_type TEXT NOT NULL,
            description TEXT NOT NULL,
            format TEXT,
            priority TEXT DEFAULT 'medium' CHECK(priority IN ('high', 'medium', 'low')),
            expected_path TEXT,
            target_gameobject TEXT,
            target_component TEXT,
            target_property TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'placed')),
            placed_at TEXT,
            FOREIGN KEY (feature_id) REFERENCES features(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    _migrate_features_table(conn)
    conn.close()
    print("Database initialized at", DB_PATH)

def add_feature(name, tests=None, impl=None, assets=None, category=None, section_id=None, dependencies=None):
    conn = get_connection()
    try:
        deps_json = json.dumps(dependencies) if dependencies else None
        conn.execute(
            "INSERT INTO features (name, category, section_id, dependencies) VALUES (?, ?, ?, ?)",
            (name, category, section_id, deps_json)
        )
        feature_id = conn.execute("SELECT id FROM features WHERE name=?", (name,)).fetchone()['id']

        if tests:
            for t in tests:
                conn.execute("INSERT INTO feature_files (feature_id, file_path, file_type) VALUES (?, ?, 'test')", (feature_id, t))
        if impl:
            for i in impl:
                conn.execute("INSERT INTO feature_files (feature_id, file_path, file_type) VALUES (?, ?, 'implementation')", (feature_id, i))

        conn.commit()
        print(f"Added feature: {name} (id={feature_id})")
    except sqlite3.IntegrityError:
        print(f"Error: Feature '{name}' already exists", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

def update_feature(name, status=None, tests_passed=None, tests_failed=None):
    conn = get_connection()
    updates = ["updated_at = datetime('now')"]
    params = []

    if status:
        updates.append("status = ?")
        params.append(status)
    if tests_passed is not None:
        updates.append("tests_passed = ?")
        params.append(int(tests_passed))
    if tests_failed is not None:
        updates.append("tests_failed = ?")
        params.append(int(tests_failed))

    params.append(name)
    result = conn.execute(f"UPDATE features SET {', '.join(updates)} WHERE name = ?", params)
    conn.commit()

    if result.rowcount == 0:
        print(f"Error: Feature '{name}' not found", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Updated feature: {name}")
    conn.close()

def get_feature(name):
    conn = get_connection()
    feature = conn.execute("SELECT * FROM features WHERE name=?", (name,)).fetchone()
    if not feature:
        print(f"Error: Feature '{name}' not found", file=sys.stderr)
        sys.exit(1)

    files = conn.execute("SELECT file_path, file_type FROM feature_files WHERE feature_id=?", (feature['id'],)).fetchall()
    assets = conn.execute("SELECT * FROM pending_assets WHERE feature_id=?", (feature['id'],)).fetchall()

    deps_raw = feature['dependencies']
    deps = json.loads(deps_raw) if deps_raw else []
    result = {
        "name": feature['name'],
        "status": feature['status'],
        "category": feature['category'],
        "section_id": feature['section_id'],
        "dependencies": deps,
        "created_at": feature['created_at'],
        "updated_at": feature['updated_at'],
        "tests_passed": feature['tests_passed'],
        "tests_failed": feature['tests_failed'],
        "tests": [f['file_path'] for f in files if f['file_type'] == 'test'],
        "implementation": [f['file_path'] for f in files if f['file_type'] == 'implementation'],
        "pending_assets": [dict(a) for a in assets]
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    conn.close()

def list_features(status=None, section=None):
    conn = get_connection()
    query = "SELECT * FROM features WHERE 1=1"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    if section:
        query += " AND section_id=?"
        params.append(section)
    query += " ORDER BY created_at DESC"
    features = conn.execute(query, params).fetchall()

    if not features:
        print("No features found.")
        conn.close()
        return

    print(f"{'Name':<30} {'Status':<15} {'Category':<10} {'Section':<12} {'Tests':>12} {'Created':<20}")
    print("-" * 99)
    for f in features:
        tests_str = f"{f['tests_passed']}P/{f['tests_failed']}F"
        cat = f['category'] or '-'
        sec = f['section_id'] or '-'
        print(f"{f['name']:<30} {f['status']:<15} {cat:<10} {sec:<12} {tests_str:>12} {f['created_at']:<20}")
    conn.close()

def list_assets(status=None):
    conn = get_connection()
    query = """
        SELECT pa.*, f.name as feature_name
        FROM pending_assets pa
        JOIN features f ON pa.feature_id = f.id
    """
    params = []
    if status:
        query += " WHERE pa.status = ?"
        params.append(status)
    query += " ORDER BY pa.priority DESC, pa.asset_id"

    assets = conn.execute(query, params).fetchall()

    if not assets:
        print("No assets found.")
        conn.close()
        return

    print(f"{'ID':<8} {'Type':<12} {'Status':<10} {'Priority':<10} {'Feature':<20} {'Description'}")
    print("-" * 90)
    for a in assets:
        print(f"{a['asset_id']:<8} {a['asset_type']:<12} {a['status']:<10} {a['priority']:<10} {a['feature_name']:<20} {a['description']}")

    pending = sum(1 for a in assets if a['status'] == 'pending')
    placed = sum(1 for a in assets if a['status'] == 'placed')
    print(f"\nTotal: {len(assets)} | Pending: {pending} | Placed: {placed}")
    conn.close()

def add_asset(asset_id, feature_name, asset_type, description, format_str=None, priority='medium',
              expected_path=None, target_go=None, target_comp=None, target_prop=None):
    conn = get_connection()
    feature = conn.execute("SELECT id FROM features WHERE name=?", (feature_name,)).fetchone()
    if not feature:
        print(f"Error: Feature '{feature_name}' not found", file=sys.stderr)
        sys.exit(1)

    try:
        conn.execute("""
            INSERT INTO pending_assets (asset_id, feature_id, asset_type, description, format, priority,
                                        expected_path, target_gameobject, target_component, target_property)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (asset_id, feature['id'], asset_type, description, format_str, priority,
              expected_path, target_go, target_comp, target_prop))
        conn.commit()
        print(f"Added asset: {asset_id}")
    except sqlite3.IntegrityError:
        print(f"Error: Asset '{asset_id}' already exists", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

def bind_asset(asset_id):
    conn = get_connection()
    result = conn.execute("""
        UPDATE pending_assets SET status='placed', placed_at=datetime('now') WHERE asset_id=?
    """, (asset_id,))
    conn.commit()
    if result.rowcount == 0:
        print(f"Error: Asset '{asset_id}' not found", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Bound asset: {asset_id}")
    conn.close()

def summary():
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as c FROM features").fetchone()['c']
    complete = conn.execute("SELECT COUNT(*) as c FROM features WHERE status='complete'").fetchone()['c']
    in_progress = conn.execute("SELECT COUNT(*) as c FROM features WHERE status='in_progress'").fetchone()['c']
    failed = conn.execute("SELECT COUNT(*) as c FROM features WHERE status='failed'").fetchone()['c']

    total_passed = conn.execute("SELECT COALESCE(SUM(tests_passed),0) as c FROM features").fetchone()['c']
    total_failed_tests = conn.execute("SELECT COALESCE(SUM(tests_failed),0) as c FROM features").fetchone()['c']

    pending_assets = conn.execute("SELECT COUNT(*) as c FROM pending_assets WHERE status='pending'").fetchone()['c']
    placed_assets = conn.execute("SELECT COUNT(*) as c FROM pending_assets WHERE status='placed'").fetchone()['c']

    # Category breakdown
    cat_rows = conn.execute("""
        SELECT category, status, COUNT(*) as c FROM features
        GROUP BY category, status
    """).fetchall()
    cat_stats = {}
    for row in cat_rows:
        cat = row['category'] or 'uncategorized'
        if cat not in cat_stats:
            cat_stats[cat] = {'complete': 0, 'in_progress': 0, 'failed': 0}
        cat_stats[cat][row['status']] = row['c']

    print("=== Pipeline Summary ===")
    print(f"Features: {total} total | {complete} complete | {in_progress} in progress | {failed} failed")
    if cat_stats:
        parts = []
        for cat in ('system', 'content', 'uncategorized'):
            if cat in cat_stats:
                s = cat_stats[cat]
                parts.append(f"  {cat}: {s['complete']} complete, {s['in_progress']} in progress, {s['failed']} failed")
        if parts:
            print("By category:")
            for p in parts:
                print(p)
    print(f"Tests: {total_passed} passed | {total_failed_tests} failed")
    print(f"Assets: {pending_assets} pending | {placed_assets} placed")
    conn.close()

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'init':
        init_db()
    elif cmd == 'add':
        if len(sys.argv) < 3:
            print("Usage: feature-db.py add <name> [--tests f1 f2] [--impl f1 f2] [--category system|content] [--section id] [--depends dep1 dep2]")
            sys.exit(1)
        name = sys.argv[2]
        tests, impl, depends = [], [], []
        category, section = None, None
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == '--tests':
                i += 1
                while i < len(sys.argv) and not sys.argv[i].startswith('--'):
                    tests.append(sys.argv[i])
                    i += 1
            elif sys.argv[i] == '--impl':
                i += 1
                while i < len(sys.argv) and not sys.argv[i].startswith('--'):
                    impl.append(sys.argv[i])
                    i += 1
            elif sys.argv[i] == '--category' and i+1 < len(sys.argv):
                category = sys.argv[i+1]; i += 2
            elif sys.argv[i] == '--section' and i+1 < len(sys.argv):
                section = sys.argv[i+1]; i += 2
            elif sys.argv[i] == '--depends':
                i += 1
                while i < len(sys.argv) and not sys.argv[i].startswith('--'):
                    depends.append(sys.argv[i])
                    i += 1
            else:
                i += 1
        add_feature(name, tests, impl, category=category, section_id=section, dependencies=depends if depends else None)
    elif cmd == 'update':
        if len(sys.argv) < 3:
            print("Usage: feature-db.py update <name> --status <status> [--test-passed N] [--test-failed N]")
            sys.exit(1)
        name = sys.argv[2]
        status, tp, tf = None, None, None
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == '--status' and i+1 < len(sys.argv):
                status = sys.argv[i+1]; i += 2
            elif sys.argv[i] == '--test-passed' and i+1 < len(sys.argv):
                tp = sys.argv[i+1]; i += 2
            elif sys.argv[i] == '--test-failed' and i+1 < len(sys.argv):
                tf = sys.argv[i+1]; i += 2
            else:
                i += 1
        update_feature(name, status, tp, tf)
    elif cmd == 'get':
        get_feature(sys.argv[2])
    elif cmd == 'list':
        status, section = None, None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == '--status' and i+1 < len(sys.argv):
                status = sys.argv[i+1]; i += 2
            elif sys.argv[i] == '--section' and i+1 < len(sys.argv):
                section = sys.argv[i+1]; i += 2
            else:
                i += 1
        list_features(status, section)
    elif cmd == 'assets':
        status = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == '--status' else None
        list_assets(status)
    elif cmd == 'add-asset':
        # feature-db.py add-asset <id> <feature> <type> <description> [--priority high] [--path x] [--target go comp prop]
        if len(sys.argv) < 6:
            print("Usage: feature-db.py add-asset <id> <feature> <type> <description> [options]")
            sys.exit(1)
        aid, feat, atype, desc = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
        priority, path, tgo, tcomp, tprop, fmt = 'medium', None, None, None, None, None
        i = 6
        while i < len(sys.argv):
            if sys.argv[i] == '--priority' and i+1 < len(sys.argv):
                priority = sys.argv[i+1]; i += 2
            elif sys.argv[i] == '--path' and i+1 < len(sys.argv):
                path = sys.argv[i+1]; i += 2
            elif sys.argv[i] == '--format' and i+1 < len(sys.argv):
                fmt = sys.argv[i+1]; i += 2
            elif sys.argv[i] == '--target' and i+3 < len(sys.argv):
                tgo, tcomp, tprop = sys.argv[i+1], sys.argv[i+2], sys.argv[i+3]; i += 4
            else:
                i += 1
        add_asset(aid, feat, atype, desc, fmt, priority, path, tgo, tcomp, tprop)
    elif cmd == 'bind':
        bind_asset(sys.argv[2])
    elif cmd == 'summary':
        summary()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

if __name__ == '__main__':
    main()
