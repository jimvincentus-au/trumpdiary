#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

LOGIN_URL = "https://rdb.makebettinggreat.com"
REPORT_URL_TEMPLATE = "https://rdbwebapi.makebettinggreat.com/v1/export/all/{yyyymmdd}"
DEFAULT_OUTPUT_DIR = "/Volumes/T3BlueJVI2026/RDB Export"
DEFAULT_TIMEOUT_MS = 30000


@dataclass(frozen=True)
class Config:
    start: date
    end: date
    output_dir: Path
    dry_run: bool
    force: bool
    level: str
    timeout_ms: int
    headless: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Race D Base exports over a date range using a manual browser login."
    )
    parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end", help="End date in YYYY-MM-DD format")
    parser.add_argument("--days", type=int, help="Number of days to include, starting at --start")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save files into (default: {DEFAULT_OUTPUT_DIR!r})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded without downloading")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument(
        "--level",
        default="info",
        choices=["debug", "info"],
        help="Logging level (default: info)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_MS,
        help=f"Per-download timeout in milliseconds (default: {DEFAULT_TIMEOUT_MS})",
    )
    parser.add_argument("--headless", action="store_true", help="Run browser headless after login flow is stable")
    return parser.parse_args()


def parse_iso_date(value: str, flag_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid {flag_name} date {value!r}; expected YYYY-MM-DD") from exc


def build_config(args: argparse.Namespace) -> Config:
    if bool(args.end) == bool(args.days):
        raise SystemExit("Provide exactly one of --end or --days")

    start = parse_iso_date(args.start, "--start")

    if args.end:
        end = parse_iso_date(args.end, "--end")
        if end < start:
            raise SystemExit("--end must be on or after --start")
    else:
        if args.days <= 0:
            raise SystemExit("--days must be a positive integer")
        end = start + timedelta(days=args.days - 1)

    return Config(
        start=start,
        end=end,
        output_dir=Path(args.output_dir),
        dry_run=args.dry_run,
        force=args.force,
        level=args.level,
        timeout_ms=args.timeout,
        headless=args.headless,
    )


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=logging.DEBUG if level == "debug" else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def ensure_output_dir(path: Path) -> None:
    volume_root = Path("/Volumes/T3BlueJVI2026")
    if str(path).startswith(str(volume_root)) and not volume_root.exists():
        raise SystemExit(f"Required volume is not mounted: {volume_root}")
    path.mkdir(parents=True, exist_ok=True)


def target_path_for(day: date, output_dir: Path) -> Path:
    return output_dir / f"RDB_{day.strftime('%Y%m%d')}.xlsx"


def report_url_for(day: date) -> str:
    return REPORT_URL_TEMPLATE.format(yyyymmdd=day.strftime("%Y%m%d"))


def summarize_plan(cfg: Config) -> List[tuple[date, Path, str]]:
    plan = []
    for day in iter_dates(cfg.start, cfg.end):
        plan.append((day, target_path_for(day, cfg.output_dir), report_url_for(day)))
    return plan


def wait_for_manual_login(page) -> None:
    logging.info("Opening login page: %s", LOGIN_URL)
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    print("\nPlease log in in the opened browser window.")
    print("After login succeeds and you can see the site, return here and press Enter to continue.\n")
    input()


def install_debug_listeners(page) -> None:
    def on_download(download) -> None:
        logging.debug(
            "Download event fired: suggested_filename=%s url=%s",
            download.suggested_filename,
            download.url,
        )

    def on_response(response) -> None:
        if response.url.startswith("https://rdbwebapi.makebettinggreat.com/"):
            logging.debug("API response: %s %s", response.status, response.url)

    def on_request_failed(request) -> None:
        failure = request.failure
        failure_text = failure["errorText"] if isinstance(failure, dict) and "errorText" in failure else str(failure)
        logging.debug("Request failed: %s %s", request.url, failure_text)

    page.on("download", on_download)
    page.on("response", on_response)
    page.on("requestfailed", on_request_failed)


def log_session_state(page) -> None:
    try:
        logging.debug("Post-login page URL: %s", page.url)
    except Exception as exc:
        logging.debug("Unable to read current page URL: %s", exc)

    try:
        cookies = page.context.cookies()
        cookie_names = sorted({cookie.get("name", "") for cookie in cookies})
        logging.debug("Session cookies present: %s", ", ".join(cookie_names) if cookie_names else "<none>")
    except Exception as exc:
        logging.debug("Unable to inspect cookies: %s", exc)


def trigger_report_download(page, url: str) -> None:
    logging.debug("Triggering report download via browser navigation: %s", url)
    page.evaluate("(u) => { window.location.href = u; }", url)


def attempt_download(page, url: str, dest_path: Path, timeout_ms: int) -> str:
    logging.debug("Preparing download for URL: %s", url)
    with page.expect_download(timeout=timeout_ms) as download_info:
        trigger_report_download(page, url)
    download = download_info.value
    suggested = download.suggested_filename
    logging.debug("Download captured. Browser suggested filename: %s", suggested)
    download.save_as(str(dest_path))
    logging.debug("Saved download to: %s", dest_path)
    return suggested


def main() -> int:
    args = parse_args()
    cfg = build_config(args)
    configure_logging(cfg.level)
    ensure_output_dir(cfg.output_dir)

    plan = summarize_plan(cfg)
    logging.info("Planned dates: %s to %s (%d file(s))", cfg.start, cfg.end, len(plan))
    logging.info("Output directory: %s", cfg.output_dir)

    if cfg.dry_run:
        for day, dest_path, url in plan:
            status = "OVERWRITE" if dest_path.exists() and cfg.force else "SKIP_EXISTING" if dest_path.exists() else "DOWNLOAD"
            logging.info("%s | %s | %s", day.isoformat(), status, url)
        return 0

    to_download: List[tuple[date, Path, str]] = []
    for day, dest_path, url in plan:
        if dest_path.exists() and not cfg.force:
            logging.info("Skipping existing file: %s", dest_path)
            continue
        to_download.append((day, dest_path, url))

    if not to_download:
        logging.info("Nothing to do.")
        return 0

    downloaded = 0
    warnings = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        install_debug_listeners(page)

        try:
            wait_for_manual_login(page)
            log_session_state(page)

            for day, dest_path, url in to_download:
                logging.info("Downloading %s -> %s", day.isoformat(), dest_path)
                logging.debug("Report URL: %s", url)
                if dest_path.exists() and cfg.force:
                    logging.debug("Overwriting existing file: %s", dest_path)
                    dest_path.unlink()

                try:
                    suggested = attempt_download(page, url, dest_path, cfg.timeout_ms)
                    if not dest_path.exists():
                        raise FileNotFoundError(f"Download completed but file was not written: {dest_path}")
                    size = dest_path.stat().st_size
                    logging.info(
                        "Saved %s (%s bytes)%s",
                        dest_path.name,
                        size,
                        f" [source filename: {suggested}]" if suggested and suggested != dest_path.name else "",
                    )
                    downloaded += 1
                except PlaywrightTimeoutError:
                    logging.warning("No download detected for %s within timeout; continuing", day.isoformat())
                    warnings += 1
                except Exception:
                    logging.exception("Failed for %s", day.isoformat())
                    warnings += 1
        finally:
            context.close()
            browser.close()

    logging.info("Complete. Downloaded=%d Warning/Skipped=%d", downloaded, warnings)
    return 0


if __name__ == "__main__":
    sys.exit(main())