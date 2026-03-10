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

PROGRAM_NAME = "build_phase1_candidates_v1"
PROGRAM_VERSION = "2.0.0"
DEFAULT_MANIFEST_NAME = "phase1_candidates_manifest.json"
DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")
DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"


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

    default_input_dir = repo_root / "02_Windows"
    default_output_dir = repo_root / "03_Candidates"
    default_schema_path = repo_root / "11_Schemas" / "phase1_candidate_threads.schema.json"

    parser = argparse.ArgumentParser(
        description=(
            "Generate Phase 1 candidate-thread JSON outputs by calling the OpenAI Responses API "
            "with the rendered window request markdown files and a strict JSON schema."
        )
    )
    parser.add_argument("--window", type=int, required=True, help="Starting window number.")
    parser.add_argument(
        "--windows",
        type=int,
        default=1,
        help="Number of consecutive windows to process from --window onward. Defaults to 1.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=default_input_dir,
        help=f"Input windows directory. Defaults to {default_input_dir}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help=f"Output candidates directory. Defaults to {default_output_dir}",
    )
    parser.add_argument(
        "--schema-path",
        type=Path,
        default=default_schema_path,
        help=f"Structured output schema path. Defaults to {default_schema_path}",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"OpenAI model name. Defaults to {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--api-base",
        default=os.environ.get("OPENAI_API_BASE", DEFAULT_API_BASE),
        help=f"Responses API base URL. Defaults to {DEFAULT_API_BASE}",
    )
    parser.add_argument(
        "--api-key-env",
        default=DEFAULT_API_KEY_ENV,
        help=f"Environment variable containing the API key. Defaults to {DEFAULT_API_KEY_ENV}",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="HTTP timeout in seconds. Defaults to 300.",
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
        help="Show what would be executed without calling the API or writing files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing outputs.",
    )
    return parser.parse_args()



def validate_args(args: argparse.Namespace) -> tuple[int, int]:
    if args.window < 1:
        raise ValueError("--window must be >= 1")
    if args.windows < 1:
        raise ValueError("--windows must be >= 1")
    if args.timeout_seconds < 1:
        raise ValueError("--timeout-seconds must be >= 1")
    return args.window, args.window + args.windows - 1



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
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    safe_write_text(path, text, force=force, dry_run=dry_run)



def list_request_files(input_dir: Path) -> list[Path]:
    return sorted(input_dir.glob("window_*_weeks_*_request.md"))



def extract_window_number(path: Path) -> int:
    name = path.name
    prefix = "window_"
    if not name.startswith(prefix):
        raise ValueError(f"Unexpected request filename: {name}")
    number_text = name[len(prefix): len(prefix) + 3]
    if not number_text.isdigit():
        raise ValueError(f"Could not extract window number from filename: {name}")
    return int(number_text)



def filter_request_files(request_files: list[Path], start_window: int, end_window: int) -> list[Path]:
    selected: list[Path] = []
    for path in request_files:
        window_number = extract_window_number(path)
        if start_window <= window_number <= end_window:
            selected.append(path)
    return selected



def output_json_name_for_request(request_path: Path) -> str:
    suffix = "_request.md"
    if not request_path.name.endswith(suffix):
        raise ValueError(f"Unexpected request filename: {request_path.name}")
    base = request_path.name[: -len(suffix)]
    return f"{base}_candidate_threads.json"



def output_raw_name_for_request(request_path: Path) -> str:
    suffix = "_request.md"
    if not request_path.name.endswith(suffix):
        raise ValueError(f"Unexpected request filename: {request_path.name}")
    base = request_path.name[: -len(suffix)]
    return f"{base}_raw_response.json"



