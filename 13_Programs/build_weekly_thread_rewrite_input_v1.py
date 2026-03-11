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

PROGRAM_NAME = "build_weekly_thread_rewrite_input_v1"
PROGRAM_VERSION = "1.0.0"
DEFAULT_OUTPUT_DIRNAME = "07_RewriteInputs"


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

    parser = argparse.ArgumentParser(
        description="Build one or more weekly rewrite input packages for the thread-conscious rewrite pass."
    )
    parser.add_argument("--week", type=int, required=True, help="Starting week number.")
    parser.add_argument("--weeks", type=int, default=1, help="Number of consecutive weeks to build.")
    parser.add_argument(
        "--thread-packages-dir",
        type=Path,
        default=repo_root / "06_ThreadPackages",
        help="Directory containing weekly thread packages.",
    )
    parser.add_argument(
        "--step3-weeks-root",
        type=Path,
        default=repo_root.parent / "Step 3" / "Weeks",
        help="Path to Step 3 Weeks root.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / DEFAULT_OUTPUT_DIRNAME,
        help="Directory for rewrite input JSON files.",
    )
    parser.add_argument("--level", choices=["info", "debug"], default="info")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> tuple[int, int]:
    if args.week < 1:
        raise ValueError("--week must be >= 1")
    if args.weeks < 1:
        raise ValueError("--weeks must be >= 1")
    return args.week, args.week + args.weeks - 1


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


