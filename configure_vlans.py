#!/usr/bin/env python3
"""
Task 7 - EXOS VLAN Deployment Script v3
Incorporates all lessons learned:
  - enable ipforwarding on all VLANs
  - STP domain configuration per VLAN
  - correct VLAN naming (_NET suffix)
  - proper timeouts for EXOS commands
  - dry-run and single-switch modes

Usage:
  python3 configure_vlans.py              # full deploy all switches
  python3 configure_vlans.py --dry-run    # test SSH only
  python3 configure_vlans.py --switch SW1-CORE  # single switch
"""

import paramiko
import time
import json
import sys
import argparse
from datetime import datetime

# ── Switch Inventory ──────────────────────────────────────────────────────────
SWITCHES = [
    {"name": "SW1-CORE",   "host": "10.10.10.11", "role": "core",         "stp_priority": 4096},
    {"name": "SW2-DIST",   "host": "10.10.10.12", "role": "distribution", "stp_priority": None},
    {"name": "SW3-DIST",   "host": "10.10.10.13", "role": "distribution", "stp_priority": None},
    {"name": "SW4-ACCESS", "host": "10.10.10.14", "role": "access",       "stp_priority": None},
    {"name": "SW5-ACCESS", "host": "10.10.10.15", "role": "access",       "stp_priority": None},
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
            4: 40,                 # WS-Gst (GUEST_NET)
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

# ── Command timeouts ──────────────────────────────────────────────────────────
COMMAND_TIMEOUTS = {
    "save configuration": 8.0,
    "enable stpd":        3.0,
    "enable ssh2":        3.0,
    "enable sntp":        2.0,
    "enable syslog":      2.0,
    "default":            1.5,
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
            print(f"    Attempt {attempt}/{retries} failed: {e}")
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
            output += shell.recv(4096).decode("utf-8", errors="ignore")
            deadline = time.time() + 0.5
        else:
            time.sleep(0.1)
    return output


def clear_buffer(shell):
    time.sleep(1.5)
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


def build_commands(switch):
    """Build complete EXOS config commands for a switch."""
    name = switch["name"]
    cfg = PORT_CONFIG[name]
    stp_priority = switch["stp_priority"]
    commands = []

    # ── Create VLANs (MGMT_NET exists from bootstrap) ────────────────────
    for vlan in VLANS:
        if vlan["name"] != "MGMT_NET":
            commands.append(f"create vlan {vlan['name']} tag {vlan['id']}")

    # ── Tagged trunk ports ────────────────────────────────────────────────
    for port, vlan_ids in cfg["tagged"].items():
        for vid in vlan_ids:
            commands.append(f"configure vlan {VLAN_NAMES[vid]} add ports {port} tagged")

    # ── Untagged access ports ─────────────────────────────────────────────
    for port, vid in cfg["untagged"].items():
        commands.append(f"configure vlan {VLAN_NAMES[vid]} add ports {port} untagged")

    # ── IP Forwarding on all VLANs ────────────────────────────────────────
    for vlan in VLANS:
        commands.append(f"enable ipforwarding vlan {vlan['name']}")

    # ── STP - add all VLANs to stpd s0 ───────────────────────────────────
    commands.append("configure stpd s0 mode dot1w")
    if stp_priority:
        commands.append(f"configure stpd s0 priority {stp_priority}")
    for vlan in VLANS:
        commands.append(f"configure stpd s0 add vlan {vlan['name']} ports all")
    commands.append("enable stpd s0")

    # ── NTP ───────────────────────────────────────────────────────────────
    commands.append("configure sntp-client primary 10.10.10.1")
    commands.append("enable sntp-client")

    # ── Syslog ────────────────────────────────────────────────────────────
    commands.append("configure syslog add 10.10.10.1 local0")
    commands.append("enable syslog")

    # ── Save ──────────────────────────────────────────────────────────────
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
        print(f"  Connecting...")
        client = ssh_connect(host, USERNAME, PASSWORD)
        shell = client.invoke_shell()
        time.sleep(2.0)
        clear_buffer(shell)
        print(f"  Connected ✅")

        commands = build_commands(switch)
        print(f"  Sending {len(commands)} commands...\n")

        for i, cmd in enumerate(commands, 1):
            if verbose:
                print(f"  [{i:02d}/{len(commands)}] {cmd}", end="", flush=True)

            output = send_command(shell, cmd)

            is_warning = any(w in output for w in [
                "already exists", "already a member", "already enabled",
                "already configured", "already in stpd"
            ])
            is_error = any(e in output for e in [
                "Error:", "Invalid input", "Cannot", "Failed", "Unknown command"
            ])

            if is_warning:
                print(f" ⚠️  (already set - OK)") if verbose else None
            elif is_error:
                print(f" ❌") if verbose else None
                result["errors"].append(f"{cmd} → {output.strip()[:80]}")
            else:
                print(f" ✅") if verbose else None

            result["commands_sent"] += 1

        # ── Verify ───────────────────────────────────────────────────────
        print(f"\n  Verifying...")
        ping_gw = send_command(shell, "ping 10.10.10.1 count 3", wait=6.0)
        ping_sw1 = send_command(shell, "ping 10.10.10.11 count 3", wait=6.0)

        gw_ok  = "3 packets received" in ping_gw  or "bytes from 10.10.10.1"  in ping_gw
        sw1_ok = "3 packets received" in ping_sw1 or "bytes from 10.10.10.11" in ping_sw1

        if gw_ok and sw1_ok:
            result["status"] = "success"
            print(f"  ✅ Gateway reachable | ✅ SW1 reachable")
        elif gw_ok or sw1_ok:
            result["status"] = "partial"
            print(f"  ⚠️  Partial connectivity - check manually")
        else:
            result["status"] = "partial"
            print(f"  ⚠️  Ping inconclusive - check manually")

        client.close()

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(str(e))
        print(f"  ❌ FAILED: {e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="EXOS VLAN Deployment v3")
    parser.add_argument("--dry-run", action="store_true",
                        help="Test SSH connectivity only")
    parser.add_argument("--switch", type=str, default=None,
                        help="Single switch name e.g. --switch SW1-CORE")
    parser.add_argument("--quiet", action="store_true",
                        help="Reduce output verbosity")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  EXOS VLAN Deployment - Task 7 v3")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'FULL DEPLOY'}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    targets = SWITCHES
    if args.switch:
        targets = [s for s in SWITCHES if s["name"] == args.switch]
        if not targets:
            print(f"  ❌ Switch '{args.switch}' not found in inventory")
            sys.exit(1)
        print(f"  Targeting: {args.switch}")

    if args.dry_run:
        print("\n  Testing SSH connectivity...\n")
        results = [test_connectivity(s) for s in targets]
        passed = sum(results)
        print(f"\n  {passed}/{len(targets)} switches reachable via SSH")
        return 0 if all(results) else 1

    report = {
        "task": "Task 7 - EXOS VLAN & Trunking v3",
        "started": datetime.now().isoformat(),
        "results": [],
    }

    for switch in targets:
        result = deploy_switch(switch, verbose=not args.quiet)
        report["results"].append(result)
        time.sleep(2)

    # ── Summary ───────────────────────────────────────────────────────────
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
    print(f"  Report saved: {report_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
