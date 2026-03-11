#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROGRAM_NAME = "build_weekly_thread_rewrite_v1"
PROGRAM_VERSION = "1.0.0"
DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")
DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"
DEFAULT_MANIFEST_NAME = "weekly_thread_rewrite_manifest.json"


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
        description="Generate weekly thread-conscious rewritten chapters via the OpenAI Responses API."
    )
    parser.add_argument("--week", type=int, required=True, help="Starting week number.")
    parser.add_argument("--weeks", type=int, default=1, help="Number of consecutive weeks to process.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=repo_root / "07_RewriteInputs",
        help="Directory containing weekly rewrite input JSON files.",
    )
    parser.add_argument(
        "--prompt-path",
        type=Path,
        default=repo_root / "12_Prompts" / "weekly_thread_rewrite_prompt_v1.md",
        help="Path to weekly thread rewrite prompt markdown.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / "08_RewrittenChapters",
        help="Directory for rewritten markdown chapters.",
    )
    parser.add_argument(
        "--raw-output-dir",
        type=Path,
        default=repo_root / "08_RewrittenChapters" / "_raw_responses",
        help="Directory for raw API responses.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model name.")
    parser.add_argument(
        "--api-base",
        default=os.environ.get("OPENAI_API_BASE", DEFAULT_API_BASE),
        help="Responses API base URL.",
    )
    parser.add_argument(
        "--api-key-env",
        default=DEFAULT_API_KEY_ENV,
        help="Environment variable containing the API key.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help="HTTP timeout in seconds.",
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
    if args.timeout_seconds < 1:
        raise ValueError("--timeout-seconds must be >= 1")
    return args.week, args.week + args.weeks - 1


def ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{description} does not exist: {path}")


def ensure_writable_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def safe_write_text(path: Path, content: str, force: bool, dry_run: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file without --force: {path}")
    if dry_run:
        logging.info("DRY RUN: would write %s", path)
        return
    path.write_text(content, encoding="utf-8")


def safe_write_json(path: Path, payload: dict[str, Any], force: bool, dry_run: bool) -> None:
    safe_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n", force=force, dry_run=dry_run)


def load_json_object(path: Path, description: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{description} is not a JSON object: {path}")
    return payload


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# Logging helper for debug path output
def log_debug_paths(*, week_number: int, rewrite_input: dict[str, Any], input_path: Path, output_path: Path, raw_path: Path) -> None:
    if not logging.getLogger().isEnabledFor(logging.DEBUG):
        return

    sources = rewrite_input.get("sources", {})
    week = rewrite_input.get("week", {})

    logging.debug("Week %02d input file: %s", week_number, input_path)
    logging.debug("Week %02d output markdown: %s", week_number, output_path)
    logging.debug("Week %02d raw response: %s", week_number, raw_path)
    logging.debug("Week %02d prior final chapter file: %s", week_number, sources.get("prior_final_chapter_file"))
    logging.debug("Week %02d weekly thread package file: %s", week_number, sources.get("weekly_thread_package_file"))
    logging.debug(
        "Week %02d optional supporting files: %s",
        week_number,
        sources.get("optional_supporting_material_files", {}),
    )
    logging.debug("Week %02d headline: %s", week_number, week.get("headline"))


def rewrite_input_path(input_dir: Path, week_number: int) -> Path:
    return input_dir / f"week_{week_number:02d}_rewrite_input.json"


def rewritten_output_path(output_dir: Path, week_number: int) -> Path:
    return output_dir / f"week_{week_number:02d}_rewritten.md"


def raw_output_path(raw_output_dir: Path, week_number: int) -> Path:
    return raw_output_dir / f"week_{week_number:02d}_rewrite_raw_response.json"


def render_prompt(prompt_template: str, rewrite_input: dict[str, Any]) -> str:
    rendered = prompt_template

    replacements = {
        "{{WEEKLY_THREAD_PACKAGE_JSON}}": json.dumps(
            rewrite_input.get("weekly_thread_package", {}), indent=2, ensure_ascii=False
        ),
        "{{PRIOR_FINAL_CHAPTER_TEXT}}": rewrite_input.get("prior_final_chapter_text", "") or "",
        "{{OPTIONAL_SUPPORTING_MATERIALS}}": json.dumps(
            rewrite_input.get("optional_supporting_materials", {}), indent=2, ensure_ascii=False
        ),
    }

    for marker, value in replacements.items():
        if marker not in rendered:
            raise ValueError(f"Prompt template missing placeholder {marker}")
        rendered = rendered.replace(marker, value)

    return rendered


def build_responses_payload(*, model: str, prompt_text: str) -> dict[str, Any]:
    return {
        "model": model,
        "input": prompt_text,
    }


def post_responses_request(*, api_base: str, api_key: str, payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    url = api_base.rstrip("/") + "/responses"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Responses API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Responses API connection error: {exc}") from exc

    try:
        response_payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Responses API returned invalid JSON: {exc}") from exc

    if not isinstance(response_payload, dict):
        raise RuntimeError("Responses API returned a non-object JSON payload")

    return response_payload


def extract_response_metadata(api_response: dict[str, Any]) -> dict[str, Any]:
    response_id = api_response.get("id") if isinstance(api_response.get("id"), str) else None
    actual_model = api_response.get("model") if isinstance(api_response.get("model"), str) else None
    return {
        "response_id": response_id,
        "actual_model": actual_model,
    }


def extract_output_text(api_response: dict[str, Any]) -> str:
    if api_response.get("status") not in (None, "completed"):
        raise RuntimeError(f"Responses API did not complete successfully: status={api_response.get('status')}")

    output_text = api_response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip() + ("\n" if not output_text.endswith("\n") else "")

    output = api_response.get("output")
    if isinstance(output, list):
        text_fragments: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for chunk in content:
                if not isinstance(chunk, dict):
                    continue
                if isinstance(chunk.get("text"), str):
                    text_fragments.append(chunk["text"])
                elif isinstance(chunk.get("output_text"), str):
                    text_fragments.append(chunk["output_text"])
                elif isinstance(chunk.get("content"), str):
                    text_fragments.append(chunk["content"])
        if text_fragments:
            joined = "\n".join(fragment for fragment in text_fragments if fragment.strip()).strip()
            if joined:
                return joined + "\n"

    raise RuntimeError("Could not extract rewritten chapter text from Responses API payload")


def validate_rewrite_input(rewrite_input: dict[str, Any], week_number: int, input_path: Path) -> None:
    scope = rewrite_input.get("scope")
    week = rewrite_input.get("week")
    weekly_thread_package = rewrite_input.get("weekly_thread_package")
    prior_final_chapter_text = rewrite_input.get("prior_final_chapter_text")

    if not isinstance(scope, dict):
        raise ValueError(f"Rewrite input scope must be an object: {input_path}")
    if not isinstance(week, dict):
        raise ValueError(f"Rewrite input week must be an object: {input_path}")
    if not isinstance(weekly_thread_package, dict):
        raise ValueError(f"Rewrite input weekly_thread_package must be an object: {input_path}")
    if not isinstance(prior_final_chapter_text, str) or not prior_final_chapter_text.strip():
        raise ValueError(f"Rewrite input prior_final_chapter_text must be non-empty: {input_path}")

    if scope.get("week_number") != week_number:
        raise ValueError(
            f"Week number mismatch in scope for {input_path}: expected {week_number}, got {scope.get('week_number')}"
        )
    if week.get("week_number") != week_number:
        raise ValueError(
            f"Week number mismatch in week block for {input_path}: expected {week_number}, got {week.get('week_number')}"
        )


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
    logging.info("Input dir: %s", args.input_dir)
    logging.info("Prompt path: %s", args.prompt_path)
    logging.info("Output dir: %s", args.output_dir)
    logging.info("Raw output dir: %s", args.raw_output_dir)
    logging.info("Model: %s", args.model)
    logging.info("API base: %s", args.api_base)
    logging.info("Weeks requested: start=%s weeks=%s end=%s", start_week, args.weeks, end_week)
    logging.info("Mode: %s", "dry-run" if args.dry_run else "write")

    try:
        ensure_exists(args.input_dir, "Rewrite input directory")
        ensure_exists(args.prompt_path, "Prompt file")
        ensure_writable_dir(args.output_dir, dry_run=args.dry_run)
        ensure_writable_dir(args.raw_output_dir, dry_run=args.dry_run)

        prompt_template = load_text(args.prompt_path)

        api_key = ""
        if not args.dry_run:
            api_key = os.environ.get(args.api_key_env, "")
            if not api_key:
                raise EnvironmentError(f"API key environment variable is not set: {args.api_key_env}")

        manifest_weeks: list[dict[str, Any]] = []

        for week_number in range(start_week, end_week + 1):
            input_path = rewrite_input_path(args.input_dir, week_number)
            ensure_exists(input_path, f"Rewrite input for Week {week_number}")

            rewrite_input = load_json_object(input_path, f"Rewrite input for Week {week_number}")
            validate_rewrite_input(rewrite_input, week_number, input_path)
            prompt_text = render_prompt(prompt_template, rewrite_input)

            output_path = rewritten_output_path(args.output_dir, week_number)
            raw_path = raw_output_path(args.raw_output_dir, week_number)

            log_debug_paths(
                week_number=week_number,
                rewrite_input=rewrite_input,
                input_path=input_path,
                output_path=output_path,
                raw_path=raw_path,
            )

            logging.info("Generating rewritten chapter for Week %02d", week_number)

            if args.dry_run:
                logging.info("DRY RUN: would call Responses API for %s", input_path)
                logging.info("DRY RUN: would write %s", output_path)
                logging.info("DRY RUN: would write %s", raw_path)
                logging.debug("Week %02d dry-run complete: prompt would be rendered and sent using model %s", week_number, args.model)
                manifest_weeks.append(
                    {
                        "week_number": week_number,
                        "input_path": str(input_path),
                        "output_path": str(output_path),
                        "raw_response_path": str(raw_path),
                        "requested_model": args.model,
                        "actual_model": None,
                        "response_id": None,
                    }
                )
                continue

            payload = build_responses_payload(model=args.model, prompt_text=prompt_text)
            api_response = post_responses_request(
                api_base=args.api_base,
                api_key=api_key,
                payload=payload,
                timeout_seconds=args.timeout_seconds,
            )
            response_meta = extract_response_metadata(api_response)
            rewritten_text = extract_output_text(api_response)

            if logging.getLogger().isEnabledFor(logging.DEBUG):
                preview = rewritten_text[:300].replace("\n", " ")
                logging.debug("Week %02d response_id: %s", week_number, response_meta["response_id"])
                logging.debug("Week %02d actual model: %s", week_number, response_meta["actual_model"])
                logging.debug("Week %02d rewritten preview: %s", week_number, preview)

            safe_write_json(raw_path, api_response, force=args.force, dry_run=False)
            safe_write_text(output_path, rewritten_text, force=args.force, dry_run=False)

            logging.debug("Week %02d write complete: markdown=%s raw=%s", week_number, output_path, raw_path)

            manifest_weeks.append(
                {
                    "week_number": week_number,
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "raw_response_path": str(raw_path),
                    "requested_model": args.model,
                    "actual_model": response_meta["actual_model"],
                    "response_id": response_meta["response_id"],
                }
            )

        manifest = {
            "schema_name": "weekly_thread_rewrite_manifest",
            "schema_version": "1.0",
            "program_name": PROGRAM_NAME,
            "program_version": PROGRAM_VERSION,
            "created_at": created_at,
            "run_id": run_id,
            "git_commit": git_commit,
            "parameters": {
                "week": start_week,
                "weeks": args.weeks,
                "end_week": end_week,
                "input_dir": str(args.input_dir),
                "prompt_path": str(args.prompt_path),
                "output_dir": str(args.output_dir),
                "raw_output_dir": str(args.raw_output_dir),
                "model": args.model,
                "api_base": args.api_base,
                "api_key_env": args.api_key_env,
                "timeout_seconds": args.timeout_seconds,
                "dry_run": args.dry_run,
                "force": args.force,
                "level": args.level,
            },
            "week_count": len(manifest_weeks),
            "weeks": manifest_weeks,
        }
        manifest_path = args.output_dir / DEFAULT_MANIFEST_NAME
        safe_write_json(manifest_path, manifest, force=args.force, dry_run=args.dry_run)

        logging.info("Done.")
        if args.dry_run:
            logging.info("Dry run only: no API calls were made and no files were written.")
        return 0

    except Exception as exc:
        logging.exception("Build failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