def load_json_object(path: Path, description: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{description} is not a JSON object: {path}")
    return payload


def week_dir(step3_root: Path, week_number: int) -> Path:
    return step3_root / f"Week {week_number}"


def candidate_path(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def read_text_or_none(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def thread_package_path(thread_packages_dir: Path, week_number: int) -> Path:
    return thread_packages_dir / f"week_{week_number:02d}_thread_package.json"


def find_prior_final_chapter_path(step3_weeks_root: Path, week_number: int) -> Path | None:
    wd = week_dir(step3_weeks_root, week_number)
    return candidate_path(
        [
            wd / f"weekly_digest_final_week{week_number}.md",
            wd / f"weekly_digest_final_week{week_number}.txt",
            wd / f"weekly_digest_week{week_number}.md",
            wd / f"weekly_digest_week{week_number}.txt",
            wd / f"digest_week{week_number}.md",
            wd / f"digest_week{week_number}.txt",
            wd / f"week{week_number}_digest.md",
            wd / f"week{week_number}_digest.txt",
        ]
    )


def find_optional_supporting_materials(step3_weeks_root: Path, week_number: int) -> dict[str, str]:
    wd = week_dir(step3_weeks_root, week_number)
    matches: dict[str, str] = {}

    development_allocator = candidate_path(
        [wd / f"development_allocator_week{week_number}.json"]
    )
    digest = candidate_path(
        [
            wd / f"weekly_digest_final_week{week_number}.md",
            wd / f"weekly_digest_final_week{week_number}.txt",
            wd / f"weekly_digest_week{week_number}.md",
            wd / f"weekly_digest_week{week_number}.txt",
            wd / f"digest_week{week_number}.md",
            wd / f"digest_week{week_number}.txt",
            wd / f"week{week_number}_digest.md",
            wd / f"week{week_number}_digest.txt",
        ]
    )
    event_log = candidate_path(
        [
            wd / f"master_event_log_week{week_number}.md",
            wd / f"master_event_log_week{week_number}.txt",
            wd / f"master_event_log_week_{week_number}.md",
            wd / f"master_event_log_week_{week_number}.txt",
            wd / f"event_log_week{week_number}.md",
            wd / f"event_log_week{week_number}.txt",
            wd / f"event_log_week_{week_number}.md",
            wd / f"event_log_week_{week_number}.txt",
            wd / f"week{week_number}_event_log.md",
            wd / f"week{week_number}_event_log.txt",
            wd / f"week_{week_number}_event_log.md",
            wd / f"week_{week_number}_event_log.txt",
        ]
    )

    if development_allocator:
        matches["development_allocator"] = str(development_allocator)
    if digest:
        matches["digest"] = str(digest)
    if event_log:
        matches["event_log"] = str(event_log)

    return matches


def build_rewrite_input_package(
    *,
    repo_root: Path,
    thread_packages_dir: Path,
    step3_weeks_root: Path,
    week_number: int,
    created_at: str,
    run_id: str,
    git_commit: str | None,
) -> dict[str, Any]:
    package_path = thread_package_path(thread_packages_dir, week_number)
    ensure_exists(package_path, f"Weekly thread package for Week {week_number}")

    thread_package = load_json_object(package_path, f"Weekly thread package for Week {week_number}")
    prior_final_chapter_path = find_prior_final_chapter_path(step3_weeks_root, week_number)
    prior_final_chapter_text = read_text_or_none(prior_final_chapter_path)

    if not prior_final_chapter_text:
        raise FileNotFoundError(
            f"Could not find prior final chapter text for Week {week_number} under {week_dir(step3_weeks_root, week_number)}"
        )

    optional_material_paths = find_optional_supporting_materials(step3_weeks_root, week_number)
    optional_supporting_materials: dict[str, str] = {}
    for key, path_str in optional_material_paths.items():
        content = read_text_or_none(Path(path_str))
        if content:
            optional_supporting_materials[key] = content

    week_block = thread_package.get("week", {})
    scope_block = thread_package.get("scope", {})

    if week_block.get("week_number") != week_number:
        raise ValueError(
            f"Week number mismatch in thread package week block for Week {week_number}: got {week_block.get('week_number')}"
        )
    if scope_block.get("week_number") != week_number:
        raise ValueError(
            f"Week number mismatch in thread package scope block for Week {week_number}: got {scope_block.get('week_number')}"
        )

    return {
        "schema_name": "weekly_thread_rewrite_input",
        "schema_version": "1.0",
        "package_type": "thread_conscious_rewrite_input",
        "scope": {
            "project": scope_block.get("project", "Trump Diary"),
            "period_label": scope_block.get("period_label", "Year 1"),
            "week_number": week_number,
        },
        "build": {
            "created_at": created_at,
            "created_by": PROGRAM_NAME,
            "program_name": PROGRAM_NAME,
            "program_version": PROGRAM_VERSION,
            "run_id": run_id,
            "git_commit": git_commit,
        },
        "week": {
            "week_number": week_number,
            "start_date": week_block.get("start_date"),
            "end_date": week_block.get("end_date"),
            "headline": week_block.get("headline"),
            "summary": week_block.get("summary"),
        },
        "sources": {
            "weekly_thread_package_file": str(package_path),
            "prior_final_chapter_file": str(prior_final_chapter_path) if prior_final_chapter_path else None,
            "optional_supporting_material_files": optional_material_paths,
        },
        "weekly_thread_package": thread_package,
        "prior_final_chapter_text": prior_final_chapter_text,
        "optional_supporting_materials": optional_supporting_materials,
    }


def main() -> int:
    args = parse_args()
    configure_logging(args.level)

    try:
        start_week, end_week = validate_args(args)
    except Exception as exc:
        logging.error(str(exc))
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    created_at = utc_now_iso()
    run_id = make_run_id()
    git_commit = try_git_commit(repo_root)

    logging.info("Program: %s %s", PROGRAM_NAME, PROGRAM_VERSION)
    logging.info("Thread packages dir: %s", args.thread_packages_dir)
    logging.info("Step 3 Weeks root: %s", args.step3_weeks_root)
    logging.info("Output dir: %s", args.output_dir)
    logging.info("Weeks requested: start=%s weeks=%s end=%s", start_week, args.weeks, end_week)

    try:
        ensure_exists(args.thread_packages_dir, "Thread packages directory")
        ensure_exists(args.step3_weeks_root, "Step 3 Weeks root")
        ensure_writable_dir(args.output_dir, dry_run=args.dry_run)

        for week_number in range(start_week, end_week + 1):
            logging.info("Building rewrite input for Week %02d", week_number)
            package = build_rewrite_input_package(
                repo_root=repo_root,
                thread_packages_dir=args.thread_packages_dir,
                step3_weeks_root=args.step3_weeks_root,
                week_number=week_number,
                created_at=created_at,
                run_id=run_id,
                git_commit=git_commit,
            )
            output_path = args.output_dir / f"week_{week_number:02d}_rewrite_input.json"
            safe_write_json(output_path, package, force=args.force, dry_run=args.dry_run)

        logging.info("Done.")
        return 0

    except Exception as exc:
        logging.exception("Build failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())