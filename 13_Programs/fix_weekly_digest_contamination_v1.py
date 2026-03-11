#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROGRAM_NAME = "fix_weekly_digest_contamination_v1"
PROGRAM_VERSION = "1.0.0"

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


def derive_week_date_range(week_number: int) -> tuple[str, str]:
    if week_number < 1:
        raise ValueError("week_number must be >= 1")
    if week_number == 1:
        return WEEK_01_START_DATE.isoformat(), WEEK_01_END_DATE.isoformat()

    start = WEEK_02_START_DATE + timedelta(days=(week_number - 2) * 7)
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    parser = argparse.ArgumentParser(
        description="One-off deterministic fixer for poisoned weekly thread inputs/packages. Repoints them to weekly_digest_final_weekN.md and patches digest-derived week metadata without rerunning the LLM."
    )
    parser.add_argument("--week", type=int, required=True, help="Starting week number.")
    parser.add_argument("--weeks", type=int, default=1, help="Number of consecutive weeks to patch.")
    parser.add_argument(
        "--step3-weeks-root",
        type=Path,
        default=repo_root.parent / "Step 3" / "Weeks",
        help="Path to Step 3 Weeks root.",
    )
    parser.add_argument(
        "--thread-input-dir",
        type=Path,
        default=repo_root / "05_WeeklyThreadInputs",
        help="Directory containing weekly thread input JSON files.",
    )
    parser.add_argument(
        "--thread-package-dir",
        type=Path,
        default=repo_root / "06_ThreadPackages",
        help="Directory containing weekly thread package JSON files.",
    )
    parser.add_argument("--level", choices=["info", "debug"], default="info")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Accepted for CLI symmetry; not needed for in-place patching.")
    return parser.parse_args()


def ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{description} does not exist: {path}")


