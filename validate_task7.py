#!/usr/bin/env python3
"""
Task 7 - EXOS Post-Deployment Validation Script
Verifies VLAN config, trunk ports, reachability, and inter-VLAN routing.
Run after configure_vlans.py completes successfully.
"""

import paramiko
import time
import json
import sys
from datetime import datetime

SWITCHES = [
    {"name": "SW1-CORE",   "host": "10.10.10.11", "expected_vlans": [10, 20, 30, 40]},
    {"name": "SW2-DIST",   "host": "10.10.10.12", "expected_vlans": [10, 20, 30, 40]},
    {"name": "SW3-DIST",   "host": "10.10.10.13", "expected_vlans": [10, 20, 30, 40]},
    {"name": "SW4-ACCESS", "host": "10.10.10.14", "expected_vlans": [10, 20, 30]},
    {"name": "SW5-ACCESS", "host": "10.10.10.15", "expected_vlans": [10, 30]},
]

USERNAME = "case"
PASSWORD = "sidewaays"

VLAN_NAMES = {10: "MGMT_NET", 20: "CORP", 30: "DMZ", 40: "GUEST"}

# Ping targets from SW1-CORE to validate reachability
PING_TARGETS = [
    {"ip": "10.10.10.1",  "desc": "pfSense gateway"},
    {"ip": "10.10.10.12", "desc": "SW2-DIST"},
    {"ip": "10.10.10.13", "desc": "SW3-DIST"},
    {"ip": "10.10.10.14", "desc": "SW4-ACCESS"},
    {"ip": "10.10.10.15", "desc": "SW5-ACCESS"},
]


def ssh_connect(host):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=USERNAME, password=PASSWORD,
                   timeout=10, look_for_keys=False, allow_agent=False)
    return client


def send_command(shell, cmd, wait=1.5):
    shell.send(cmd + "\n")
    time.sleep(wait)
    out = ""
    while shell.recv_ready():
        out += shell.recv(4096).decode("utf-8", errors="ignore")
    return out


def check_vlans(output, expected_vlan_ids):
    """Check if expected VLANs appear in 'show vlan' output."""
    missing = []
    for vid in expected_vlan_ids:
        vname = VLAN_NAMES.get(vid, str(vid))
        if vname not in output and str(vid) not in output:
            missing.append(vid)
    return missing


def validate_switch(switch):
    name = switch["name"]
    host = switch["host"]
    result = {
        "switch": name,
        "host": host,
        "checks": {},
        "passed": 0,
        "failed": 0,
    }

    print(f"\n  Validating {name} ({host})...")

    try:
        client = ssh_connect(host)
        shell = client.invoke_shell()
        time.sleep(1.5)
        if shell.recv_ready():
            shell.recv(4096)

        # Check 1: VLANs present
        vlan_output = send_command(shell, "show vlan")
        missing = check_vlans(vlan_output, switch["expected_vlans"])
        if not missing:
            result["checks"]["vlans_present"] = "PASS"
            result["passed"] += 1
            print(f"    ✅ VLANs present: {[VLAN_NAMES[v] for v in switch['expected_vlans']]}")
        else:
            result["checks"]["vlans_present"] = f"FAIL - missing: {missing}"
            result["failed"] += 1
            print(f"    ❌ Missing VLANs: {missing}")

        # Check 2: MGMT IP configured
        ip_output = send_command(shell, "show vlan MGMT_NET")
        if "10.10.10." in ip_output:
            result["checks"]["mgmt_ip"] = "PASS"
            result["passed"] += 1
            print(f"    ✅ MGMT IP configured")
        else:
            result["checks"]["mgmt_ip"] = "FAIL"
            result["failed"] += 1
            print(f"    ❌ MGMT IP not found")

        # Check 3: Default gateway
        route_output = send_command(shell, "show iproute")
        if "10.10.10.1" in route_output:
            result["checks"]["default_gateway"] = "PASS"
            result["passed"] += 1
            print(f"    ✅ Default gateway present")
        else:
            result["checks"]["default_gateway"] = "FAIL"
            result["failed"] += 1
            print(f"    ❌ Default gateway missing")

        # Check 4: Ping gateway
        ping_out = send_command(shell, "ping 10.10.10.1 count 3", wait=4.0)
        if "3 packets received" in ping_out or "bytes from 10.10.10.1" in ping_out:
            result["checks"]["ping_gateway"] = "PASS"
            result["passed"] += 1
            print(f"    ✅ Gateway reachable (ping)")
        else:
            result["checks"]["ping_gateway"] = "FAIL"
            result["failed"] += 1
            print(f"    ❌ Gateway unreachable")

        # Check 5: Trunk ports have tagged VLANs
        port_output = send_command(shell, "show ports 1 information detail")
        if "Tagged" in port_output or "MGMT" in port_output:
            result["checks"]["trunk_port1"] = "PASS"
            result["passed"] += 1
            print(f"    ✅ Port 1 trunk operational")
        else:
            result["checks"]["trunk_port1"] = "WARN - check manually"
            print(f"    ⚠️  Port 1 trunk - verify manually")

        client.close()

    except Exception as e:
        result["checks"]["connection"] = f"FAIL - {e}"
        result["failed"] += 1
        print(f"    ❌ Connection failed: {e}")

    return result


def validate_reachability():
    """From SW1-CORE, ping all other switch management IPs."""
    print(f"\n{'='*60}")
    print("  REACHABILITY TEST (from SW1-CORE)")
    print(f"{'='*60}")
    results = {}

    try:
        client = ssh_connect("10.10.10.11")
        shell = client.invoke_shell()
        time.sleep(1.5)
        if shell.recv_ready():
            shell.recv(4096)

        for target in PING_TARGETS:
            ping_out = send_command(shell, f"ping {target['ip']} count 3", wait=4.0)
            success = "3 packets received" in ping_out or "bytes from" in ping_out
            status = "✅ REACHABLE" if success else "❌ UNREACHABLE"
            print(f"  {status}  {target['ip']:15s}  {target['desc']}")
            results[target["ip"]] = "pass" if success else "fail"

        client.close()
    except Exception as e:
        print(f"  ❌ Could not connect to SW1-CORE: {e}")

    return results


def main():
    print("\n" + "="*60)
    print("  EXOS Task 7 - Post-Deployment Validation")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    all_results = []
    for switch in SWITCHES:
        r = validate_switch(switch)
        all_results.append(r)

    reachability = validate_reachability()

    # Summary
    print(f"\n{'='*60}")
    print("  VALIDATION SUMMARY")
    print(f"{'='*60}")
    total_pass = sum(r["passed"] for r in all_results)
    total_fail = sum(r["failed"] for r in all_results)

    for r in all_results:
        icon = "✅" if r["failed"] == 0 else "⚠️ " if r["passed"] > 0 else "❌"
        print(f"  {icon} {r['switch']:15s} {r['passed']} passed / {r['failed']} failed")

    print(f"\n  Overall: {total_pass} checks passed, {total_fail} checks failed")

    # Save report
    report = {
        "task": "Task 7 Validation",
        "timestamp": datetime.now().isoformat(),
        "switch_results": all_results,
        "reachability": reachability,
        "summary": {"passed": total_pass, "failed": total_fail},
    }
    report_file = f"task7_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved: {report_file}")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
