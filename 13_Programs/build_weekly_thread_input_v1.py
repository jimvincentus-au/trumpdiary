#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROGRAM_NAME = "build_weekly_thread_input_v1"
PROGRAM_VERSION = "1.0.0"
DEFAULT_OUTPUT_DIRNAME = "05_WeeklyThreadInputs"

WEEK_01_START_DATE = date(2025, 1, 20)
WEEK_01_END_DATE = date(2025, 1, 24)
WEEK_02_START_DATE = date(2025, 1, 25)


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
        description="Build one or more weekly thread input packages for the weekly thread-state LLM pass."
    )
    parser.add_argument("--week", type=int, required=True, help="Starting week number.")
    parser.add_argument("--weeks", type=int, default=1, help="Number of consecutive weeks to build.")
    parser.add_argument(
        "--catalog-file",
        type=Path,
        default=repo_root / "04_Catalog" / "phase1_consolidated_thread_catalog.json",
        help="Path to consolidated thread catalog JSON.",
    )
    parser.add_argument(
        "--step3-weeks-root",
        type=Path,
        default=repo_root.parent / "Step 3" / "Weeks",
        help="Path to Step 3 Weeks root.",
    )
    parser.add_argument(
        "--thread-packages-dir",
        type=Path,
        default=repo_root / "06_ThreadPackages",
        help="Directory where weekly thread packages will eventually live.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / DEFAULT_OUTPUT_DIRNAME,
        help="Directory for weekly thread input JSON files.",
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


def candidate_path(paths: list[Path]) -> str | None:
    for path in paths:
        if path.exists():
            return str(path)
    return None


def derive_week_date_range(week_number: int) -> tuple[str, str]:
    if week_number < 1:
        raise ValueError("week_number must be >= 1")
    if week_number == 1:
        return WEEK_01_START_DATE.isoformat(), WEEK_01_END_DATE.isoformat()

    start = WEEK_02_START_DATE + timedelta(days=(week_number - 2) * 7)
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def find_week_headline_and_summary(week_markdown_path: Path | None) -> tuple[str | None, str | None]:
    if week_markdown_path is None or not week_markdown_path.exists():
        return None, None

    text = week_markdown_path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None, None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    headline: str | None = None
    summary: str | None = None

    for line in lines:
        if line.startswith("#"):
            headline = line.lstrip("#").strip()
            break

    if headline is None and lines:
        first_line = lines[0]
        sentence_end = len(first_line)
        for marker in [". ", "? ", "! "]:
            idx = first_line.find(marker)
            if idx != -1:
                sentence_end = min(sentence_end, idx + 1)
        headline = first_line[:sentence_end].strip()[:160]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if paragraphs:
        first = paragraphs[0].replace("\n", " ").strip()
        if headline and first.startswith("#"):
            summary = paragraphs[1].replace("\n", " ").strip()[:500] if len(paragraphs) > 1 else None
        else:
            summary = first[:500]

    return headline, summary


def get_catalog_reference(catalog: dict[str, Any], catalog_file: Path) -> dict[str, Any]:
    build = catalog.get("build", {})
    return {
        "catalog_file": str(catalog_file),
        "catalog_run_id": build.get("run_id"),
        "catalog_schema_name": catalog.get("schema_name", ""),
        "catalog_schema_version": catalog.get("schema_version", ""),
    }


def get_catalog_threads(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    threads = catalog.get("canonical_threads", [])
    if not isinstance(threads, list):
        raise ValueError("Catalog canonical_threads must be a list")
    return threads


def build_input_package(
    *,
    repo_root: Path,
    catalog_file: Path,
    catalog: dict[str, Any],
    step3_weeks_root: Path,
    thread_packages_dir: Path,
    week_number: int,
    created_at: str,
    run_id: str,
    git_commit: str | None,
) -> dict[str, Any]:
    wd = week_dir(step3_weeks_root, week_number)
    ensure_exists(wd, f"Week directory for Week {week_number}")

    development_allocator_file = candidate_path(
        [
            wd / f"development_allocator_week{week_number}.json",
        ]
    )
    digest_file = candidate_path(
        [
            wd / f"digest_week{week_number}.md",
            wd / f"digest_week{week_number}.txt",
            wd / f"weekly_digest_week{week_number}.md",
            wd / f"weekly_digest_week{week_number}.txt",
            wd / f"week{week_number}_digest.md",
            wd / f"week{week_number}_digest.txt",
        ]
    )
    event_log_file = candidate_path(
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
    week_final_markdown = candidate_path(
        [
            wd / f"week{week_number}_final.md",
            wd / f"week{week_number}_final.txt",
            wd / f"week_{week_number}_final.md",
            wd / f"week_{week_number}_final.txt",
            wd / f"narrative_week{week_number}_final.md",
            wd / f"narrative_week{week_number}_final.txt",
            wd / f"weekly_chapter_week{week_number}.md",
            wd / f"weekly_chapter_week{week_number}.txt",
            wd / f"step5_narrative_week{week_number}_final.txt",
            wd / f"step5_narrative_week{week_number}_final.md",
        ]
    )

    prior_week_thread_package = None
    if week_number > 1:
        prior_candidate = thread_packages_dir / f"week_{week_number - 1:02d}_thread_package.json"
        if prior_candidate.exists():
            prior_week_thread_package = str(prior_candidate)

    headline, summary = find_week_headline_and_summary(Path(week_final_markdown) if week_final_markdown else None)

    start_date, end_date = derive_week_date_range(week_number)

    threads = get_catalog_threads(catalog)
    catalog_threads = []
    for thread in threads:
        catalog_threads.append(
            {
                "thread_id": thread.get("thread_id"),
                "canonical_name": thread.get("canonical_name"),
                "short_name": thread.get("short_name"),
                "description": thread.get("description"),
                "scope_level": thread.get("scope_level"),
                "parent_thread_id": thread.get("parent_thread_id"),
                "child_thread_ids": thread.get("child_thread_ids", []),
                "related_thread_ids": thread.get("related_thread_ids", []),
                "window_ids": thread.get("window_ids", []),
                "supporting_weeks": thread.get("supporting_weeks", []),
                "aliases": thread.get("aliases", []),
                "inclusion_notes": thread.get("inclusion_notes", []),
                "exclusion_notes": thread.get("exclusion_notes", []),
                "boundary_notes": thread.get("boundary_notes", []),
                "continuity_summary": thread.get("continuity_summary"),
            }
        )

    package = {
        "schema_name": "weekly_thread_input",
        "schema_version": "1.0",
        "package_type": "thread_state_input",
        "scope": {
            "project": "Trump Diary",
            "period_label": "Year 1",
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
        "catalog_reference": get_catalog_reference(catalog, catalog_file),
        "sources": {
            "week_final_markdown": week_final_markdown,
            "development_allocator_file": development_allocator_file,
            "digest_file": digest_file,
            "event_log_file": event_log_file,
            "prior_week_thread_package": prior_week_thread_package,
        },
        "week": {
            "week_number": week_number,
            "start_date": start_date,
            "end_date": end_date,
            "headline": headline,
            "summary": summary,
        },
        "catalog_threads": catalog_threads,
        "instructions": {
            "status_values": ["new", "continuing", "dormant", "reborn", "inactive"],
            "salience_values": ["high", "medium", "low"],
            "week_role_values": ["primary", "secondary", "background", "absent_but_relevant"],
            "rewrite_priority_values": ["lead", "major", "supporting", "mention_only", "omit"],
        },
    }

    return package


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
    logging.info("Catalog file: %s", args.catalog_file)
    logging.info("Step 3 Weeks root: %s", args.step3_weeks_root)
    logging.info("Thread packages dir: %s", args.thread_packages_dir)
    logging.info("Output dir: %s", args.output_dir)
    logging.info("Weeks requested: start=%s weeks=%s end=%s", start_week, args.weeks, end_week)

    try:
        ensure_exists(args.catalog_file, "Catalog file")
        ensure_exists(args.step3_weeks_root, "Step 3 Weeks root")
        ensure_writable_dir(args.output_dir, dry_run=args.dry_run)

        catalog = load_json_object(args.catalog_file, "Catalog file")

        for week_number in range(start_week, end_week + 1):
            logging.info("Building weekly thread input for Week %02d", week_number)
            package = build_input_package(
                repo_root=repo_root,
                catalog_file=args.catalog_file,
                catalog=catalog,
                step3_weeks_root=args.step3_weeks_root,
                thread_packages_dir=args.thread_packages_dir,
                week_number=week_number,
                created_at=created_at,
                run_id=run_id,
                git_commit=git_commit,
            )
            output_path = args.output_dir / f"week_{week_number:02d}_thread_input.json"
            safe_write_json(output_path, package, force=args.force, dry_run=args.dry_run)

        logging.info("Done.")
        return 0

    except Exception as exc:
        logging.exception("Build failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())