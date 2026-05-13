"""
Scheduler — Automatically backup devices at set intervals.

Uses APScheduler to run backups on a schedule:
  - Every N hours (e.g., every 6 hours)
  - Daily at a specific time
  - Custom cron-like schedules

The scheduler runs in the foreground and keeps backing up until you stop it (Ctrl+C).
Each run creates timestamped backups just like manual backups.
"""

import signal
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from netbackup.utils.device_loader import load_devices
from netbackup.backup.backup_manager import backup_all_devices, backup_all_devices_parallel
from netbackup.utils.logger import get_logger

logger = get_logger("scheduler")


def _run_backup_job(inventory_path: str, backup_dir: str, parallel: bool, workers: int):
    """Internal function called by the scheduler on each run."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'#'*60}")
    print(f" SCHEDULED BACKUP — {timestamp}")
    print(f"{'#'*60}")
    logger.info(f"Scheduled backup started at {timestamp}")

    try:
        devices = load_devices(inventory_path)
        if parallel:
            results = backup_all_devices_parallel(devices, backup_dir, max_workers=workers)
        else:
            results = backup_all_devices(devices, backup_dir)

        success = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        logger.info(f"Scheduled backup complete: {success} succeeded, {failed} failed")
    except Exception as e:
        logger.error(f"Scheduled backup failed: {e}")
        print(f"[ERROR] Scheduled backup failed: {e}")


def start_scheduler(
    inventory_path: str,
    backup_dir: str = "backups",
    interval_hours: int = 6,
    parallel: bool = False,
    workers: int = 5,
    cron_expr: str = None,
):
    """
    Start the backup scheduler.

    Args:
        inventory_path: Path to device inventory YAML
        backup_dir:     Where to save backups
        interval_hours: Run every N hours (default: 6)
        parallel:       Use parallel backups
        workers:        Number of parallel workers
        cron_expr:      Optional cron expression (overrides interval_hours)
                        Format: "hour:minute" e.g., "02:00" for 2 AM daily
    """
    scheduler = BlockingScheduler()

    if cron_expr:
        # Parse "HH:MM" format for daily schedule
        parts = cron_expr.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        trigger = CronTrigger(hour=hour, minute=minute)
        schedule_desc = f"daily at {cron_expr}"
    else:
        trigger = IntervalTrigger(hours=interval_hours)
        schedule_desc = f"every {interval_hours} hour(s)"

    scheduler.add_job(
        _run_backup_job,
        trigger=trigger,
        args=[inventory_path, backup_dir, parallel, workers],
        id="backup_job",
        name="Network Config Backup",
    )

    print(f"\n{'='*60}")
    print(f" BACKUP SCHEDULER STARTED")
    print(f" Schedule: {schedule_desc}")
    print(f" Inventory: {inventory_path}")
    print(f" Backup Dir: {backup_dir}")
    print(f" Parallel: {parallel} (workers: {workers})")
    print(f" Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    logger.info(f"Scheduler started: {schedule_desc}")

    # Run first backup immediately
    print("  Running initial backup now...\n")
    _run_backup_job(inventory_path, backup_dir, parallel, workers)

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\n\n  Scheduler stopped by user.")
        logger.info("Scheduler stopped by user")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