def parse_window_metadata_from_request(request_path: Path) -> dict[str, Any]:
    text = request_path.read_text(encoding="utf-8")
    marker = "{{WINDOW_PACKAGE_JSON}}"
    if marker in text:
        raise ValueError(f"Unrendered request template still contains placeholder in {request_path}")

    anchor = text.rfind('"schema_name": "phase1_window_package"')
    if anchor == -1:
        raise ValueError(f"Could not locate embedded window package JSON in {request_path}")

    start = text.rfind("{", 0, anchor)
    if start == -1:
        raise ValueError(f"Could not find JSON object start in {request_path}")

    json_text = text[start:].strip()
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Embedded window package JSON is invalid in {request_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Embedded window package is not a JSON object in {request_path}")

    window = payload.get("window")
    if not isinstance(window, dict):
        raise ValueError(f"Embedded window package missing 'window' object in {request_path}")

    required = ["window_id", "start_week", "end_week", "week_count", "week_numbers"]
    for key in required:
        if key not in window:
            raise ValueError(f"Embedded window package missing window.{key} in {request_path}")

    return {
        "window_id": window["window_id"],
        "start_week": window["start_week"],
        "end_week": window["end_week"],
        "week_count": window["week_count"],
        "week_numbers": window["week_numbers"],
    }



def load_request_text(request_path: Path) -> str:
    return request_path.read_text(encoding="utf-8")



def load_and_sanitize_schema(schema_path: Path) -> dict[str, Any]:
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Schema file is not a JSON object: {schema_path}")

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



def build_responses_payload(*, model: str, prompt_text: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": model,
        "input": prompt_text,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema.get("schema_name", "phase1_candidate_threads"),
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
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Responses API returned invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Responses API returned a non-object JSON payload")

    return payload



def extract_candidate_json(api_response: dict[str, Any]) -> dict[str, Any]:
    if api_response.get("status") not in (None, "completed"):
        raise RuntimeError(f"Responses API did not complete successfully: status={api_response.get('status')}")

    if "output_parsed" in api_response and isinstance(api_response["output_parsed"], dict):
        return api_response["output_parsed"]

    output_text = api_response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not parse output_text as JSON: {exc}") from exc
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
            joined = "\n".join(fragment for fragment in text_fragments if fragment.strip())
            try:
                parsed = json.loads(joined)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Could not parse collected response text as JSON: {exc}") from exc
            if isinstance(parsed, dict):
                return parsed

    raise RuntimeError("Could not extract structured candidate JSON from Responses API payload")



def validate_candidate_payload(payload: dict[str, Any], source_window: dict[str, Any], model: str) -> dict[str, Any]:
    required_top = [
        "schema_name",
        "schema_version",
        "package_type",
        "source_window",
        "build",
        "candidate_threads",
    ]
    for key in required_top:
        if key not in payload:
            raise ValueError(f"Candidate payload missing top-level key: {key}")

    if payload.get("schema_name") != "phase1_candidate_threads":
        raise ValueError("Candidate payload has unexpected schema_name")

    if not isinstance(payload.get("candidate_threads"), list):
        raise ValueError("Candidate payload candidate_threads must be a list")

    source = payload.get("source_window")
    if not isinstance(source, dict):
        raise ValueError("Candidate payload source_window must be an object")

    for key in ["window_id", "start_week", "end_week", "week_count", "week_numbers"]:
        if key not in source:
            raise ValueError(f"Candidate payload source_window missing key: {key}")

    build = payload.get("build")
    if not isinstance(build, dict):
        raise ValueError("Candidate payload build must be an object")

    build.setdefault("created_at", utc_now_iso())
    build.setdefault("created_by", PROGRAM_NAME)
    build["model"] = model
    build.setdefault("prompt_version", "1.0")

    payload["source_window"] = {
        "window_id": source_window["window_id"],
        "start_week": source_window["start_week"],
        "end_week": source_window["end_week"],
        "week_count": source_window["week_count"],
        "week_numbers": source_window["week_numbers"],
    }

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
    run_id = make_run_id()
    created_at = utc_now_iso()
    git_commit = try_git_commit(repo_root)

    logging.info("Program: %s %s", PROGRAM_NAME, PROGRAM_VERSION)
    logging.info("Repo root: %s", repo_root)
    logging.info("Input dir: %s", args.input_dir)
    logging.info("Output dir: %s", args.output_dir)
    logging.info("Schema path: %s", args.schema_path)
    logging.info("Model: %s", args.model)
    logging.info("API base: %s", args.api_base)
    logging.info(
        "Windows requested: start=%s windows=%s end=%s",
        start_window,
        args.windows,
        end_window,
    )
    logging.info("Mode: %s", "dry-run" if args.dry_run else "write")

    try:
        ensure_exists(args.input_dir, "Input directory")
        ensure_exists(args.schema_path, "Schema file")
        ensure_writable_dir(args.output_dir, dry_run=args.dry_run)

        schema = load_and_sanitize_schema(args.schema_path)

        api_key = ""
        if not args.dry_run:
            api_key = os.environ.get(args.api_key_env, "")
            if not api_key:
                raise EnvironmentError(f"API key environment variable is not set: {args.api_key_env}")

        request_files = list_request_files(args.input_dir)
        if not request_files:
            raise FileNotFoundError(f"No request markdown files found in {args.input_dir}")

        selected_requests = filter_request_files(request_files, start_window, end_window)
        if not selected_requests:
            raise FileNotFoundError(
                f"No request markdown files matched windows {start_window}-{end_window} in {args.input_dir}"
            )

        manifest_windows: list[dict[str, Any]] = []

        for request_path in selected_requests:
            window_number = extract_window_number(request_path)
            source_window = parse_window_metadata_from_request(request_path)
            prompt_text = load_request_text(request_path)

            output_json_path = args.output_dir / output_json_name_for_request(request_path)
            raw_response_path = args.output_dir / output_raw_name_for_request(request_path)

            logging.info(
                "Generating candidate output for window %03d covering weeks %02d-%02d",
                window_number,
                source_window["start_week"],
                source_window["end_week"],
            )

            if args.dry_run:
                logging.info("DRY RUN: would call Responses API for %s", request_path)
                logging.info("DRY RUN: would write %s", output_json_path)
                logging.info("DRY RUN: would write %s", raw_response_path)
            else:
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
                candidate_payload = extract_candidate_json(api_response)
                candidate_payload = validate_candidate_payload(candidate_payload, source_window, args.model)

                safe_write_json(raw_response_path, api_response, force=args.force, dry_run=False)
                safe_write_json(output_json_path, candidate_payload, force=args.force, dry_run=False)

            manifest_windows.append(
                {
                    "window_number": window_number,
                    "window_id": source_window["window_id"],
                    "start_week": source_window["start_week"],
                    "end_week": source_window["end_week"],
                    "week_numbers": source_window["week_numbers"],
                    "request_md_path": str(request_path),
                    "candidate_json_path": str(output_json_path),
                    "raw_response_path": str(raw_response_path),
                }
            )

        manifest: dict[str, Any] = {
            "schema_name": "phase1_candidates_manifest",
            "schema_version": "1.0",
            "program_name": PROGRAM_NAME,
            "program_version": PROGRAM_VERSION,
            "created_at": created_at,
            "run_id": run_id,
            "parameters": {
                "window": start_window,
                "windows": args.windows,
                "end_window": end_window,
                "input_dir": str(args.input_dir),
                "output_dir": str(args.output_dir),
                "schema_path": str(args.schema_path),
                "model": args.model,
                "api_base": args.api_base,
                "api_key_env": args.api_key_env,
                "timeout_seconds": args.timeout_seconds,
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

        logging.info("Done. Generated %s candidate file(s).", len(manifest_windows))
        if args.dry_run:
            logging.info("Dry run only: no API calls were made and no files were written.")

        return 0

    except Exception as exc:
        logging.exception("Build failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
