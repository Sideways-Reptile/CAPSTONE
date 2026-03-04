#!/usr/bin/env python3
"""
task3_banners/deploy_banners.py
Bigfork IT — Capstone Lab

Task 3: Login Banners — Security & Compliance
Deploys legal login banners to all EXOS switches via SSH.
Also generates the pfSense banner config for manual application.

NOTE: SSH must already be enabled on switches (done via console — see guide).

Usage:
  python3 deploy_banners.py                  # deploy to all switches
  python3 deploy_banners.py --hq-only        # HQ switches only
  python3 deploy_banners.py --branch-only    # Branch switch only
  python3 deploy_banners.py --generate-only  # Print configs, no SSH
  python3 deploy_banners.py --host 10.10.10.21  # Single switch
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.exos_helper import (
    ok, fail, warn, info, section, banner_print,
    EXOSSwitch, HQ_SWITCHES, BRANCH_SWITCHES,
    BANNER_TEXT, save_report, run_on_all_switches, print_summary
)

# ─── BANNER CONFIGS ───────────────────────────────────────────────────────────

EXOS_BANNER = BANNER_TEXT.strip()

PFSENSE_SSH_BANNER = """\
***********************************************
*                                             *
*   AUTHORIZED ACCESS ONLY                   *
*                                             *
*   This system is property of Bigfork IT.  *
*   All activity is monitored and logged.    *
*   Unauthorized access is strictly          *
*   prohibited. Disconnect now if you are    *
*   not an authorized user.                  *
*                                             *
***********************************************
"""

PFSENSE_MOTD = """\
Welcome to Bigfork IT Network Infrastructure.
This system is monitored. Authorized access only.
"""


# ─── EXOS BANNER DEPLOYMENT ───────────────────────────────────────────────────

def deploy_banner_to_switch(sw_name, sw_info):
    """Deploy banner to a single EXOS switch. Returns list of commands."""
    # EXOS configure banner ends with a line containing only a period (.)
    banner_lines = EXOS_BANNER.split('\n')
    commands = ["configure banner"]
    commands.extend(banner_lines)
    commands.append(".")          # EXOS end-of-banner marker
    return commands


def deploy_banners(switch_dict):
    """Deploy banners to all switches in dict."""
    results = {}
    for name, sw_info in switch_dict.items():
        ip = sw_info["ip"]
        section(f"Deploying banner to {name} ({ip})")
        try:
            with EXOSSwitch(ip) as sw:
                # EXOS banner input is interactive — use send_command with timing
                # Send 'configure banner' then lines then '.'
                banner_lines = EXOS_BANNER.split('\n')

                # Start the banner prompt
                sw.conn.send_command_timing("configure banner")
                import time
                time.sleep(0.3)

                # Send each banner line
                for line in banner_lines:
                    sw.conn.send_command_timing(line if line else " ")
                    time.sleep(0.05)

                # End with a dot on its own line
                output = sw.conn.send_command_timing(".")
                time.sleep(0.3)

                sw.save()
                ok(f"Banner deployed on {name}")
                results[name] = {"success": True, "host": ip}

        except Exception as e:
            fail(f"{name}: {e}")
            results[name] = {"success": False, "error": str(e), "host": ip}

    return results


# ─── PFSENSE CONFIG GENERATOR ─────────────────────────────────────────────────

def generate_pfsense_banner_config():
    print("""
=============================================================
pfSense SSH Banner Configuration — Task 3
Apply manually via pfSense console shell (Option 8):
=============================================================

# Paste this block in pfSense shell:

cat > /etc/issue.net << 'BANNEREOF'
***********************************************
*                                             *
*   AUTHORIZED ACCESS ONLY                   *
*                                             *
*   This system is property of Bigfork IT.  *
*   All activity is monitored and logged.    *
*   Unauthorized access is strictly          *
*   prohibited. Disconnect now if you are    *
*   not an authorized user.                  *
*                                             *
***********************************************
BANNEREOF

# Enable the banner in sshd_config:
grep -q 'Banner /etc/issue.net' /etc/ssh/sshd_config || \\
    echo 'Banner /etc/issue.net' >> /etc/ssh/sshd_config

# Restart SSH:
/etc/rc.d/sshd onerestart

# Also set MOTD:
cat > /etc/motd << 'MOTDEOF'
Welcome to Bigfork IT Network Infrastructure.
This system is monitored. Authorized access only.
MOTDEOF

echo "pfSense banner configured."

=============================================================
Verify: ssh admin@10.10.10.1
Banner should appear BEFORE the password prompt.
=============================================================
""")


def generate_exos_banner_manual():
    """Print manual EXOS banner commands for switches that can't be reached via SSH."""
    print("""
=============================================================
Manual EXOS Banner Commands (via console if SSH unavailable)
=============================================================
Run on each switch console:

  configure banner
""")
    for line in EXOS_BANNER.split('\n'):
        print(f"  {line}")
    print("  .")
    print("""
  save configuration

=============================================================
""")


# ─── BANNER FILE WRITER ───────────────────────────────────────────────────────

def write_banner_files():
    """Write banner text files to disk for reference."""
    Path("standard_banner.txt").write_text(EXOS_BANNER)
    Path("ssh_banner.txt").write_text(PFSENSE_SSH_BANNER)
    Path("motd.txt").write_text(PFSENSE_MOTD)
    ok("Banner files written: standard_banner.txt, ssh_banner.txt, motd.txt")


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Task 3: Deploy login banners to EXOS switches")
    parser.add_argument("--hq-only",       action="store_true", help="HQ switches only")
    parser.add_argument("--branch-only",   action="store_true", help="Branch switch only")
    parser.add_argument("--generate-only", action="store_true", help="Print configs only, no SSH")
    parser.add_argument("--host",          help="Deploy to single switch IP")
    args = parser.parse_args()

    banner_print("Task 3 — Login Banner Deployment")

    write_banner_files()
    generate_pfsense_banner_config()
    generate_exos_banner_manual()

    if args.generate_only:
        info("Generate-only mode: no SSH connections made.")
        return

    # Determine target switches
    if args.host:
        targets = {args.host: {"ip": args.host, "role": "unknown"}}
    elif args.branch_only:
        targets = BRANCH_SWITCHES
    elif args.hq_only:
        targets = HQ_SWITCHES
    else:
        targets = {**HQ_SWITCHES, **BRANCH_SWITCHES}

    results = deploy_banners(targets)
    print_summary(results)

    report = {
        "timestamp": datetime.now().isoformat(),
        "task": "Task 3 — Login Banners",
        "results": results,
    }
    save_report(report, "task3_banner_report.json", "Task 3 report")


if __name__ == "__main__":
    main()
