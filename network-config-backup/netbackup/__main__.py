"""
Entry point for: python -m netbackup

This file allows you to run the tool as a Python module:
  python -m netbackup backup --inventory inventory/devices.yaml
  python -m netbackup demo
"""

from netbackup.cli import cli

if __name__ == "__main__":
    cli()
