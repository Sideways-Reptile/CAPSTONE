#!/usr/bin/env python3
"""
Task 7 - EXOS VLAN Deployment Script
Connects to all 5 EXOS switches via SSH and deploys VLAN + trunk config.
Uses paramiko for SSH. Run from host (10.10.10.104) on MGMT network.

Install deps: pip3 install paramiko
"""

import paramiko
import time
import json
import sys
from datetime import datetime

# ── Switch Inventory ──────────────────────────────────────────────────────────
SWITCHES = [
    {
        "name": "SW1-CORE",
        "host": "10.10.10.11",
        "role": "core",
    },
    {
        "name": "SW2-DIST",
        "host": "10.10.10.12",
        "role": "distribution",
    },
    {
        "name": "SW3-DIST",
        "host": "10.10.10.13",
        "role": "distribution",
    },
    {
        "name": "SW4-ACCESS",
        "host": "10.10.10.14",
        "role": "access",
    },
    {
        "name": "SW5-ACCESS",
        "host": "10.10.10.15",
        "role": "access",
    },
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

# ── Per-switch port config ────────────────────────────────────────────────────
PORT_CONFIG = {
    "SW1-CORE": {
        "tagged": {
            1: [10, 20, 30, 40],   # trunk to pfSense
            2: [10, 20, 30, 40],   # trunk to SW2-DIST
            3: [10, 20, 30, 40],   # trunk to SW3-DIST
        },
        "untagged": {
            4: 10,                 # Lbu-WS01 admin workstation (MGMT)
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
            4: 40,                 # WS-Gst access port (GUEST)
        },
        "mgmt_ip": "10.10.10.13/24",
    },
    "SW4-ACCESS": {
        "tagged": {
            1: [10, 20, 30],       # trunk to SW2-DIST
            2: [10, 20, 30],       # trunk to SW3-DIST (redundant)
        },
        "untagged": {
            3: 20,                 # WIN10-WS1 (CORP)
            4: 20,                 # WIN10-WS2 (CORP)
            5: 20,                 # PRINT-SVR1 (CORP)
        },
        "mgmt_ip": "10.10.10.14/24",
    },
    "SW5-ACCESS": {
        "tagged": {
            1: [10, 30, 40],       # trunk to SW3-DIST
            2: [10, 20, 30],       # trunk to SW2-DIST (redundant)
        },
        "untagged": {
            3: 30,                 # FILE-SVR1 (DMZ)
            4: 30,                 # Lbu-WS01 (DMZ)
        },
        "mgmt_ip": "10.10.10.15/24",
    },
}

# ── VLAN name lookup ──────────────────────────────────────────────────────────
VLAN_NAMES = {v["id"]: v["name"] for v in VLANS}


def ssh_connect(host, username, password):
    """Open SSH connection to EXOS switch."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username=username,
        password=password,
        timeout=10,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


def send_command(shell, command, wait=1.0):
    """Send a command and return output."""
    shell.send(command + "\n")
    time.sleep(wait)
    output = ""
    while shell.recv_ready():
        output += shell.recv(4096).decode("utf-8", errors="ignore")
    return output


def build_commands(switch_name):
    """Build EXOS config commands for a given switch."""
    cfg = PORT_CONFIG[switch_name]
    commands = []

    # Create VLANs
    for vlan in VLANS:
        commands.append(f"create vlan {vlan['name']} tag {vlan['id']}")

    # Remove all ports from Default VLAN
    commands.append("configure vlan Default delete ports all")

    # Tagged (trunk) ports
    for port, vlan_ids in cfg["tagged"].items():
        for vid in vlan_ids:
            vname = VLAN_NAMES[vid]
            commands.append(f"configure vlan {vname} add ports {port} tagged")

    # Untagged (access) ports
    for port, vid in cfg["untagged"].items():
        vname = VLAN_NAMES[vid]
        commands.append(f"configure vlan {vname} add ports {port} untagged")

    # Management IP
    commands.append(f"configure vlan MGMT_NET ipaddress {cfg['mgmt_ip']}")

    # Default gateway
    commands.append("configure iproute add default 10.10.10.1")

    # Enable SSH
    commands.append("enable ssh2")

    # NTP
    commands.append("configure sntp-client primary 10.10.10.1")
    commands.append("enable sntp-client")

    # Syslog
    commands.append("configure syslog add 10.10.10.1 local0")
    commands.append("enable syslog")

    # Save
    commands.append("save configuration primary")

    return commands


def verify_switch(shell):
    """Run verification checks, return dict of results."""
    results = {}
    results["vlan_brief"] = send_command(shell, "show vlan", wait=1.5)
    results["ports"] = send_command(shell, "show ports information", wait=1.5)
    results["iproute"] = send_command(shell, "show iproute", wait=1.0)
    results["ping_gateway"] = send_command(shell, "ping 10.10.10.1 count 3", wait=3.0)
    results["ping_core"] = send_command(shell, "ping 10.10.10.11 count 3", wait=3.0)
    return results


def deploy_switch(switch):
    """Deploy config to a single switch."""
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
        "verification": {},
        "timestamp": datetime.now().isoformat(),
    }

    try:
        client = ssh_connect(host, USERNAME, PASSWORD)
        shell = client.invoke_shell()
        time.sleep(1.5)
        # Clear banner/initial output
        if shell.recv_ready():
            shell.recv(4096)

        commands = build_commands(name)
        print(f"  Sending {len(commands)} commands...")

        for cmd in commands:
            output = send_command(shell, cmd, wait=0.5)
            print(f"  > {cmd}")
            # Basic error detection
            if "Error" in output or "Invalid" in output:
                result["errors"].append(f"CMD: {cmd} | OUTPUT: {output.strip()}")

        result["commands_sent"] = len(commands)

        print(f"\n  Running verification...")
        result["verification"] = verify_switch(shell)

        # Check ping success
        gw_ping = result["verification"].get("ping_gateway", "")
        if "3 packets received" in gw_ping or "bytes from" in gw_ping:
            result["status"] = "success"
            print(f"  ✅ {name} - GATEWAY REACHABLE")
        else:
            result["status"] = "partial"
            print(f"  ⚠️  {name} - Gateway ping inconclusive, check manually")

        client.close()

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(str(e))
        print(f"  ❌ {name} - FAILED: {e}")

    return result


def main():
    print("\n" + "="*60)
    print("  EXOS VLAN Deployment - Task 7")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    report = {
        "task": "Task 7 - EXOS VLAN & Trunking",
        "started": datetime.now().isoformat(),
        "results": [],
    }

    # Deploy to each switch
    for switch in SWITCHES:
        result = deploy_switch(switch)
        report["results"].append(result)

    # Summary
    print("\n" + "="*60)
    print("  DEPLOYMENT SUMMARY")
    print("="*60)
    success = sum(1 for r in report["results"] if r["status"] == "success")
    partial = sum(1 for r in report["results"] if r["status"] == "partial")
    failed  = sum(1 for r in report["results"] if r["status"] == "failed")

    for r in report["results"]:
        icon = {"success": "✅", "partial": "⚠️ ", "failed": "❌"}.get(r["status"], "?")
        print(f"  {icon} {r['switch']:15s} {r['host']:15s} {r['status']}")
        if r["errors"]:
            for err in r["errors"]:
                print(f"       ERROR: {err}")

    print(f"\n  Total: {success} success | {partial} partial | {failed} failed")

    # Save report
    report["completed"] = datetime.now().isoformat()
    report_file = f"task7_deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved: {report_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