def load_json_object(path: Path, description: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{description} is not a JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        logging.info("DRY RUN: would write %s", path)
        return
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def week_dir(step3_root: Path, week_number: int) -> Path:
    return step3_root / f"Week {week_number}"


def candidate_path(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def resolve_digest_path(step3_root: Path, week_number: int) -> Path:
    wd = week_dir(step3_root, week_number)
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
    if digest is None:
        raise FileNotFoundError(f"Could not find digest file for Week {week_number} under {wd}")
    return digest


def first_paragraph(text: str) -> str:
    paragraphs = [p.strip().replace("\n", " ") for p in text.split("\n\n") if p.strip()]
    return paragraphs[0] if paragraphs else ""


def headline_from_paragraph(paragraph: str) -> str:
    paragraph = paragraph.strip()
    if not paragraph:
        return ""
    match = re.search(r"(.+?[.!?])(?:\s|$)", paragraph)
    if match:
        return match.group(1).strip()
    return paragraph


def recursively_replace(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {k: recursively_replace(v, replacements) for k, v in value.items()}
    if isinstance(value, list):
        return [recursively_replace(v, replacements) for v in value]
    if isinstance(value, str):
        new_value = value
        for old, new in replacements.items():
            if old:
                new_value = new_value.replace(old, new)
        return new_value
    return value


def patch_thread_input(payload: dict[str, Any], *, week_number: int, digest_path: Path, digest_headline: str, digest_summary: str) -> tuple[dict[str, Any], dict[str, str]]:
    old_week_final = payload.get("sources", {}).get("week_final_markdown")
    old_digest = payload.get("sources", {}).get("digest_file")
    old_headline = payload.get("week", {}).get("headline")
    old_summary = payload.get("week", {}).get("summary")

    replacements = {
        str(old_week_final) if old_week_final else "": str(digest_path),
        str(Path(old_week_final).name) if old_week_final else "": digest_path.name,
        str(old_digest) if old_digest else "": str(digest_path),
        str(Path(old_digest).name) if old_digest else "": digest_path.name,
        old_headline or "": digest_headline,
        old_summary or "": digest_summary,
    }
    replacements = {k: v for k, v in replacements.items() if k}

    payload = recursively_replace(payload, replacements)

    sources = payload.setdefault("sources", {})
    sources["week_final_markdown"] = str(digest_path)
    sources["digest_file"] = str(digest_path)

    week = payload.setdefault("week", {})
    week["week_number"] = week_number
    start_date, end_date = derive_week_date_range(week_number)
    week["start_date"] = start_date
    week["end_date"] = end_date
    week["headline"] = digest_headline
    week["summary"] = digest_summary

    scope = payload.setdefault("scope", {})
    scope["week_number"] = week_number

    return payload, replacements


def patch_thread_package(payload: dict[str, Any], *, week_number: int, digest_path: Path, digest_headline: str, digest_summary: str, replacements: dict[str, str]) -> dict[str, Any]:
    payload = recursively_replace(payload, replacements)

    sources = payload.setdefault("sources", {})
    sources["week_final_markdown"] = str(digest_path)
    sources["digest_file"] = str(digest_path)

    week = payload.setdefault("week", {})
    week["week_number"] = week_number
    start_date, end_date = derive_week_date_range(week_number)
    week["start_date"] = start_date
    week["end_date"] = end_date
    week["headline"] = digest_headline
    week["summary"] = digest_summary

    scope = payload.setdefault("scope", {})
    scope["week_number"] = week_number

    build = payload.setdefault("build", {})
    build["created_by"] = PROGRAM_NAME
    build["program_name"] = PROGRAM_NAME
    build["program_version"] = PROGRAM_VERSION
    build["created_at"] = utc_now_iso()
    build["run_id"] = make_run_id()
    build["git_commit"] = build.get("git_commit")
    build["patch_note"] = "Deterministic digest-source contamination fix applied without LLM rerun."

    return payload


def main() -> int:
    args = parse_args()
    configure_logging(args.level)

    if args.week < 1 or args.weeks < 1:
        logging.error("--week and --weeks must be >= 1")
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    git_commit = try_git_commit(repo_root)
    logging.info("Program: %s %s", PROGRAM_NAME, PROGRAM_VERSION)
    logging.info("Step 3 Weeks root: %s", args.step3_weeks_root)
    logging.info("Thread input dir: %s", args.thread_input_dir)
    logging.info("Thread package dir: %s", args.thread_package_dir)
    logging.info("Weeks requested: start=%s weeks=%s end=%s", args.week, args.weeks, args.week + args.weeks - 1)
    logging.info("Mode: %s", "dry-run" if args.dry_run else "write")

    try:
        ensure_exists(args.step3_weeks_root, "Step 3 Weeks root")
        ensure_exists(args.thread_input_dir, "Thread input dir")
        ensure_exists(args.thread_package_dir, "Thread package dir")

        for week_number in range(args.week, args.week + args.weeks):
            digest_path = resolve_digest_path(args.step3_weeks_root, week_number)
            digest_text = digest_path.read_text(encoding="utf-8", errors="replace")
            digest_summary = first_paragraph(digest_text)
            if not digest_summary:
                raise ValueError(f"Digest appears empty for Week {week_number}: {digest_path}")
            digest_headline = headline_from_paragraph(digest_summary)

            input_path = args.thread_input_dir / f"week_{week_number:02d}_thread_input.json"
            package_path = args.thread_package_dir / f"week_{week_number:02d}_thread_package.json"
            ensure_exists(input_path, f"Week {week_number} thread input")
            ensure_exists(package_path, f"Week {week_number} thread package")

            thread_input = load_json_object(input_path, f"Week {week_number} thread input")
            thread_input, replacements = patch_thread_input(
                thread_input,
                week_number=week_number,
                digest_path=digest_path,
                digest_headline=digest_headline,
                digest_summary=digest_summary,
            )
            thread_input.setdefault("build", {})["git_commit"] = git_commit or thread_input.get("build", {}).get("git_commit")
            thread_input["build"]["created_by"] = PROGRAM_NAME
            thread_input["build"]["program_name"] = PROGRAM_NAME
            thread_input["build"]["program_version"] = PROGRAM_VERSION
            thread_input["build"]["created_at"] = utc_now_iso()
            thread_input["build"]["run_id"] = make_run_id()
            thread_input["build"]["patch_note"] = "Deterministic digest-source contamination fix applied without LLM rerun."

            thread_package = load_json_object(package_path, f"Week {week_number} thread package")
            thread_package = patch_thread_package(
                thread_package,
                week_number=week_number,
                digest_path=digest_path,
                digest_headline=digest_headline,
                digest_summary=digest_summary,
                replacements=replacements,
            )
            if git_commit:
                thread_package["build"]["git_commit"] = git_commit

            logging.info("Week %02d digest source: %s", week_number, digest_path)
            logging.info("Week %02d patched input: %s", week_number, input_path)
            logging.info("Week %02d patched package: %s", week_number, package_path)
            logging.debug("Week %02d headline => %s", week_number, digest_headline)
            logging.debug("Week %02d summary => %s", week_number, digest_summary)

            write_json(input_path, thread_input, args.dry_run)
            write_json(package_path, thread_package, args.dry_run)

        logging.info("Done.")
        return 0

    except Exception as exc:
        logging.exception("Patch failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
