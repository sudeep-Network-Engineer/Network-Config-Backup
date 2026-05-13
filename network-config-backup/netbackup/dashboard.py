"""
Web Dashboard — Interactive browser-based dashboard for viewing results.

Runs a local Flask web server that shows:
  - Device inventory overview
  - Backup status per device
  - Compliance scores with charts
  - Recent backups list
  - Quick access to reports

Access at: http://localhost:5050

This is impressive for interviews — shows you can build full-stack tools.
"""

import json
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template_string, jsonify

from netbackup.utils.device_loader import load_devices
from netbackup.backup.backup_manager import list_backups, detect_config_changes
from netbackup.compliance.checker import load_baseline, check_all_devices


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetBackup Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }

        /* Header */
        .header {
            background: linear-gradient(135deg, #1e293b, #334155);
            padding: 20px 30px;
            border-bottom: 2px solid #3b82f6;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { color: #3b82f6; font-size: 22px; }
        .header .time { color: #94a3b8; font-size: 14px; }

        /* Main Grid */
        .main { padding: 20px 30px; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }

        /* Stat Cards */
        .card {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #334155;
        }
        .card .value {
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .card .label { color: #94a3b8; font-size: 14px; }
        .card.blue .value { color: #3b82f6; }
        .card.green .value { color: #22c55e; }
        .card.yellow .value { color: #eab308; }
        .card.red .value { color: #ef4444; }

        /* Tables */
        .section {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #334155;
            margin-bottom: 20px;
        }
        .section h2 {
            font-size: 16px;
            color: #3b82f6;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        table { width: 100%; border-collapse: collapse; }
        th {
            text-align: left;
            padding: 10px 12px;
            color: #94a3b8;
            font-size: 12px;
            text-transform: uppercase;
            border-bottom: 1px solid #334155;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #1e293b;
            font-size: 14px;
        }
        tr:hover { background: #334155; }

        /* Badges */
        .badge {
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        .badge-green { background: #166534; color: #22c55e; }
        .badge-yellow { background: #713f12; color: #eab308; }
        .badge-red { background: #7f1d1d; color: #ef4444; }
        .badge-blue { background: #1e3a5f; color: #3b82f6; }

        /* Score bar */
        .score-bar {
            width: 100%;
            height: 8px;
            background: #334155;
            border-radius: 4px;
            overflow: hidden;
        }
        .score-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        .score-fill.green { background: #22c55e; }
        .score-fill.yellow { background: #eab308; }
        .score-fill.red { background: #ef4444; }

        /* Refresh button */
        .refresh-btn {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        .refresh-btn:hover { background: #2563eb; }

        .footer {
            text-align: center;
            padding: 20px;
            color: #475569;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>NetBackup Dashboard</h1>
        <div>
            <span class="time">Last updated: {{ timestamp }}</span>
            &nbsp;&nbsp;
            <button class="refresh-btn" onclick="location.reload()">Refresh</button>
        </div>
    </div>

    <div class="main">
        <!-- Summary Cards -->
        <div class="grid">
            <div class="card blue">
                <div class="value">{{ total_devices }}</div>
                <div class="label">Total Devices</div>
            </div>
            <div class="card green">
                <div class="value">{{ total_backups }}</div>
                <div class="label">Total Backups</div>
            </div>
            <div class="card {% if avg_score >= 80 %}green{% elif avg_score >= 50 %}yellow{% else %}red{% endif %}">
                <div class="value">{{ avg_score }}%</div>
                <div class="label">Avg Compliance Score</div>
            </div>
            <div class="card {% if changes_detected > 0 %}red{% else %}green{% endif %}">
                <div class="value">{{ changes_detected }}</div>
                <div class="label">Config Changes Detected</div>
            </div>
        </div>

        <!-- Compliance Results -->
        {% if compliance_results %}
        <div class="section">
            <h2>Compliance Scores</h2>
            <table>
                <thead>
                    <tr>
                        <th>Device</th>
                        <th>Score</th>
                        <th>Progress</th>
                        <th>Passed</th>
                        <th>Failed</th>
                    </tr>
                </thead>
                <tbody>
                    {% for r in compliance_results %}
                    <tr>
                        <td><strong>{{ r.hostname }}</strong></td>
                        <td>
                            <span class="badge {% if r.score >= 80 %}badge-green{% elif r.score >= 50 %}badge-yellow{% else %}badge-red{% endif %}">
                                {{ r.score }}%
                            </span>
                        </td>
                        <td>
                            <div class="score-bar">
                                <div class="score-fill {% if r.score >= 80 %}green{% elif r.score >= 50 %}yellow{% else %}red{% endif %}"
                                     style="width: {{ r.score }}%"></div>
                            </div>
                        </td>
                        <td>{{ r.passed }}</td>
                        <td>{{ r.failed }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}

        <!-- Recent Backups -->
        <div class="section">
            <h2>Recent Backups</h2>
            <table>
                <thead>
                    <tr>
                        <th>Device</th>
                        <th>Backups</th>
                        <th>Latest</th>
                    </tr>
                </thead>
                <tbody>
                    {% for hostname, files in backups.items() %}
                    <tr>
                        <td><strong>{{ hostname }}</strong></td>
                        <td><span class="badge badge-blue">{{ files|length }}</span></td>
                        <td>{{ files[0].split('/')[-1] if files else 'None' }}</td>
                    </tr>
                    {% endfor %}
                    {% if not backups %}
                    <tr><td colspan="3" style="color:#94a3b8">No backups found. Run: python -m netbackup backup</td></tr>
                    {% endif %}
                </tbody>
            </table>
        </div>

        <!-- Device Inventory -->
        <div class="section">
            <h2>Device Inventory</h2>
            <table>
                <thead>
                    <tr>
                        <th>Hostname</th>
                        <th>IP Address</th>
                        <th>Type</th>
                        <th>Protocol</th>
                        <th>Port</th>
                    </tr>
                </thead>
                <tbody>
                    {% for d in devices %}
                    <tr>
                        <td><strong>{{ d.hostname }}</strong></td>
                        <td>{{ d.host }}</td>
                        <td>{{ d.device_type }}</td>
                        <td>
                            <span class="badge {% if 'telnet' in d.device_type %}badge-yellow{% else %}badge-green{% endif %}">
                                {% if 'telnet' in d.device_type %}Telnet{% else %}SSH{% endif %}
                            </span>
                        </td>
                        <td>{{ d.port }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="footer">
        Network Config Backup & Compliance Checker | Dashboard v1.0
    </div>
</body>
</html>
"""


def start_dashboard(
    inventory_path: str,
    baseline_path: str = None,
    backup_dir: str = "backups",
    port: int = 5050,
):
    """
    Start the web dashboard server.

    Args:
        inventory_path: Path to device inventory YAML
        baseline_path:  Path to compliance baseline YAML (optional)
        backup_dir:     Backup directory
        port:           Port to run the dashboard on (default: 5050)
    """
    app = Flask(__name__)

    @app.route("/")
    def index():
        # Load data
        try:
            devices = load_devices(inventory_path)
        except SystemExit:
            devices = []

        backups_data = list_backups(backup_dir)
        total_backups = sum(len(files) for files in backups_data.values())

        # Compliance results (if baseline provided)
        compliance_results = []
        avg_score = 0
        if baseline_path:
            try:
                rules = load_baseline(baseline_path)
                compliance_results = check_all_devices(devices, rules, backup_dir=backup_dir)
                avg_score = round(
                    sum(r["score"] for r in compliance_results) / len(compliance_results), 1
                ) if compliance_results else 0
            except (SystemExit, Exception):
                pass

        # Change detection
        changes = detect_config_changes(backup_dir)
        changes_detected = sum(1 for c in changes if c.get("changed", False))

        return render_template_string(
            DASHBOARD_HTML,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_devices=len(devices),
            total_backups=total_backups,
            avg_score=avg_score,
            changes_detected=changes_detected,
            compliance_results=compliance_results,
            backups=backups_data,
            devices=devices,
        )

    print(f"\n{'='*60}")
    print(f" NETBACKUP DASHBOARD")
    print(f" Open in browser: http://localhost:{port}")
    print(f" Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    app.run(host="0.0.0.0", port=port, debug=False)
