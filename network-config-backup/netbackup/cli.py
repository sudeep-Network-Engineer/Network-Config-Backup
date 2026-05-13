"""
CLI Interface — The main entry point for the Network Config Backup tool.

Uses the Click library to define 20 CLI commands:
  - backup:            Backup device configs (sequential or parallel)
  - list-backups:      Show saved backups
  - rollback:          Restore a previous config
  - comply:            Run compliance checks
  - diff:              Compare two config backups
  - detect-changes:    Check if configs have changed
  - cleanup:           Delete old backups (retention policy)
  - generate-key:      Create encryption key
  - encrypt-inventory: Encrypt passwords in inventory
  - decrypt-inventory: Decrypt passwords in inventory
  - health-check:      Test device reachability
  - schedule:          Auto-backup on a schedule
  - dashboard:         Launch web dashboard
  - setup-email:       Create email settings template
  - stats:             Backup statistics
  - search:            Search across all configs
  - topology:          Network topology map
  - menu:              Interactive guided menu
  - demo:              Run a demo with sample configs

Usage:
  python -m netbackup backup --inventory inventory/devices.yaml
  python -m netbackup backup --inventory inventory/devices.yaml --parallel --workers 10
  python -m netbackup comply --inventory inventory/devices.yaml --baseline baselines/security_baseline.yaml
  python -m netbackup diff --file1 backups/router1/old.cfg --file2 backups/router1/new.cfg
  python -m netbackup dashboard --inventory inventory/devices.yaml
"""

import click

from netbackup.utils.device_loader import load_devices
from netbackup.backup.backup_manager import (
    backup_all_devices,
    backup_all_devices_parallel,
    backup_device,
    list_backups,
    detect_config_changes,
    cleanup_old_backups,
)
from netbackup.backup.rollback import rollback_device
from netbackup.backup.config_diff import diff_configs, print_diff, save_html_diff
from netbackup.compliance.checker import load_baseline, check_all_devices, check_device_compliance
from netbackup.reports.report_generator import generate_cli_report, generate_html_report, generate_csv_report
from netbackup.utils.crypto import (
    generate_key,
    encrypt_inventory,
    decrypt_inventory,
)
from netbackup.utils.health_check import health_check_all
from netbackup.utils.email_alert import send_compliance_email, create_email_settings_template
from netbackup.scheduler import start_scheduler
from netbackup.dashboard import start_dashboard
from netbackup.utils.backup_stats import print_backup_stats
from netbackup.utils.config_search import search_configs, print_search_results
from netbackup.utils.topology import print_topology
from netbackup.interactive import run_interactive


@click.group()
def cli():
    """
    Network Config Backup & Compliance Checker

    A CLI tool to backup network device configs via SSH/Telnet,
    check compliance against security baselines, and generate reports.

    Supports: SSH, Telnet, parallel backups, config diff, encrypted
    credentials, change detection, backup retention, health checks,
    scheduled backups, email alerts, CSV export, and web dashboard.
    """
    pass


# ============================================================
# BACKUP COMMAND
# ============================================================
@cli.command()
@click.option(
    "--inventory", "-i",
    required=True,
    help="Path to device inventory YAML file",
)
@click.option(
    "--device", "-d",
    default=None,
    help="Backup a specific device by hostname (optional)",
)
@click.option(
    "--backup-dir", "-o",
    default="backups",
    help="Directory to store backups (default: backups/)",
)
@click.option(
    "--parallel", "-p",
    is_flag=True,
    default=False,
    help="Run backups in parallel (multi-threaded) for speed",
)
@click.option(
    "--workers", "-w",
    default=5,
    help="Number of parallel workers (default: 5, use with --parallel)",
)
def backup(inventory, device, backup_dir, parallel, workers):
    """Backup running configs from network devices via SSH/Telnet."""
    devices = load_devices(inventory, device_filter=device)

    if device:
        # Single device backup
        result = backup_device(devices[0], backup_dir)
        if result["status"] == "failed":
            click.echo(f"\nFailed: {result['message']}")
    elif parallel:
        # Parallel backup (multi-threaded)
        results = backup_all_devices_parallel(devices, backup_dir, max_workers=workers)
    else:
        # Sequential backup
        results = backup_all_devices(devices, backup_dir)


