#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROGRAM_NAME = "build_phase1_consolidation_input_v1"
PROGRAM_VERSION = "1.0.0"
DEFAULT_OUTPUT_NAME = "phase1_consolidation_input.json"


def configure_logging(level: str) -> None:
    numeric = logging.DEBUG if level.lower() == "debug" else logging.INFO
    logging.basicConfig(level=numeric, format="%(asctime)s [%(levelname)s] %(message)s")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def try_git_commit(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    default_input_dir = repo_root / "03_Candidates"
    default_output_dir = repo_root / "04_Catalog"

    parser = argparse.ArgumentParser(
        description="Build a single consolidation input package from Phase 1 candidate window files."
    )
    parser.add_argument("--window", type=int, required=True, help="Starting window number.")
    parser.add_argument("--windows", type=int, default=1, help="Number of consecutive windows to include.")
    parser.add_argument("--input-dir", type=Path, default=default_input_dir, help=f"Defaults to {default_input_dir}")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir, help=f"Defaults to {default_output_dir}")
    parser.add_argument("--level", choices=["info", "debug"], default="info")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> tuple[int, int]:
    if args.window < 1:
        raise ValueError("--window must be >= 1")
    if args.windows < 1:
        raise ValueError("--windows must be >= 1")
    return args.window, args.window + args.windows - 1


def ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{description} does not exist: {path}")


def ensure_writable_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def safe_write_json(path: Path, payload: dict[str, Any], force: bool, dry_run: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file without --force: {path}")
    if dry_run:
        logging.info("DRY RUN: would write %s", path)
        return
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def extract_window_number(path: Path) -> int:
    name = path.name
    prefix = "window_"
    if not name.startswith(prefix):
        raise ValueError(f"Unexpected candidate filename: {name}")
    number_text = name[len(prefix): len(prefix) + 3]
    if not number_text.isdigit():
        raise ValueError(f"Could not extract window number from filename: {name}")
    return int(number_text)


def list_candidate_files(input_dir: Path) -> list[Path]:
    return sorted(input_dir.glob("window_*_candidate_threads.json"))


def filter_candidate_files(candidate_files: list[Path], start_window: int, end_window: int) -> list[Path]:
    selected: list[Path] = []
    for path in candidate_files:
        number = extract_window_number(path)
        if start_window <= number <= end_window:
            selected.append(path)
    return selected


def load_candidate_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Candidate file is not a JSON object: {path}")
    return payload


def main() -> int:
    args = parse_args()
    configure_logging(args.level)

    try:
        start_window, end_window = validate_args(args)
    except Exception as exc:
        logging.error(str(exc))
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    created_at = utc_now_iso()
    run_id = make_run_id()
    git_commit = try_git_commit(repo_root)

    logging.info("Program: %s %s", PROGRAM_NAME, PROGRAM_VERSION)
    logging.info("Input dir: %s", args.input_dir)
    logging.info("Output dir: %s", args.output_dir)
    logging.info("Windows requested: start=%s windows=%s end=%s", start_window, args.windows, end_window)

    try:
        ensure_exists(args.input_dir, "Input directory")
        ensure_writable_dir(args.output_dir, dry_run=args.dry_run)

        candidate_files = list_candidate_files(args.input_dir)
        if not candidate_files:
            raise FileNotFoundError(f"No candidate files found in {args.input_dir}")

        selected = filter_candidate_files(candidate_files, start_window, end_window)
        if not selected:
            raise FileNotFoundError(f"No candidate files matched windows {start_window}-{end_window}")

        windows: list[dict[str, Any]] = []
        source_files: list[dict[str, Any]] = []
        all_window_ids: list[str] = []
        all_weeks: list[int] = []

        for path in selected:
            payload = load_candidate_payload(path)
            source_window = payload.get("source_window")
            if not isinstance(source_window, dict):
                raise ValueError(f"Missing source_window in {path}")

            window_id = source_window["window_id"]
            start_week = source_window["start_week"]
            end_week = source_window["end_week"]
            week_count = source_window["week_count"]
            week_numbers = source_window["week_numbers"]
            candidate_count = len(payload.get("candidate_threads", []))

            all_window_ids.append(window_id)
            all_weeks.extend(week_numbers)

            windows.append(
                {
                    "window_id": window_id,
                    "start_week": start_week,
                    "end_week": end_week,
                    "week_count": week_count,
                    "week_numbers": week_numbers,
                    "candidate_count": candidate_count,
                    "candidate_payload": payload,
                }
            )

            source_files.append(
                {
                    "window_id": window_id,
                    "path": str(path),
                    "filename": path.name,
                }
            )

        package: dict[str, Any] = {
            "schema_name": "phase1_consolidation_input",
            "schema_version": "1.0",
            "package_type": "thread_catalog_consolidation_input",
            "scope": {
                "project": "Trump Diary",
                "period_label": "Year 1",
                "start_week": min(all_weeks),
                "end_week": max(all_weeks),
                "window_count": len(windows),
                "window_ids": all_window_ids,
            },
            "build": {
                "created_at": created_at,
                "created_by": PROGRAM_NAME,
                "program_name": PROGRAM_NAME,
                "program_version": PROGRAM_VERSION,
                "run_id": run_id,
                "git_commit": git_commit,
            },
            "source_manifest": {
                "input_dir": str(args.input_dir),
                "file_count": len(source_files),
                "files": source_files,
            },
            "windows": windows,
        }

        output_path = args.output_dir / DEFAULT_OUTPUT_NAME
        safe_write_json(output_path, package, force=args.force, dry_run=args.dry_run)

        logging.info("Done. Consolidation input built for %s window(s).", len(windows))
        return 0

    except Exception as exc:
        logging.exception("Build failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())