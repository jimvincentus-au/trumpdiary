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


PROGRAM_NAME = "build_weekly_thread_package_v1"
PROGRAM_VERSION = "1.0.0"
DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")
DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"
DEFAULT_MANIFEST_NAME = "weekly_thread_package_manifest.json"


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
        description="Generate weekly thread packages by calling the OpenAI Responses API."
    )
    parser.add_argument("--week", type=int, required=True, help="Starting week number.")
    parser.add_argument("--weeks", type=int, default=1, help="Number of consecutive weeks to process.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=repo_root / "05_WeeklyThreadInputs",
        help="Directory containing weekly thread input JSON files.",
    )
    parser.add_argument(
        "--prompt-path",
        type=Path,
        default=repo_root / "12_Prompts" / "weekly_thread_package_prompt_v1.md",
        help="Path to weekly thread package prompt markdown.",
    )
    parser.add_argument(
        "--schema-path",
        type=Path,
        default=repo_root / "11_Schemas" / "weekly_thread_package.schema.json",
        help="Path to weekly thread package schema JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / "06_ThreadPackages",
        help="Directory for generated weekly thread packages.",
    )
    parser.add_argument(
        "--raw-output-dir",
        type=Path,
        default=repo_root / "06_ThreadPackages" / "_raw_responses",
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


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_and_sanitize_schema(schema_path: Path) -> dict[str, Any]:
    payload = load_json_object(schema_path, "Schema file")

    def _strip_unsupported_keywords(value: Any) -> Any:
        if isinstance(value, dict):
            cleaned: dict[str, Any] = {}
            for key, child in value.items():
                if key in {"$schema", "$id", "uniqueItems"}:
                    continue
                cleaned[key] = _strip_unsupported_keywords(child)
            return cleaned
        if isinstance(value, list):
            return [_strip_unsupported_keywords(item) for item in value]
        return value

    return _strip_unsupported_keywords(payload)


def render_prompt(prompt_template: str, weekly_input: dict[str, Any]) -> str:
    marker = "{{WEEKLY_THREAD_INPUT_JSON}}"
    if marker not in prompt_template:
        raise ValueError(f"Prompt template missing placeholder {marker}")
    rendered_json = json.dumps(weekly_input, indent=2, ensure_ascii=False)
    return prompt_template.replace(marker, rendered_json)


def build_responses_payload(*, model: str, prompt_text: str, schema: dict[str, Any]) -> dict[str, Any]:
    schema_name = schema.get("schema_name", "weekly_thread_package")
    if not isinstance(schema_name, str):
        schema_name = "weekly_thread_package"

    return {
        "model": model,
        "input": prompt_text,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
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


def extract_structured_json(api_response: dict[str, Any]) -> dict[str, Any]:
    if api_response.get("status") not in (None, "completed"):
        raise RuntimeError(f"Responses API did not complete successfully: status={api_response.get('status')}")

    output_parsed = api_response.get("output_parsed")
    if isinstance(output_parsed, dict):
        return output_parsed

    output_text = api_response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        parsed = json.loads(output_text)
        if isinstance(parsed, dict):
            return parsed

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
            parsed = json.loads("\n".join(fragment for fragment in text_fragments if fragment.strip()))
            if isinstance(parsed, dict):
                return parsed

    raise RuntimeError("Could not extract structured JSON from Responses API payload")


# Helper to extract actual response metadata
def extract_response_metadata(api_response: dict[str, Any]) -> dict[str, Any]:
    response_id = api_response.get("id") if isinstance(api_response.get("id"), str) else None
    actual_model = api_response.get("model") if isinstance(api_response.get("model"), str) else None
    return {
        "response_id": response_id,
        "actual_model": actual_model,
    }


def validate_weekly_package_payload(
    payload: dict[str, Any],
    *,
    weekly_input: dict[str, Any],
    model: str,
    created_at: str,
    run_id: str,
    git_commit: str | None,
    response_id: str | None,
    actual_model: str | None,
) -> dict[str, Any]:
    required_top = [
        "schema_name",
        "schema_version",
        "package_type",
        "scope",
        "build",
        "catalog_reference",
        "sources",
        "week",
        "thread_states",
        "week_summary_notes",
        "rewrite_guidance",
    ]
    for key in required_top:
        if key not in payload:
            raise ValueError(f"Weekly package payload missing top-level key: {key}")

    if payload.get("schema_name") != "weekly_thread_package":
        raise ValueError("Weekly package payload has unexpected schema_name")

    for list_key in ["thread_states", "week_summary_notes"]:
        if not isinstance(payload.get(list_key), list):
            raise ValueError(f"Weekly package payload {list_key} must be a list")

    if not isinstance(payload.get("rewrite_guidance"), dict):
        raise ValueError("Weekly package payload rewrite_guidance must be an object")

    payload["scope"] = dict(weekly_input.get("scope", {}))
    payload["catalog_reference"] = dict(weekly_input.get("catalog_reference", {}))
    payload["sources"] = dict(weekly_input.get("sources", {}))
    payload["week"] = dict(weekly_input.get("week", {}))

    build = payload.get("build")
    if not isinstance(build, dict):
        raise ValueError("Weekly package payload build must be an object")

    build["created_at"] = created_at
    build["created_by"] = PROGRAM_NAME
    build["model"] = actual_model or model
    build["run_id"] = run_id
    build.setdefault("prompt_version", "1.0")
    build["git_commit"] = git_commit
    build["response_id"] = response_id

    return payload


def week_input_path(input_dir: Path, week_number: int) -> Path:
    return input_dir / f"week_{week_number:02d}_thread_input.json"


def week_output_path(output_dir: Path, week_number: int) -> Path:
    return output_dir / f"week_{week_number:02d}_thread_package.json"


def raw_output_path(raw_output_dir: Path, week_number: int) -> Path:
    return raw_output_dir / f"week_{week_number:02d}_thread_package_raw_response.json"


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
    logging.info("Schema path: %s", args.schema_path)
    logging.info("Output dir: %s", args.output_dir)
    logging.info("Raw output dir: %s", args.raw_output_dir)
    logging.info("Model: %s", args.model)
    logging.info("API base: %s", args.api_base)
    logging.info("Weeks requested: start=%s weeks=%s end=%s", start_week, args.weeks, end_week)
    logging.info("Mode: %s", "dry-run" if args.dry_run else "write")

    try:
        ensure_exists(args.input_dir, "Input directory")
        ensure_exists(args.prompt_path, "Prompt file")
        ensure_exists(args.schema_path, "Schema file")
        ensure_writable_dir(args.output_dir, dry_run=args.dry_run)
        ensure_writable_dir(args.raw_output_dir, dry_run=args.dry_run)

        prompt_template = load_text(args.prompt_path)
        schema = load_and_sanitize_schema(args.schema_path)

        api_key = ""
        if not args.dry_run:
            api_key = os.environ.get(args.api_key_env, "")
            if not api_key:
                raise EnvironmentError(f"API key environment variable is not set: {args.api_key_env}")

        manifest_weeks: list[dict[str, Any]] = []

        for week_number in range(start_week, end_week + 1):
            input_path = week_input_path(args.input_dir, week_number)
            ensure_exists(input_path, f"Weekly thread input for Week {week_number}")

            weekly_input = load_json_object(input_path, f"Weekly thread input for Week {week_number}")
            input_scope = weekly_input.get("scope", {})
            input_week = weekly_input.get("week", {})
            if input_scope.get("week_number") != week_number:
                raise ValueError(
                    f"Week number mismatch in scope for {input_path}: expected {week_number}, got {input_scope.get('week_number')}"
                )
            if input_week.get("week_number") != week_number:
                raise ValueError(
                    f"Week number mismatch in week block for {input_path}: expected {week_number}, got {input_week.get('week_number')}"
                )

            sources = weekly_input.get("sources")
            if not isinstance(sources, dict):
                raise ValueError(f"Weekly thread input sources must be an object: {input_path}")

            if week_number > 1 and not sources.get("prior_week_thread_package"):
                prior_path = week_output_path(args.output_dir, week_number - 1)
                if prior_path.exists():
                    sources["prior_week_thread_package"] = str(prior_path)

            prompt_text = render_prompt(prompt_template, weekly_input)

            output_path = week_output_path(args.output_dir, week_number)
            raw_path = raw_output_path(args.raw_output_dir, week_number)

            logging.info("Generating weekly thread package for Week %02d", week_number)

            if args.dry_run:
                logging.info("DRY RUN: would call Responses API for %s", input_path)
                logging.info("DRY RUN: would write %s", output_path)
                logging.info("DRY RUN: would write %s", raw_path)
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

            payload = build_responses_payload(
                model=args.model,
                prompt_text=prompt_text,
                schema=schema,
            )
            api_response = post_responses_request(
                api_base=args.api_base,
                api_key=api_key,
                payload=payload,
                timeout_seconds=args.timeout_seconds,
            )
            response_meta = extract_response_metadata(api_response)
            weekly_package = extract_structured_json(api_response)
            weekly_package = validate_weekly_package_payload(
                weekly_package,
                weekly_input=weekly_input,
                model=args.model,
                created_at=created_at,
                run_id=run_id,
                git_commit=git_commit,
                response_id=response_meta["response_id"],
                actual_model=response_meta["actual_model"],
            )

            safe_write_json(raw_path, api_response, force=args.force, dry_run=False)
            safe_write_json(output_path, weekly_package, force=args.force, dry_run=False)

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
            "schema_name": "weekly_thread_package_manifest",
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
                "schema_path": str(args.schema_path),
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