# ============================================================
# LIST-BACKUPS COMMAND
# ============================================================
@cli.command("list-backups")
@click.option(
    "--device", "-d",
    default=None,
    help="Filter by device hostname",
)
@click.option(
    "--backup-dir",
    default="backups",
    help="Backup directory (default: backups/)",
)
def list_backups_cmd(device, backup_dir):
    """List all saved configuration backups."""
    backups = list_backups(backup_dir, device_filter=device)

    if not backups:
        click.echo("No backups found.")
        return

    for hostname, files in backups.items():
        click.echo(f"\n  {hostname} ({len(files)} backups):")
        for f in files:
            click.echo(f"    - {f}")


# ============================================================
# ROLLBACK COMMAND
# ============================================================
@cli.command()
@click.option(
    "--inventory", "-i",
    required=True,
    help="Path to device inventory YAML file",
)
@click.option(
    "--device", "-d",
    required=True,
    help="Device hostname to rollback",
)
@click.option(
    "--backup-file", "-f",
    required=True,
    help="Path to the backup .cfg file to restore",
)
@click.option(
    "--no-save",
    is_flag=True,
    default=False,
    help="Don't save to startup-config after rollback",
)
def rollback(inventory, device, backup_file, no_save):
    """Rollback a device to a previously saved configuration."""
    devices = load_devices(inventory, device_filter=device)
    result = rollback_device(devices[0], backup_file, save_config=not no_save)

    if result["status"] == "success":
        click.echo(f"\n{result['message']}")
    else:
        click.echo(f"\nFailed: {result['message']}")


# ============================================================
# COMPLY COMMAND
# ============================================================
@cli.command()
@click.option(
    "--inventory", "-i",
    required=True,
    help="Path to device inventory YAML file",
)
@click.option(
    "--baseline", "-b",
    required=True,
    help="Path to compliance baseline YAML file",
)
@click.option(
    "--device", "-d",
    default=None,
    help="Check a specific device (optional)",
)
@click.option(
    "--backup-dir",
    default="backups",
    help="Backup directory to read configs from (default: backups/)",
)
@click.option(
    "--html-report",
    default=None,
    help="Generate HTML report at this path (e.g., reports_output/report.html)",
)
@click.option(
    "--csv-report",
    default=None,
    help="Generate CSV report at this path (e.g., reports_output/report.csv)",
)
@click.option(
    "--email",
    is_flag=True,
    default=False,
    help="Send results via email (requires email_settings.yaml)",
)
def comply(inventory, baseline, device, backup_dir, html_report, csv_report, email):
    """Run compliance checks against security baselines."""
    devices = load_devices(inventory, device_filter=device)
    rules = load_baseline(baseline)

    # Run compliance checks
    results = check_all_devices(devices, rules, backup_dir=backup_dir)

    # Generate CLI report
    generate_cli_report(results)

    # Generate HTML report if requested
    if html_report:
        generate_html_report(results, html_report, baseline_name=baseline)
        click.echo(f"\nHTML report: {html_report}")

    # Generate CSV report if requested
    if csv_report:
        generate_csv_report(results, csv_report)
        click.echo(f"CSV report: {csv_report}")

    # Send email if requested
    if email:
        send_compliance_email(results, html_report_path=html_report)


# ============================================================
# DIFF COMMAND — Compare two config backups
# ============================================================
@cli.command("diff")
@click.option(
    "--file1", "-1",
    required=True,
    help="Path to the first (older) config file",
)
@click.option(
    "--file2", "-2",
    required=True,
    help="Path to the second (newer) config file",
)
@click.option(
    "--html",
    default=None,
    help="Save HTML diff to this path (optional)",
)
@click.option(
    "--context", "-c",
    default=3,
    help="Number of context lines around changes (default: 3)",
)
def diff_cmd(file1, file2, html, context):
    """Compare two configuration backup files side-by-side."""
    result = diff_configs(file1, file2, context_lines=context)
    print_diff(result)

    if html:
        save_html_diff(result, html)
        click.echo(f"\nHTML diff: {html}")


