#!/usr/bin/env python3
"""diagnostic_diff.py — Compare two build diagnostic metadata JSON files.

Bounty #172: Helps reviewers understand what changed between PR submissions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def color(text: str, color_name: str) -> str:
    """Colorize text for TTY output."""
    codes = {"red": 31, "green": 32, "yellow": 33, "cyan": 36, "bold": 1}
    c = codes.get(color_name, 0)
    return f"\033[{c}m{text}\033[0m" if sys.stdout.isatty() else text


def load_metadata(path_str: str) -> dict[str, Any]:
    """Load and validate diagnostic metadata JSON file."""
    path = Path(path_str)
    if not path.exists():
        print(f"Error: File not found: {path_str}", file=sys.stderr)
        sys.exit(2)
        
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON in {path_str} (line {exc.lineno}, col {exc.colno}): {exc.msg}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"Error: Could not read {path_str}: {exc}", file=sys.stderr)
        sys.exit(2)
        
    if not isinstance(data, dict):
        print(f"Error: {path_str} root must be a JSON object", file=sys.stderr)
        sys.exit(2)
        
    if "modules" in data and not isinstance(data["modules"], list):
        print(f"Error: {path_str} 'modules' field must be a list", file=sys.stderr)
        sys.exit(2)
        
    return data


def normalize_modules(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract and normalize modules from metadata into a name-indexed dict."""
    normalized = {}
    for m in data.get("modules", []):
        if not isinstance(m, dict) or "name" not in m:
            continue
        name = str(m["name"])
        
        # Guard against duplicate module names
        if name in normalized:
            continue
            
        # Support fallback keys for command/artifact if format changes
        cmd = m.get("command") or m.get("commands") or m.get("cmd") or ""
        if isinstance(cmd, list):
            cmd = " ".join(str(x) for x in cmd)
            
        art = m.get("artifact") or m.get("artifacts") or m.get("artifact_name") or ""
        
        normalized[name] = {
            "name": name,
            "status": str(m.get("status", "UNKNOWN")),
            "elapsed_seconds": m.get("elapsed_seconds") or m.get("duration_seconds") or 0.0,
            "command": str(cmd),
            "artifact": str(art)
        }
    return normalized


def compute_diff(old_mods: dict[str, dict[str, Any]], new_mods: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compute structural diff between old and new normalized modules."""
    old_names = set(old_mods.keys())
    new_names = set(new_mods.keys())
    
    added_names = sorted(new_names - old_names)
    removed_names = sorted(old_names - new_names)
    common_names = sorted(old_names & new_names)
    
    added_modules = []
    for name in added_names:
        m = new_mods[name]
        added_modules.append({
            "name": name,
            "status": m["status"],
            "artifact": m["artifact"]
        })
        
    removed_modules = []
    for name in removed_names:
        m = old_mods[name]
        removed_modules.append({
            "name": name,
            "status": m["status"],
            "artifact": m["artifact"]
        })
        
    changed_statuses = []
    duration_deltas = []
    changed_commands = []
    changed_artifacts = []
    
    for name in common_names:
        o = old_mods[name]
        n = new_mods[name]
        
        if o["status"] != n["status"]:
            changed_statuses.append({
                "name": name,
                "before": o["status"],
                "after": n["status"]
            })
            
        delta = n["elapsed_seconds"] - o["elapsed_seconds"]
        if abs(delta) >= 0.001:  # report precision down to 1ms
            duration_deltas.append({
                "name": name,
                "before_seconds": round(o["elapsed_seconds"], 3),
                "after_seconds": round(n["elapsed_seconds"], 3),
                "delta_seconds": round(delta, 3)
            })
            
        if o["command"] != n["command"]:
            changed_commands.append({
                "name": name,
                "before": o["command"],
                "after": n["command"]
            })
            
        if o["artifact"] != n["artifact"]:
            changed_artifacts.append({
                "name": name,
                "before": o["artifact"],
                "after": n["artifact"]
            })
            
    return {
        "added_modules": added_modules,
        "removed_modules": removed_modules,
        "changed_statuses": changed_statuses,
        "duration_deltas": duration_deltas,
        "changed_commands": changed_commands,
        "changed_artifacts": changed_artifacts
    }


def print_human_report(diff: dict[str, Any], old_meta: dict[str, Any], new_meta: dict[str, Any]) -> None:
    """Print human-readable colored report of the diff."""
    print(color(f"Diagnostic Diff: {old_meta.get('commit', 'old')} -> {new_meta.get('commit', 'new')}", "bold"))
    print("=" * 60)
    
    has_changes = False
    
    if diff["added_modules"]:
        has_changes = True
        print(color("\n[+] Added Modules:", "green"))
        for m in diff["added_modules"]:
            art_str = f" (artifact: {m['artifact']})" if m["artifact"] else ""
            print(f"  ✓ {m['name']} - status: {m['status']}{art_str}")
            
    if diff["removed_modules"]:
        has_changes = True
        print(color("\n[-] Removed Modules:", "red"))
        for m in diff["removed_modules"]:
            print(f"  ✗ {m['name']} - was status: {m['status']}")
            
    if diff["changed_statuses"]:
        has_changes = True
        print(color("\n[~] Status Changes:", "yellow"))
        for m in diff["changed_statuses"]:
            stat_str = f"{m['before']} -> {m['after']}"
            if m["after"] == "PASS":
                stat_str = color(stat_str, "green")
            elif m["after"] == "FAIL":
                stat_str = color(stat_str, "red")
            print(f"  ~ {m['name']}: {stat_str}")
            
    if diff["duration_deltas"]:
        has_changes = True
        print(color("\n[~] Duration Deltas:", "cyan"))
        for m in diff["duration_deltas"]:
            icon = "🐌" if m["delta_seconds"] > 0 else "⚡"
            print(f"  {icon} {m['name']}: {m['before_seconds']}s -> {m['after_seconds']}s ({m['delta_seconds']:+.3f}s)")
            
    if diff["changed_commands"]:
        has_changes = True
        print(color("\n[~] Command Changes:", "bold"))
        for m in diff["changed_commands"]:
            print(f"  ~ {m['name']}:")
            print(f"    before: {m['before'] or '(none)'}")
            print(f"    after:  {m['after'] or '(none)'}")
            
    if diff["changed_artifacts"]:
        has_changes = True
        print(color("\n[~] Artifact Path Changes:", "bold"))
        for m in diff["changed_artifacts"]:
            print(f"  ~ {m['name']}:")
            print(f"    before: {m['before'] or '(none)'}")
            print(f"    after:  {m['after'] or '(none)'}")
            
    if not has_changes:
        print(color("\nNo diagnostic metadata changes found.", "green"))
    print()


def main(argv: list[str] | None = None) -> int:
    """Main execution entry point."""
    if argv is None:
        argv = sys.argv[1:]
        
    parser = argparse.ArgumentParser(description="Compare two build diagnostic metadata JSON files.")
    parser.add_argument("before", help="Path to older diagnostic JSON file")
    parser.add_argument("after", help="Path to newer diagnostic JSON file")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON diff")
    
    args = parser.parse_args(argv)
    
    old_meta = load_metadata(args.before)
    new_meta = load_metadata(args.after)
    
    old_mods = normalize_modules(old_meta)
    new_mods = normalize_modules(new_meta)
    
    diff = compute_diff(old_mods, new_mods)
    
    if args.json:
        print(json.dumps(diff, indent=2))
    else:
        print_human_report(diff, old_meta, new_meta)
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
