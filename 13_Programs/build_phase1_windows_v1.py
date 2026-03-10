#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROGRAM_NAME = "build_phase1_windows_v1"
PROGRAM_VERSION = "1.0.0"
DEFAULT_MANIFEST_NAME = "phase1_windows_manifest.json"


@dataclass(frozen=True)
class WindowSpec:
    window_id: str
    start_week: int
    end_week: int
    week_numbers: list[int]


def configure_logging(level: str) -> None:
    numeric = logging.DEBUG if level.lower() == "debug" else logging.INFO
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_mtime_utc(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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

    default_source_root = repo_root.parent / "Step 3" / "Weeks"
    default_output_dir = repo_root / "02_Windows"
    default_prompt_template = repo_root / "12_Prompts" / "phase1_discovery_prompt_v1.md"

    parser = argparse.ArgumentParser(
        description="Build overlapping Phase 1 discovery-window JSON packages and prompt-ready markdown request files."
    )
    parser.add_argument("--week", type=int, required=True, help="Starting week number.")
    parser.add_argument(
        "--weeks",
        type=int,
        default=1,
        help="Number of weeks to include from --week onward. Defaults to 1.",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=10,
        help="Discovery window size. Defaults to 10.",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=4,
        help="Discovery window stride. Defaults to 4.",
    )
    parser.add_argument(
        "--dormancy-window",
        type=int,
        default=5,
        help="Dormancy window metadata value. Defaults to 5.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=default_source_root,
        help=f"Step 3 Weeks root. Defaults to {default_source_root}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help=f"Output directory. Defaults to {default_output_dir}",
    )
    parser.add_argument(
        "--prompt-template",
        type=Path,
        default=default_prompt_template,
        help=f"Prompt template markdown file. Defaults to {default_prompt_template}",
    )
    parser.add_argument(
        "--level",
        choices=["info", "debug"],
        default="info",
        help="Log level. Defaults to info.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without writing files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing outputs.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> tuple[int, int]:
    if args.week < 1:
        raise ValueError("--week must be >= 1")
    if args.weeks < 1:
        raise ValueError("--weeks must be >= 1")
    if args.window_size < 1:
        raise ValueError("--window-size must be >= 1")
    if args.stride < 1:
        raise ValueError("--stride must be >= 1")
    if args.dormancy_window < 1:
        raise ValueError("--dormancy-window must be >= 1")

    start_week = args.week
    end_week = args.week + args.weeks - 1
    return start_week, end_week


def source_file_for_week(source_root: Path, week_number: int) -> Path:
    return source_root / f"Week {week_number}" / f"development_allocator_week{week_number}.json"


def load_week_payload(source_root: Path, week_number: int) -> dict[str, Any]:
    path = source_file_for_week(source_root, week_number)
    if not path.exists():
        raise FileNotFoundError(f"Missing source file for Week {week_number}: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Expected top-level JSON object in {path}")

    return payload


def build_window_starts(start_week: int, end_week: int, window_size: int, stride: int) -> list[int]:
    if end_week < start_week:
        return []

    if (end_week - start_week + 1) <= window_size:
        return [start_week]

    starts = [start_week]
    while starts[-1] + window_size - 1 < end_week:
        next_start = starts[-1] + stride
        if next_start > end_week:
            break
        starts.append(next_start)

    final_start = max(start_week, end_week - window_size + 1)
    if starts[-1] + window_size - 1 < end_week and final_start not in starts:
        starts.append(final_start)

    starts = sorted(set(starts))
    return starts


def build_windows(start_week: int, end_week: int, window_size: int, stride: int) -> list[WindowSpec]:
    starts = build_window_starts(start_week, end_week, window_size, stride)
    windows: list[WindowSpec] = []

    for idx, start in enumerate(starts, start=1):
        end = min(start + window_size - 1, end_week)
        week_numbers = list(range(start, end + 1))
        windows.append(
            WindowSpec(
                window_id=f"window_{idx:03d}",
                start_week=start,
                end_week=end,
                week_numbers=week_numbers,
            )
        )

    return windows


def ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{description} does not exist: {path}")


def ensure_writable_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def file_metadata(path: Path, week_number: int) -> dict[str, Any]:
    return {
        "week_number": week_number,
        "path": str(path),
        "filename": path.name,
        "sha256": sha256_file(path),
        "mtime_utc": iso_mtime_utc(path),
        "size_bytes": path.stat().st_size,
    }


def build_window_package(
    window: WindowSpec,
    *,
    source_root: Path,
    dormancy_window: int,
    build_created_at: str,
    run_id: str,
    git_commit: str | None,
) -> dict[str, Any]:
    weeks: list[dict[str, Any]] = []
    source_files: list[dict[str, Any]] = []

    for week_number in window.week_numbers:
        src_path = source_file_for_week(source_root, week_number)
        payload = load_week_payload(source_root, week_number)
        meta = file_metadata(src_path, week_number)

        source_files.append(meta)
        weeks.append(
            {
                "week_number": week_number,
                "source_file": {
                    "path": meta["path"],
                    "filename": meta["filename"],
                    "sha256": meta["sha256"],
                    "mtime_utc": meta["mtime_utc"],
                    "size_bytes": meta["size_bytes"],
                },
                "allocator_payload": payload,
            }
        )

    package: dict[str, Any] = {
        "schema_name": "phase1_window_package",
        "schema_version": "1.0",
        "package_type": "thread_discovery_window",
        "window": {
            "window_id": window.window_id,
            "start_week": window.start_week,
            "end_week": window.end_week,
            "week_count": len(window.week_numbers),
            "window_size": len(window.week_numbers),
            "stride": None,  # filled by caller below
            "dormancy_window": dormancy_window,
            "week_numbers": window.week_numbers,
        },
        "build": {
            "created_at": build_created_at,
            "created_by": PROGRAM_NAME,
            "program_name": PROGRAM_NAME,
            "program_version": PROGRAM_VERSION,
            "run_id": run_id,
        },
        "source_manifest": {
            "source_root": str(source_root),
            "file_count": len(source_files),
            "files": source_files,
        },
        "weeks": weeks,
    }

    if git_commit:
        package["build"]["git_commit"] = git_commit

    return package


def render_request_markdown(prompt_template: str, window_package: dict[str, Any]) -> str:
    pretty_json = json.dumps(window_package, indent=2, ensure_ascii=False)
    return prompt_template.replace("{{WINDOW_PACKAGE_JSON}}", pretty_json)


def safe_write_text(path: Path, content: str, force: bool, dry_run: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file without --force: {path}")
    if dry_run:
        logging.info("DRY RUN: would write %s", path)
        return
    path.write_text(content, encoding="utf-8")


def safe_write_json(path: Path, payload: dict[str, Any], force: bool, dry_run: bool) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    safe_write_text(path, text, force=force, dry_run=dry_run)


def main() -> int:
    args = parse_args()
    configure_logging(args.level)

    try:
        start_week, end_week = validate_args(args)
    except Exception as exc:
        logging.error(str(exc))
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    run_id = make_run_id()
    created_at = utc_now_iso()
    git_commit = try_git_commit(repo_root)

    logging.info("Program: %s %s", PROGRAM_NAME, PROGRAM_VERSION)
    logging.info("Repo root: %s", repo_root)
    logging.info("Source root: %s", args.source_root)
    logging.info("Output dir: %s", args.output_dir)
    logging.info("Prompt template: %s", args.prompt_template)
    logging.info(
        "Weeks requested: start=%s weeks=%s end=%s window_size=%s stride=%s dormancy_window=%s",
        start_week,
        args.weeks,
        end_week,
        args.window_size,
        args.stride,
        args.dormancy_window,
    )
    logging.info("Mode: %s", "dry-run" if args.dry_run else "write")

    try:
        ensure_exists(args.source_root, "Source root")
        ensure_exists(args.prompt_template, "Prompt template")
        ensure_writable_dir(args.output_dir, dry_run=args.dry_run)

        for week_number in range(start_week, end_week + 1):
            path = source_file_for_week(args.source_root, week_number)
            ensure_exists(path, f"Week {week_number} source file")

        windows = build_windows(start_week, end_week, args.window_size, args.stride)
        if not windows:
            raise ValueError("No windows were generated.")

        prompt_template = args.prompt_template.read_text(encoding="utf-8")

        manifest_windows: list[dict[str, Any]] = []

        for window in windows:
            logging.info(
                "Building %s covering weeks %02d-%02d",
                window.window_id,
                window.start_week,
                window.end_week,
            )

            package = build_window_package(
                window,
                source_root=args.source_root,
                dormancy_window=args.dormancy_window,
                build_created_at=created_at,
                run_id=run_id,
                git_commit=git_commit,
            )
            package["window"]["stride"] = args.stride
            package["window"]["window_size"] = args.window_size

            json_name = f"{window.window_id}_weeks_{window.start_week:02d}_{window.end_week:02d}.json"
            request_name = f"{window.window_id}_weeks_{window.start_week:02d}_{window.end_week:02d}_request.md"
            json_path = args.output_dir / json_name
            request_path = args.output_dir / request_name

            request_md = render_request_markdown(prompt_template, package)

            safe_write_json(json_path, package, force=args.force, dry_run=args.dry_run)
            safe_write_text(request_path, request_md, force=args.force, dry_run=args.dry_run)

            manifest_windows.append(
                {
                    "window_id": window.window_id,
                    "start_week": window.start_week,
                    "end_week": window.end_week,
                    "week_numbers": window.week_numbers,
                    "json_path": str(json_path),
                    "request_md_path": str(request_path),
                }
            )

        manifest = {
            "schema_name": "phase1_windows_manifest",
            "schema_version": "1.0",
            "program_name": PROGRAM_NAME,
            "program_version": PROGRAM_VERSION,
            "created_at": created_at,
            "run_id": run_id,
            "parameters": {
                "week": start_week,
                "weeks": args.weeks,
                "end_week": end_week,
                "window_size": args.window_size,
                "stride": args.stride,
                "dormancy_window": args.dormancy_window,
                "source_root": str(args.source_root),
                "output_dir": str(args.output_dir),
                "prompt_template": str(args.prompt_template),
                "dry_run": args.dry_run,
                "force": args.force,
                "level": args.level,
            },
            "window_count": len(manifest_windows),
            "windows": manifest_windows,
        }
        if git_commit:
            manifest["git_commit"] = git_commit

        manifest_path = args.output_dir / DEFAULT_MANIFEST_NAME
        safe_write_json(manifest_path, manifest, force=args.force, dry_run=args.dry_run)

        logging.info("Done. Built %s window package(s).", len(manifest_windows))
        if args.dry_run:
            logging.info("Dry run only: no files were written.")

        return 0

    except Exception as exc:
        logging.exception("Build failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())