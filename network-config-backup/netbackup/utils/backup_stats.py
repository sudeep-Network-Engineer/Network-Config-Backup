"""
Backup Statistics — Show detailed summary of all stored backups.

Provides:
  - Total backup count and disk usage
  - Per-device backup count, size, oldest/newest dates
  - Overall storage statistics

Useful for:
  - Knowing how much disk space backups are consuming
  - Identifying devices that haven't been backed up recently
  - Quick inventory of your backup history
"""

from pathlib import Path
from datetime import datetime

from colorama import Fore, Style, init
from prettytable import PrettyTable

init(autoreset=True)


def get_backup_stats(backup_dir: str = "backups") -> dict:
    """
    Calculate detailed statistics about all backups.

    Args:
        backup_dir: Path to the backup directory

    Returns:
        Dict with total_devices, total_backups, total_size_bytes,
        total_size_human, oldest_backup, newest_backup, per_device stats
    """
    backup_path = Path(backup_dir)

    stats = {
        "total_devices": 0,
        "total_backups": 0,
        "total_size_bytes": 0,
        "total_size_human": "0 B",
        "oldest_backup": None,
        "newest_backup": None,
        "devices": [],
    }

    if not backup_path.exists():
        return stats

    oldest_time = None
    newest_time = None

    for device_dir in sorted(backup_path.iterdir()):
        if not device_dir.is_dir():
            continue

        hostname = device_dir.name
        cfg_files = sorted(
            [f for f in device_dir.glob("*.cfg") if f.name != "latest.cfg"],
            key=lambda f: f.stat().st_mtime,
        )

        if not cfg_files:
            continue

        stats["total_devices"] += 1
        device_size = sum(f.stat().st_size for f in cfg_files)
        stats["total_backups"] += len(cfg_files)
        stats["total_size_bytes"] += device_size

        oldest_file = cfg_files[0]
        newest_file = cfg_files[-1]
        oldest_mtime = datetime.fromtimestamp(oldest_file.stat().st_mtime)
        newest_mtime = datetime.fromtimestamp(newest_file.stat().st_mtime)

        if oldest_time is None or oldest_mtime < oldest_time:
            oldest_time = oldest_mtime
        if newest_time is None or newest_mtime > newest_time:
            newest_time = newest_mtime

        device_stat = {
            "hostname": hostname,
            "backup_count": len(cfg_files),
            "total_size": _human_size(device_size),
            "oldest": oldest_mtime.strftime("%Y-%m-%d %H:%M"),
            "newest": newest_mtime.strftime("%Y-%m-%d %H:%M"),
            "avg_size": _human_size(device_size // len(cfg_files)) if cfg_files else "0 B",
        }
        stats["devices"].append(device_stat)

    stats["total_size_human"] = _human_size(stats["total_size_bytes"])
    if oldest_time:
        stats["oldest_backup"] = oldest_time.strftime("%Y-%m-%d %H:%M")
    if newest_time:
        stats["newest_backup"] = newest_time.strftime("%Y-%m-%d %H:%M")

    return stats


def print_backup_stats(backup_dir: str = "backups") -> dict:
    """
    Print a formatted backup statistics report.

    Args:
        backup_dir: Path to the backup directory

    Returns:
        Stats dict
    """
    stats = get_backup_stats(backup_dir)

    print(f"\n{'='*65}")
    print(f" BACKUP STATISTICS")
    print(f"{'='*65}\n")

    if stats["total_devices"] == 0:
        print("  No backups found. Run: python -m netbackup backup")
        return stats

    # Overall summary
    print(f"  Total Devices:  {Fore.CYAN}{stats['total_devices']}{Style.RESET_ALL}")
    print(f"  Total Backups:  {Fore.CYAN}{stats['total_backups']}{Style.RESET_ALL}")
    print(f"  Total Size:     {Fore.CYAN}{stats['total_size_human']}{Style.RESET_ALL}")
    print(f"  Oldest Backup:  {stats['oldest_backup']}")
    print(f"  Newest Backup:  {stats['newest_backup']}")

    # Per-device table
    print(f"\n  PER-DEVICE BREAKDOWN\n")
    table = PrettyTable()
    table.field_names = ["Device", "Backups", "Total Size", "Avg Size", "Oldest", "Newest"]
    table.align = "l"

    for d in stats["devices"]:
        table.add_row([
            d["hostname"],
            d["backup_count"],
            d["total_size"],
            d["avg_size"],
            d["oldest"],
            d["newest"],
        ])

    print(table)
    print()

    return stats


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
