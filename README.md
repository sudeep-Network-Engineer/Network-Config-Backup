[README.md](https://github.com/user-attachments/files/27682942/README.md)
# Network Config Backup & Compliance Checker

A Python CLI tool to automate bulk network device configuration backups via SSH/Telnet with timestamped versioning, rollback capability, compliance checking, and 12 advanced features including parallel backups, web dashboard, scheduled auto-backups, email alerts, and more.

## Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Bulk Config Backup** | Connect to 20+ routers/switches via SSH, pull configs, save with timestamps |
| 2 | **Telnet Support** | Works with older devices that don't support SSH |
| 3 | **Parallel Backups** | Multi-threaded backup (backup 20 devices simultaneously) |
| 4 | **Rollback** | Push a previously saved config back to any device |
| 5 | **Compliance Engine** | Scan configs against YAML-defined security baselines |
| 6 | **Config Diff** | Compare any two backups side-by-side with colored output |
| 7 | **Change Detection** | Alert when configs change unexpectedly between backups |
| 8 | **Encrypted Credentials** | Encrypt passwords in inventory files |
| 9 | **Backup Retention** | Auto-delete old backups based on retention policy |
| 10 | **Scheduled Backups** | Auto-backup devices at set intervals (every N hours or daily) |
| 11 | **Email Alerts** | Send compliance reports via email (Gmail, Outlook, etc.) |
| 12 | **CSV Export** | Export compliance results to CSV for Excel analysis |
| 13 | **Device Health Check** | Ping + port check before operations |
| 14 | **Web Dashboard** | Interactive browser dashboard with charts and scores |
| 15 | **Professional Logging** | Timestamped audit trail in log files |
| 16 | **HTML Reports** | Professional web reports using Jinja2 templates |

## Tech Stack

| Component | Tool |
|-----------|------|
| SSH/Telnet | Netmiko |
| Config/rules | YAML (PyYAML) |
| Report templates | Jinja2 |
| CLI interface | Click |
| CLI tables | PrettyTable |
| Web dashboard | Flask |
| Scheduled backups | APScheduler |
| Credential encryption | Built-in XOR + Base64 |

## Project Structure

```
network-config-backup/
├── netbackup/                  # Main Python package
│   ├── __init__.py
│   ├── __main__.py             # Entry point
│   ├── cli.py                  # 16 CLI commands
│   ├── dashboard.py            # Flask web dashboard
│   ├── scheduler.py            # APScheduler auto-backups
│   ├── backup/
│   │   ├── backup_manager.py   # SSH/Telnet backup engine
│   │   ├── rollback.py         # Config rollback
│   │   └── config_diff.py      # Config comparison (diff)
│   ├── compliance/
│   │   └── checker.py          # Compliance scanning engine
│   ├── reports/
│   │   └── report_generator.py # CLI + HTML + CSV reports
│   ├── templates/
│   │   └── report.html.j2      # Jinja2 HTML template
│   └── utils/
│       ├── device_loader.py    # YAML inventory loader
│       ├── crypto.py           # Encrypt/decrypt credentials
│       ├── health_check.py     # Ping + port reachability
│       ├── email_alert.py      # Email notifications
│       └── logger.py           # Professional logging system
├── inventory/
│   └── devices.yaml            # Device inventory
├── baselines/
│   └── security_baseline.yaml  # 15 compliance rules
├── requirements.txt
├── LICENSE
└── README.md
```

## Installation

```bash
git clone https://github.com/yourusername/network-config-backup.git
cd network-config-backup
pip install -r requirements.txt
```

## Quick Start

```bash
# Test without any real devices
python -m netbackup demo

# See all commands
python -m netbackup --help
```

## All CLI Commands

| Command | Description |
|---------|-------------|
| `backup` | Backup device configs (`--parallel` for speed) |
| `list-backups` | Show saved backups |
| `rollback` | Restore a previous config to a device |
| `comply` | Run compliance checks (`--csv-report`, `--html-report`, `--email`) |
| `diff` | Compare two config backups side-by-side |
| `detect-changes` | Check for config drift between backups |
| `cleanup` | Delete old backups (retention policy) |
| `health-check` | Ping + port test on all devices |
| `schedule` | Auto-backup on interval or daily schedule |
| `dashboard` | Launch web dashboard in browser |
| `generate-key` | Create encryption key |
| `encrypt-inventory` | Encrypt passwords in inventory |
| `decrypt-inventory` | Decrypt passwords back to plain text |
| `setup-email` | Create email settings template |
| `demo` | Run demo with sample configs |

## Usage Examples

### Backup

```bash
# Backup all devices
python -m netbackup backup -i inventory/devices.yaml

# Parallel backup (10 threads)
python -m netbackup backup -i inventory/devices.yaml --parallel --workers 10

# Backup one device
python -m netbackup backup -i inventory/devices.yaml -d router1
```

### Compliance

```bash
# CLI report
python -m netbackup comply -i inventory/devices.yaml -b baselines/security_baseline.yaml

# HTML + CSV reports
python -m netbackup comply -i inventory/devices.yaml -b baselines/security_baseline.yaml \
  --html-report reports_output/report.html \
  --csv-report reports_output/report.csv

# Email results
python -m netbackup comply -i inventory/devices.yaml -b baselines/security_baseline.yaml --email
```

### Config Diff

```bash
python -m netbackup diff -1 backups/router1/old.cfg -2 backups/router1/new.cfg
```

### Health Check

```bash
python -m netbackup health-check -i inventory/devices.yaml
```

### Scheduled Backups

```bash
# Every 6 hours
python -m netbackup schedule -i inventory/devices.yaml --interval 6

# Daily at 2 AM
python -m netbackup schedule -i inventory/devices.yaml --daily 02:00

# Parallel scheduled backups
python -m netbackup schedule -i inventory/devices.yaml --interval 4 --parallel --workers 10
```

### Web Dashboard

```bash
python -m netbackup dashboard -i inventory/devices.yaml -b baselines/security_baseline.yaml
# Open http://localhost:5050 in browser
```

### Credential Encryption

```bash
python -m netbackup generate-key
python -m netbackup encrypt-inventory -i inventory/devices.yaml
```

### Backup Retention

```bash
# Delete backups older than 7 days
python -m netbackup cleanup -r 7
```

### Email Alerts

```bash
# Create email config
python -m netbackup setup-email

# Edit email_settings.yaml with your SMTP credentials

# Run compliance with email
python -m netbackup comply -i inventory/devices.yaml -b baselines/security_baseline.yaml --email
```

## Telnet Support

For older devices without SSH, use `_telnet` suffix:

```yaml
devices:
  - hostname: "old-router"
    device_type: "cisco_ios_telnet"
    port: 23
```

## License

MIT
