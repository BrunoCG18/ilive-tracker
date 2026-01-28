"""
Ilive Tracker - Monitors Campus Living Darmstadt for apartment availability.
Sends an email notification when a room becomes free.

Usage:
    python main.py          # Run continuously with scheduled checks
    python main.py --once   # Run a single check and exit
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import schedule
from dotenv import load_dotenv

from scraper import get_apartments, STATUS_FREE, STATUS_OCCUPIED, STATUS_RESERVED
from notifier import notify_available

BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "state.json"


def load_config():
    """Load configuration from .env file."""
    load_dotenv(BASE_DIR / ".env")

    required = ["SMTP_HOST", "SMTP_PORT", "EMAIL_FROM", "EMAIL_PASSWORD", "EMAIL_TO"]
    config = {}
    missing = []

    for key in required:
        val = os.getenv(key)
        if not val:
            missing.append(key)
        config[key] = val

    config["CHECK_INTERVAL_MINUTES"] = int(os.getenv("CHECK_INTERVAL_MINUTES", "10"))

    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print(f"Copy .env.example to .env and fill in your values.")
        sys.exit(1)

    return config


def load_state():
    """Load previous apartment state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return None


def save_state(apartments):
    """Save current apartment state to file."""
    with open(STATE_FILE, "w") as f:
        json.dump(apartments, f, indent=2, ensure_ascii=False)


def find_newly_available(previous, current):
    """
    Compare previous and current states.
    Returns apartments that are no longer occupied/reserved (changed to free or unknown-with-rent).
    """
    if previous is None:
        return {}  # First run, don't alert

    newly_available = {}
    for apt_id, info in current.items():
        was_unavailable = True
        prev_info = previous.get(apt_id)
        if prev_info:
            was_unavailable = prev_info.get("status") in (STATUS_OCCUPIED, STATUS_RESERVED)

        is_available = info["status"] == STATUS_FREE
        # Also consider "unknown" status with rent info as potentially available
        if info["status"] == "unknown" and info.get("rent"):
            is_available = True

        if is_available and was_unavailable:
            newly_available[apt_id] = info

    return newly_available


def check_availability(config, first_run=False):
    """Perform a single availability check."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now}] Checking apartment availability...")

    try:
        apartments = get_apartments()
    except Exception as e:
        print(f"  ERROR fetching apartments: {e}")
        return

    if not apartments:
        print("  WARNING: No apartments found. Page structure may have changed.")
        return

    free_count = sum(1 for a in apartments.values() if a["status"] == STATUS_FREE)
    unknown_count = sum(1 for a in apartments.values() if a["status"] == "unknown")
    total = len(apartments)

    reserved_count = sum(1 for a in apartments.values() if a["status"] == STATUS_RESERVED)
    occupied_count = sum(1 for a in apartments.values() if a["status"] == STATUS_OCCUPIED)

    print(f"  Found {total} apartments: {free_count} free, {reserved_count} reserved, {occupied_count} occupied, {unknown_count} unknown")

    # Log free apartments
    free_apts = {k: v for k, v in apartments.items() if v["status"] == STATUS_FREE}
    if free_apts:
        print(f"  Free apartments:")
        for apt_id, info in sorted(free_apts.items()):
            size = info.get("size", "N/A")
            total = info.get("total", "N/A")
            print(f"    - {info['name']} | {info['type']} | {size} | Total: {total}")
    else:
        print("  No free apartments right now.")

    # Log reserved apartments
    reserved_apts = {k: v for k, v in apartments.items() if v["status"] == STATUS_RESERVED}
    if reserved_apts:
        print(f"  Reserved apartments:")
        for apt_id, info in sorted(reserved_apts.items()):
            size = info.get("size", "N/A")
            total = info.get("total", "N/A")
            print(f"    - {info['name']} | {info['type']} | {size} | Total: {total}")
    else:
        print("  No reserved apartments right now.")

    if first_run:
        print("  First run - saving initial state (no notification sent).")
        save_state(apartments)
        return

    previous = load_state()
    newly_available = find_newly_available(previous, apartments)

    if newly_available:
        print(f"  NEW AVAILABILITY DETECTED: {len(newly_available)} apartment(s)!")
        for apt_id, info in newly_available.items():
            print(f"    -> {info['name']} ({info['type']})")

        try:
            notify_available(config, newly_available)
        except Exception as e:
            print(f"  ERROR sending notification: {e}")
    else:
        print("  No new availability.")

    save_state(apartments)


def main():
    single_run = "--once" in sys.argv
    config = load_config()

    interval = config["CHECK_INTERVAL_MINUTES"]
    print("=" * 50)
    print("  Ilive Tracker - Campus Living Darmstadt")
    print("=" * 50)
    print(f"  Monitoring: https://www.campus-living-darmstadt.de/mieten")
    print(f"  Notifications: {config['EMAIL_TO']}")

    is_first_run = not STATE_FILE.exists()

    if single_run:
        print(f"  Mode: Single check")
        print("=" * 50)
        check_availability(config, first_run=is_first_run)
    else:
        print(f"  Interval: Every {interval} minutes")
        print(f"  Mode: Continuous (Ctrl+C to stop)")
        print("=" * 50)

        # Run immediately
        check_availability(config, first_run=is_first_run)

        # Schedule subsequent checks
        schedule.every(interval).minutes.do(check_availability, config)

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nStopped by user. Goodbye!")


if __name__ == "__main__":
    main()