# ============================================================
# DETECT-CHANGES COMMAND — Check for config drift
# ============================================================
@cli.command("detect-changes")
@click.option(
    "--backup-dir",
    default="backups",
    help="Backup directory (default: backups/)",
)
@click.option(
    "--device", "-d",
    default=None,
    help="Check a specific device (optional)",
)
def detect_changes_cmd(backup_dir, device):
    """Detect if device configs have changed between backups."""
    changes = detect_config_changes(backup_dir, device_filter=device)

    if not changes:
        click.echo("No backups found to compare.")
        return

    click.echo(f"\n{'='*60}")
    click.echo(f" CONFIG CHANGE DETECTION")
    click.echo(f"{'='*60}\n")

    for change in changes:
        if change["changed"]:
            click.echo(f"  [!] {change['hostname']}: {change['message']}")
        else:
            click.echo(f"  [=] {change['hostname']}: {change['message']}")

    changed_count = sum(1 for c in changes if c["changed"])
    click.echo(f"\n  {changed_count}/{len(changes)} devices have config changes.\n")


# ============================================================
# CLEANUP COMMAND — Delete old backups
# ============================================================
@cli.command("cleanup")
@click.option(
    "--backup-dir",
    default="backups",
    help="Backup directory (default: backups/)",
)
@click.option(
    "--retention-days", "-r",
    default=30,
    help="Delete backups older than this many days (default: 30)",
)
@click.option(
    "--device", "-d",
    default=None,
    help="Cleanup a specific device (optional)",
)
def cleanup_cmd(backup_dir, retention_days, device):
    """Delete old backups based on retention policy."""
    click.echo(f"\n  Cleaning up backups older than {retention_days} days...\n")
    summary = cleanup_old_backups(backup_dir, retention_days, device_filter=device)

    click.echo(f"\n  Total: {summary['total_deleted']} deleted, "
               f"{summary['total_kept']} kept")


# ============================================================
# GENERATE-KEY COMMAND — Create encryption key
# ============================================================
@cli.command("generate-key")
@click.option(
    "--key-path", "-k",
    default=".encryption.key",
    help="Where to save the key (default: .encryption.key)",
)
def generate_key_cmd(key_path):
    """Generate a new encryption key for securing inventory passwords."""
    generate_key(key_path)
    click.echo("\n  Key generated! Now encrypt your inventory:")
    click.echo(f"  python -m netbackup encrypt-inventory -i inventory/devices.yaml")


# ============================================================
# ENCRYPT-INVENTORY COMMAND
# ============================================================
@cli.command("encrypt-inventory")
@click.option(
    "--inventory", "-i",
    required=True,
    help="Path to device inventory YAML file",
)
@click.option(
    "--key-path", "-k",
    default=".encryption.key",
    help="Path to encryption key (default: .encryption.key)",
)
def encrypt_inventory_cmd(inventory, key_path):
    """Encrypt passwords in the inventory file."""
    encrypt_inventory(inventory, key_path)
    click.echo("\n  Passwords are now encrypted in the inventory file.")
    click.echo("  The tool will auto-decrypt them when it runs.")


# ============================================================
# DECRYPT-INVENTORY COMMAND
# ============================================================
@cli.command("decrypt-inventory")
@click.option(
    "--inventory", "-i",
    required=True,
    help="Path to device inventory YAML file",
)
@click.option(
    "--key-path", "-k",
    default=".encryption.key",
    help="Path to encryption key (default: .encryption.key)",
)
def decrypt_inventory_cmd(inventory, key_path):
    """Decrypt passwords in the inventory file (restore to plain text)."""
    decrypt_inventory(inventory, key_path)
    click.echo("\n  Passwords are now decrypted (plain text) in the inventory file.")


