#!/usr/bin/env python3
"""
Task 7 - EXOS VLAN Deployment Script v2
Fixes: longer timeouts, better error handling, dry-run mode, verbose output
Usage:
  python3 configure_vlans.py            # full deploy
  python3 configure_vlans.py --dry-run  # test SSH connectivity only
  python3 configure_vlans.py --switch SW1-CORE  # deploy to one switch only
"""

import paramiko
import time
import json
import sys
import argparse
from datetime import datetime

# ── Switch Inventory ──────────────────────────────────────────────────────────
SWITCHES = [
    {"name": "SW1-CORE",   "host": "10.10.10.11", "role": "core"},
    {"name": "SW2-DIST",   "host": "10.10.10.12", "role": "distribution"},
    {"name": "SW3-DIST",   "host": "10.10.10.13", "role": "distribution"},
    {"name": "SW4-ACCESS", "host": "10.10.10.14", "role": "access"},
    {"name": "SW5-ACCESS", "host": "10.10.10.15", "role": "access"},
]

USERNAME = "case"
PASSWORD = "sidewaays"

# ── VLAN Definitions ──────────────────────────────────────────────────────────
VLANS = [
    {"id": 10, "name": "MGMT_NET"},
    {"id": 20, "name": "CORP_NET"},
    {"id": 30, "name": "DMZ_NET"},
    {"id": 40, "name": "GUEST_NET"},
]

VLAN_NAMES = {v["id"]: v["name"] for v in VLANS}

# ── Per-switch port config ────────────────────────────────────────────────────
PORT_CONFIG = {
    "SW1-CORE": {
        "tagged": {
            1: [10, 20, 30, 40],   # trunk to pfSense
            2: [10, 20, 30, 40],   # trunk to SW2-DIST
            3: [10, 20, 30, 40],   # trunk to SW3-DIST
        },
        "untagged": {
            4: 10,                 # Lbu-WS01 admin workstation
        },
        "mgmt_ip": "10.10.10.11/24",
    },
    "SW2-DIST": {
        "tagged": {
            1: [10, 20, 30, 40],   # trunk to SW1-CORE
            2: [10, 20, 30],       # trunk to SW4-ACCESS
            3: [10, 20, 30],       # trunk to SW5-ACCESS (redundant)
        },
        "untagged": {},
        "mgmt_ip": "10.10.10.12/24",
    },
    "SW3-DIST": {
        "tagged": {
            1: [10, 20, 30, 40],   # trunk to SW1-CORE
            2: [10, 30, 40],       # trunk to SW5-ACCESS
            3: [10, 20, 30],       # trunk to SW4-ACCESS (redundant)
        },
        "untagged": {
            4: 40,                 # WS-Gst access port (GUEST_NET)
        },
        "mgmt_ip": "10.10.10.13/24",
    },
    "SW4-ACCESS": {
        "tagged": {
            1: [10, 20, 30],       # trunk to SW2-DIST
            2: [10, 20, 30],       # trunk to SW3-DIST (redundant)
        },
        "untagged": {
            3: 20,                 # WIN10-WS1 (CORP_NET)
            4: 20,                 # WIN10-WS2 (CORP_NET)
            5: 20,                 # PRINT-SVR1 (CORP_NET)
        },
        "mgmt_ip": "10.10.10.14/24",
    },
    "SW5-ACCESS": {
        "tagged": {
            1: [10, 30, 40],       # trunk to SW3-DIST
            2: [10, 20, 30],       # trunk to SW2-DIST (redundant)
        },
        "untagged": {
            3: 30,                 # FILE-SVR1 (DMZ_NET)
            4: 30,                 # extra DMZ host
        },
        "mgmt_ip": "10.10.10.15/24",
    },
}

# ── Command timeouts (seconds) ────────────────────────────────────────────────
COMMAND_TIMEOUTS = {
    "configure ssh2 key": 25.0,
    "save configuration": 8.0,
    "enable ssh2": 3.0,
    "default": 1.5,
}


def get_timeout(cmd):
    for key, timeout in COMMAND_TIMEOUTS.items():
        if key in cmd:
            return timeout
    return COMMAND_TIMEOUTS["default"]


