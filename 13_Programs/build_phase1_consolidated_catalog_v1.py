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

PROGRAM_NAME = "build_phase1_consolidated_catalog_v1"
PROGRAM_VERSION = "1.0.0"
DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")
DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"
DEFAULT_OUTPUT_NAME = "phase1_consolidated_thread_catalog.json"
DEFAULT_RAW_OUTPUT_NAME = "phase1_consolidated_thread_catalog_raw_response.json"


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

    default_input_json = repo_root / "04_Catalog" / "phase1_consolidation_input.json"
    default_prompt_path = repo_root / "12_Prompts" / "phase1_consolidation_prompt_v1.md"
    default_schema_path = repo_root / "11_Schemas" / "phase1_consolidated_thread_catalog.schema.json"
    default_output_dir = repo_root / "04_Catalog"

    parser = argparse.ArgumentParser(
        description=(
            "Generate the Phase 1 consolidated thread catalog by calling the OpenAI Responses API "
            "with the consolidation input package, consolidation prompt, and strict JSON schema."
        )
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        default=default_input_json,
        help=f"Consolidation input package. Defaults to {default_input_json}",
    )
    parser.add_argument(
        "--prompt-path",
        type=Path,
        default=default_prompt_path,
        help=f"Consolidation prompt markdown file. Defaults to {default_prompt_path}",
    )
    parser.add_argument(
        "--schema-path",
        type=Path,
        default=default_schema_path,
        help=f"Structured output schema path. Defaults to {default_schema_path}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help=f"Output directory. Defaults to {default_output_dir}",
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
        default=600,
        help="HTTP timeout in seconds. Defaults to 600.",
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


def validate_args(args: argparse.Namespace) -> None:
    if args.timeout_seconds < 1:
        raise ValueError("--timeout-seconds must be >= 1")


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


def load_prompt_text(prompt_path: Path) -> str:
    return prompt_path.read_text(encoding="utf-8")


def render_prompt(prompt_template: str, consolidation_input: dict[str, Any]) -> str:
    marker = "{{CONSOLIDATION_INPUT_JSON}}"
    if marker not in prompt_template:
        raise ValueError(f"Prompt template missing placeholder {marker}")
    rendered_json = json.dumps(consolidation_input, indent=2, ensure_ascii=False)
    return prompt_template.replace(marker, rendered_json)


def build_responses_payload(*, model: str, prompt_text: str, schema: dict[str, Any]) -> dict[str, Any]:
    schema_name = schema.get("schema_name", "phase1_consolidated_thread_catalog")
    if not isinstance(schema_name, str):
        schema_name = "phase1_consolidated_thread_catalog"

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


def validate_catalog_payload(
    payload: dict[str, Any],
    *,
    consolidation_input: dict[str, Any],
    model: str,
    created_at: str,
    run_id: str,
    git_commit: str | None,
) -> dict[str, Any]:
    required_top = [
        "schema_name",
        "schema_version",
        "package_type",
        "scope",
        "build",
        "source_windows",
        "canonical_threads",
        "rejected_or_folded_candidates",
        "consolidation_notes",
    ]
    for key in required_top:
        if key not in payload:
            raise ValueError(f"Catalog payload missing top-level key: {key}")

    if payload.get("schema_name") != "phase1_consolidated_thread_catalog":
        raise ValueError("Catalog payload has unexpected schema_name")

    scope = consolidation_input.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("Consolidation input missing scope object")

    source_manifest = consolidation_input.get("source_manifest")
    if not isinstance(source_manifest, dict):
        raise ValueError("Consolidation input missing source_manifest object")

    source_files = source_manifest.get("files", [])
    if not isinstance(source_files, list):
        raise ValueError("Consolidation input source_manifest.files must be a list")

    payload["scope"] = {
        "project": scope.get("project"),
        "period_label": scope.get("period_label"),
        "start_week": scope.get("start_week"),
        "end_week": scope.get("end_week"),
        "window_count": scope.get("window_count"),
        "window_ids": scope.get("window_ids"),
    }

    payload["source_windows"] = []
    windows = consolidation_input.get("windows", [])
    if not isinstance(windows, list):
        raise ValueError("Consolidation input windows must be a list")

    file_map: dict[str, str] = {}
    for item in source_files:
        if isinstance(item, dict):
            window_id = item.get("window_id")
            path = item.get("path")
            if isinstance(window_id, str) and isinstance(path, str):
                file_map[window_id] = path

    for window in windows:
        if not isinstance(window, dict):
            continue
        window_id = window.get("window_id")
        if not isinstance(window_id, str):
            continue
        payload["source_windows"].append(
            {
                "window_id": window_id,
                "start_week": window.get("start_week"),
                "end_week": window.get("end_week"),
                "candidate_file": file_map.get(window_id, ""),
                "candidate_count": window.get("candidate_count", 0),
            }
        )

    build = payload.get("build")
    if not isinstance(build, dict):
        raise ValueError("Catalog payload build must be an object")

    build["created_at"] = created_at
    build["created_by"] = PROGRAM_NAME
    build["model"] = model
    build["run_id"] = run_id
    build.setdefault("prompt_version", "1.0")
    build["git_commit"] = git_commit

    if not isinstance(payload.get("canonical_threads"), list):
        raise ValueError("Catalog payload canonical_threads must be a list")
    if not isinstance(payload.get("rejected_or_folded_candidates"), list):
        raise ValueError("Catalog payload rejected_or_folded_candidates must be a list")
    if not isinstance(payload.get("consolidation_notes"), list):
        raise ValueError("Catalog payload consolidation_notes must be a list")

    return payload


def main() -> int:
    args = parse_args()
    configure_logging(args.level)

    try:
        validate_args(args)
    except Exception as exc:
        logging.error(str(exc))
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    created_at = utc_now_iso()
    run_id = make_run_id()
    git_commit = try_git_commit(repo_root)

    logging.info("Program: %s %s", PROGRAM_NAME, PROGRAM_VERSION)
    logging.info("Input JSON: %s", args.input_json)
    logging.info("Prompt path: %s", args.prompt_path)
    logging.info("Schema path: %s", args.schema_path)
    logging.info("Output dir: %s", args.output_dir)
    logging.info("Model: %s", args.model)
    logging.info("API base: %s", args.api_base)
    logging.info("Mode: %s", "dry-run" if args.dry_run else "write")

    try:
        ensure_exists(args.input_json, "Consolidation input JSON")
        ensure_exists(args.prompt_path, "Prompt file")
        ensure_exists(args.schema_path, "Schema file")
        ensure_writable_dir(args.output_dir, dry_run=args.dry_run)

        consolidation_input = load_json_object(args.input_json, "Consolidation input JSON")
        prompt_template = load_prompt_text(args.prompt_path)
        schema = load_and_sanitize_schema(args.schema_path)
        prompt_text = render_prompt(prompt_template, consolidation_input)

        output_json_path = args.output_dir / DEFAULT_OUTPUT_NAME
        raw_output_path = args.output_dir / DEFAULT_RAW_OUTPUT_NAME

        if args.dry_run:
            logging.info("DRY RUN: would call Responses API")
            logging.info("DRY RUN: would write %s", output_json_path)
            logging.info("DRY RUN: would write %s", raw_output_path)
            return 0

        api_key = os.environ.get(args.api_key_env, "")
        if not api_key:
            raise EnvironmentError(f"API key environment variable is not set: {args.api_key_env}")

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
        catalog_payload = extract_structured_json(api_response)
        catalog_payload = validate_catalog_payload(
            catalog_payload,
            consolidation_input=consolidation_input,
            model=args.model,
            created_at=created_at,
            run_id=run_id,
            git_commit=git_commit,
        )

        safe_write_json(raw_output_path, api_response, force=args.force, dry_run=False)
        safe_write_json(output_json_path, catalog_payload, force=args.force, dry_run=False)

        logging.info("Done. Consolidated catalog written to %s", output_json_path)
        return 0

    except Exception as exc:
        logging.exception("Build failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())