# ============================================================
# DEMO COMMAND — Test without real devices
# ============================================================
@cli.command()
@click.option(
    "--baseline", "-b",
    default="baselines/security_baseline.yaml",
    help="Path to compliance baseline YAML file",
)
@click.option(
    "--html-report",
    default="reports_output/demo_report.html",
    help="Path for HTML report output",
)
def demo(baseline, html_report):
    """Run a demo compliance check with sample configs (no real devices needed)."""

    # Sample configs — includes both SSH and Telnet device examples
    sample_devices = [
        {
            "hostname": "demo-router-compliant",
            "config": """
hostname demo-router-compliant
!
service password-encryption
no ip source-route
ip ssh version 2
ip ssh time-out 60
!
enable secret 5 $1$abc$hashedpassword
!
logging host 10.0.0.100
logging buffered 16384
!
ntp server 10.0.0.50
!
banner login ^C Authorized Access Only ^C
!
line con 0
 exec-timeout 5 0
 transport input ssh
line vty 0 4
 exec-timeout 5 0
 transport input ssh
!
end
""",
        },
        {
            "hostname": "demo-switch-noncompliant",
            "config": """
hostname demo-switch-noncompliant
!
enable password 0 plaintext123
!
snmp-server community public RO
snmp-server community private RW
!
line con 0
 transport input telnet
line vty 0 4
 transport input telnet
!
end
""",
        },
        {
            "hostname": "demo-router-partial",
            "config": """
hostname demo-router-partial
!
service password-encryption
ip ssh version 2
!
enable secret 9 $9$hashedpassword
!
logging host 10.0.0.100
!
no ip source-route
!
line con 0
 transport input ssh
line vty 0 4
 transport input ssh
!
end
""",
        },
        {
            "hostname": "demo-telnet-device",
            "config": """
hostname demo-telnet-device
!
service password-encryption
no ip source-route
ip ssh version 2
ip ssh time-out 120
!
enable secret 8 $8$hashedpassword
!
logging host 10.0.0.100
logging buffered 8192
!
ntp server 10.0.0.50
!
banner login ^C Warning: Authorized Access Only ^C
!
line con 0
 exec-timeout 10 0
 transport input ssh
line vty 0 4
 exec-timeout 10 0
 transport input ssh telnet
!
end
""",
        },
    ]

    click.echo("\n  Running demo with sample device configs...\n")
    click.echo("  Includes SSH and Telnet device examples.\n")

    rules = load_baseline(baseline)

    # Check each sample device
    results = []
    for sample in sample_devices:
        fake_device = {"hostname": sample["hostname"], "device_type": "cisco_ios"}
        result = check_device_compliance(
            fake_device, rules, config=sample["config"]
        )
        results.append(result)

    # Generate reports
    generate_cli_report(results)
    generate_html_report(results, html_report)

    # Demo the diff feature with sample configs
    click.echo(f"\n  {'='*50}")
    click.echo(f"  DEMO: Config Diff Feature")
    click.echo(f"  {'='*50}")

    # Create temp files for diff demo
    import tempfile, os
    old_config = sample_devices[0]["config"]
    new_config = old_config.replace("ip ssh time-out 60", "ip ssh time-out 120")
    new_config = new_config.replace("exec-timeout 5 0", "exec-timeout 10 0")
    new_config = new_config + "\naccess-list 10 permit 10.0.0.0 0.0.0.255\n"

    tmp_dir = tempfile.mkdtemp()
    old_file = os.path.join(tmp_dir, "old_config.cfg")
    new_file = os.path.join(tmp_dir, "new_config.cfg")

    with open(old_file, "w") as f:
        f.write(old_config)
    with open(new_file, "w") as f:
        f.write(new_config)

    diff_result = diff_configs(old_file, new_file)
    print_diff(diff_result)

    # Generate CSV demo
    csv_path = "reports_output/demo_report.csv"
    generate_csv_report(results, csv_path)

    click.echo(f"\n  Demo complete!")
    click.echo(f"  HTML report: {html_report}")
    click.echo(f"  CSV report:  {csv_path}")


# ============================================================
# HEALTH-CHECK COMMAND
# ============================================================
@cli.command("health-check")
@click.option(
    "--inventory", "-i",
    required=True,
    help="Path to device inventory YAML file",
)
@click.option(
    "--device", "-d",
    default=None,
    help="Check a specific device (optional)",
)
@click.option(
    "--timeout", "-t",
    default=3,
    help="Timeout per check in seconds (default: 3)",
)
def health_check_cmd(inventory, device, timeout):
    """Test device reachability (ping + port check) before operations."""
    devices = load_devices(inventory, device_filter=device)
    results = health_check_all(devices, timeout=timeout)