def ssh_connect(host, username, password, retries=3):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for attempt in range(1, retries + 1):
        try:
            client.connect(
                hostname=host,
                username=username,
                password=password,
                timeout=15,
                look_for_keys=False,
                allow_agent=False,
            )
            return client
        except Exception as e:
            print(f"    Connection attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(3)
    raise ConnectionError(f"Could not connect to {host} after {retries} attempts")


def send_command(shell, command, wait=None):
    if wait is None:
        wait = get_timeout(command)
    shell.send(command + "\n")
    time.sleep(wait)
    output = ""
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if shell.recv_ready():
            chunk = shell.recv(4096).decode("utf-8", errors="ignore")
            output += chunk
            deadline = time.time() + 0.5
        else:
            time.sleep(0.1)
    return output


def clear_buffer(shell):
    time.sleep(1.0)
    while shell.recv_ready():
        shell.recv(4096)


def test_connectivity(switch):
    name = switch["name"]
    host = switch["host"]
    try:
        client = ssh_connect(host, USERNAME, PASSWORD, retries=2)
        client.close()
        print(f"  ✅ {name:15s} ({host}) - SSH OK")
        return True
    except Exception as e:
        print(f"  ❌ {name:15s} ({host}) - FAILED: {e}")
        return False


def build_commands(switch_name):
    cfg = PORT_CONFIG[switch_name]
    commands = []

    # Create VLANs (skip MGMT_NET - already exists from bootstrap)
    for vlan in VLANS:
        if vlan["name"] != "MGMT_NET":
            commands.append(f"create vlan {vlan['name']} tag {vlan['id']}")

    # Tagged trunk ports
    for port, vlan_ids in cfg["tagged"].items():
        for vid in vlan_ids:
            vname = VLAN_NAMES[vid]
            commands.append(f"configure vlan {vname} add ports {port} tagged")

    # Untagged access ports
    for port, vid in cfg["untagged"].items():
        vname = VLAN_NAMES[vid]
        commands.append(f"configure vlan {vname} add ports {port} untagged")

    # NTP
    commands.append("configure sntp-client primary 10.10.10.1")
    commands.append("enable sntp-client")

    # Syslog
    commands.append("configure syslog add 10.10.10.1 local0")
    commands.append("enable syslog")

    # Save
    commands.append("save configuration")

    return commands


def deploy_switch(switch, verbose=True):
    name = switch["name"]
    host = switch["host"]

    print(f"\n{'='*60}")
    print(f"  Deploying: {name} ({host})")
    print(f"{'='*60}")

    result = {
        "switch": name,
        "host": host,
        "status": "unknown",
        "commands_sent": 0,
        "errors": [],
        "timestamp": datetime.now().isoformat(),
    }

    try:
        print(f"  Connecting via SSH...")
        client = ssh_connect(host, USERNAME, PASSWORD)
        shell = client.invoke_shell()
        time.sleep(2.0)
        clear_buffer(shell)
        print(f"  Connected ✅")

        commands = build_commands(name)
        print(f"  Sending {len(commands)} commands...\n")

        for i, cmd in enumerate(commands, 1):
            timeout = get_timeout(cmd)
            if verbose:
                print(f"  [{i:02d}/{len(commands)}] {cmd}", end="", flush=True)

            output = send_command(shell, cmd, wait=timeout)

            has_error = any(err in output for err in [
                "Error:", "Invalid input", "Cannot", "Failed", "Unknown command"
            ])
            is_warning = "already exists" in output or "already a member" in output

            if is_warning:
                if verbose:
                    print(f" ⚠️  (already configured - OK)")
            elif has_error:
                if verbose:
                    print(f" ❌ ERROR")
                result["errors"].append(f"CMD: {cmd} | {output.strip()[:100]}")
            else:
                if verbose:
                    print(f" ✅")

            result["commands_sent"] += 1

        # Verify
        print(f"\n  Verifying gateway reachability...")
        ping_out = send_command(shell, "ping 10.10.10.1 count 3", wait=6.0)
        if "3 packets received" in ping_out or "bytes from 10.10.10.1" in ping_out:
            result["status"] = "success"
            print(f"  ✅ Gateway reachable")
        else:
            result["status"] = "partial"
            print(f"  ⚠️  Gateway ping inconclusive - check manually")

        client.close()

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(str(e))
        print(f"  ❌ FAILED: {e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="EXOS VLAN Deployment Script v2")
    parser.add_argument("--dry-run", action="store_true",
                        help="Test SSH connectivity only")
    parser.add_argument("--switch", type=str, default=None,
                        help="Deploy to single switch (e.g. --switch SW1-CORE)")
    parser.add_argument("--quiet", action="store_true",
                        help="Reduce verbosity")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  EXOS VLAN Deployment - Task 7 v2")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'FULL DEPLOY'}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    targets = SWITCHES
    if args.switch:
        targets = [s for s in SWITCHES if s["name"] == args.switch]
        if not targets:
            print(f"  ❌ Switch '{args.switch}' not found")
            sys.exit(1)
        print(f"  Targeting: {args.switch}")

    if args.dry_run:
        print("\n  Testing SSH connectivity...\n")
        results = [test_connectivity(s) for s in targets]
        passed = sum(results)
        print(f"\n  {passed}/{len(targets)} switches reachable")
        return 0 if all(results) else 1

    report = {
        "task": "Task 7 - EXOS VLAN & Trunking v2",
        "started": datetime.now().isoformat(),
        "results": [],
    }

    for switch in targets:
        result = deploy_switch(switch, verbose=not args.quiet)
        report["results"].append(result)
        time.sleep(2)

    print(f"\n{'='*60}")
    print("  DEPLOYMENT SUMMARY")
    print(f"{'='*60}")

    success = sum(1 for r in report["results"] if r["status"] == "success")
    partial = sum(1 for r in report["results"] if r["status"] == "partial")
    failed  = sum(1 for r in report["results"] if r["status"] == "failed")

    for r in report["results"]:
        icon = {"success": "✅", "partial": "⚠️ ", "failed": "❌"}.get(r["status"], "?")
        print(f"  {icon} {r['switch']:15s} {r['host']:15s} {r['status']}")
        if r["errors"]:
            for err in r["errors"][:3]:
                print(f"       → {err[:80]}")

    print(f"\n  Total: {success} success | {partial} partial | {failed} failed")

    report["completed"] = datetime.now().isoformat()
    report_file = f"task7_deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Report: {report_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