# ============================================================
# SCHEDULE COMMAND — Auto-backup on a schedule
# ============================================================
@cli.command("schedule")
@click.option(
    "--inventory", "-i",
    required=True,
    help="Path to device inventory YAML file",
)
@click.option(
    "--interval", "-n",
    default=6,
    help="Backup every N hours (default: 6)",
)
@click.option(
    "--daily",
    default=None,
    help="Run daily at HH:MM (e.g., '02:00' for 2 AM). Overrides --interval",
)
@click.option(
    "--backup-dir",
    default="backups",
    help="Backup directory (default: backups/)",
)
@click.option(
    "--parallel", "-p",
    is_flag=True,
    default=False,
    help="Use parallel backups",
)
@click.option(
    "--workers", "-w",
    default=5,
    help="Number of parallel workers",
)
def schedule_cmd(inventory, interval, daily, backup_dir, parallel, workers):
    """Start automatic scheduled backups (runs until Ctrl+C)."""
    start_scheduler(
        inventory_path=inventory,
        backup_dir=backup_dir,
        interval_hours=interval,
        parallel=parallel,
        workers=workers,
        cron_expr=daily,
    )


# ============================================================
# DASHBOARD COMMAND — Launch web dashboard
# ============================================================
@cli.command("dashboard")
@click.option(
    "--inventory", "-i",
    required=True,
    help="Path to device inventory YAML file",
)
@click.option(
    "--baseline", "-b",
    default=None,
    help="Path to compliance baseline (optional, enables compliance view)",
)
@click.option(
    "--backup-dir",
    default="backups",
    help="Backup directory (default: backups/)",
)
@click.option(
    "--port",
    default=5050,
    help="Port to run dashboard on (default: 5050)",
)
def dashboard_cmd(inventory, baseline, backup_dir, port):
    """Launch interactive web dashboard in your browser."""
    start_dashboard(
        inventory_path=inventory,
        baseline_path=baseline,
        backup_dir=backup_dir,
        port=port,
    )


# ============================================================
# SETUP-EMAIL COMMAND
# ============================================================
@cli.command("setup-email")
@click.option(
    "--output", "-o",
    default="email_settings.yaml",
    help="Output path for email settings template",
)
def setup_email_cmd(output):
    """Create an email settings template file for email alerts."""
    create_email_settings_template(output)


# ============================================================
# STATS COMMAND — Backup statistics
# ============================================================
@cli.command("stats")
@click.option(
    "--backup-dir",
    default="backups",
    help="Backup directory (default: backups/)",
)
def stats_cmd(backup_dir):
    """Show backup statistics (count, size, dates per device)."""
    print_backup_stats(backup_dir)


# ============================================================
# SEARCH COMMAND — Search across configs
# ============================================================
@cli.command("search")
@click.argument("pattern")
@click.option(
    "--backup-dir",
    default="backups",
    help="Backup directory (default: backups/)",
)
@click.option(
    "--device", "-d",
    default=None,
    help="Search a specific device (optional)",
)
@click.option(
    "--regex", "-r",
    is_flag=True,
    default=False,
    help="Treat pattern as a regex",
)
@click.option(
    "--context", "-c",
    default=0,
    help="Lines of context around matches (default: 0)",
)
def search_cmd(pattern, backup_dir, device, regex, context):
    """Search all device configs for a pattern (e.g., 'snmp-server community')."""
    results = search_configs(
        pattern, backup_dir, device_filter=device,
        regex=regex, context_lines=context,
    )
    print_search_results(results, pattern)


# ============================================================
# TOPOLOGY COMMAND — Network topology map
# ============================================================
@cli.command("topology")
@click.option(
    "--inventory", "-i",
    required=True,
    help="Path to device inventory YAML file",
)
@click.option(
    "--backup-dir",
    default="backups",
    help="Backup directory (default: backups/)",
)
def topology_cmd(inventory, backup_dir):
    """Generate a visual network topology map from inventory."""
    devices = load_devices(inventory)
    print_topology(devices, backup_dir)


# ============================================================
# MENU COMMAND — Interactive guided menu
# ============================================================
@cli.command("menu")
def menu_cmd():
    """Launch interactive guided menu (beginner-friendly)."""
    run_interactive()


# ============================================================
# Entry point: python -m netbackup.cli
# ============================================================
if __name__ == "__main__":
    cli()
