#!/usr/bin/env python3
"""
pfSense Auto-Configuration Script
Configures interfaces, aliases, and firewall rules via:
  - SSH / paramiko  (Option 1 — live push to pfSense)
  - CLI commands    (Option 2 — copy-paste into console)

SSH prerequisites:
  1. Enable SSH on pfSense: System → Advanced → Admin Access → Enable Secure Shell
  2. pip install paramiko
  (No shell change needed — paramiko exec_command bypasses the pfSense console menu)
"""

import base64

import paramiko


# ---------------------------------------------------------------------------
# SSH Configurator — paramiko
# ---------------------------------------------------------------------------

class pfSenseSSHConfigurator:
    """Configure pfSense over SSH using paramiko.

    Uses exec_command() instead of an interactive shell session, so there is
    no prompt detection involved — the approach that caused Netmiko's
    '[\$\#] not detected' error on pfSense's non-standard shell.

    PHP scripts are transferred via base64 to avoid all shell quoting issues:
        echo <base64_payload> | base64 -d | php
    """

    def __init__(self, host: str, username: str, password: str, port: int = 22):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = None

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def connect(self):
        """Open SSH connection to pfSense."""
        print(f"\n[*] Connecting to pfSense at {self.host}:{self.port}...")
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=30,
                look_for_keys=False,
                allow_agent=False,
            )
            print("  ✓ SSH connection established")
        except paramiko.AuthenticationException:
            print("  [!] Authentication failed — check SSH credentials.")
            raise
        except (paramiko.ssh_exception.NoValidConnectionsError, TimeoutError):
            print("  [!] Connection failed — verify SSH is enabled on pfSense.")
            raise

    def disconnect(self):
        """Close SSH connection."""
        if self.client:
            self.client.close()
            print("\n[*] SSH session closed")

    # ------------------------------------------------------------------
    # Low-level execution helpers
    # ------------------------------------------------------------------

    def _run_php(self, php_code: str) -> str:
        """Execute a PHP script on pfSense.

        Encodes the script as base64 and pipes it through php to avoid
        any shell quoting or escaping problems:
            echo <b64> | base64 -d | php

        exec_command() opens a fresh SSH channel per call with no
        interactive shell or prompt detection required.
        """
        encoded = base64.b64encode(php_code.encode()).decode()
        _, stdout, stderr = self.client.exec_command(
            f"echo {encoded} | base64 -d | php", timeout=30
        )
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        return f"STDERR: {err}\n{out}" if err else out

    def _run_cmd(self, command: str, timeout: int = 30) -> str:
        """Run a plain shell command on pfSense."""
        _, stdout, _ = self.client.exec_command(command, timeout=timeout)
        return stdout.read().decode().strip()

    # ------------------------------------------------------------------
    # Configuration tasks
    # ------------------------------------------------------------------

    def create_aliases(self):
        """Create network aliases (address objects) via PHP."""
        print("\n[*] Creating network aliases...")

        aliases = [
            ("NET_MGMT",    "network", "10.10.10.0/24",                            "Management Network"),
            ("NET_CORP",    "network", "172.16.1.0/24",                            "Corporate Network"),
            ("NET_DMZ",     "network", "192.168.100.0/24",                         "DMZ Network"),
            ("NET_GUEST",   "network", "192.168.200.0/24",                         "Guest Network"),
            ("RFC1918_ALL", "network", "10.0.0.0/8 172.16.0.0/12 192.168.0.0/16", "All RFC1918 Private Networks"),
            ("PUBLIC_DNS",  "host",    "8.8.8.8 8.8.4.4 1.1.1.1 1.0.0.1",        "Public DNS Servers"),
        ]

        for name, alias_type, address, descr in aliases:
            print(f"  [+] {name}")

            php = f"""<?php
require_once('config.gui.inc');
require_once('util.inc');
global $config;
if (!is_array($config['aliases']['alias'])) $config['aliases']['alias'] = [];
foreach ($config['aliases']['alias'] as $a) {{
    if ($a['name'] === '{name}') {{ echo "EXISTS\\n"; exit; }}
}}
$config['aliases']['alias'][] = [
    'name'    => '{name}',
    'type'    => '{alias_type}',
    'address' => '{address}',
    'descr'   => '{descr}',
    'detail'  => '',
];
write_config('SSH auto-config: alias {name}');
echo "OK\\n";
"""
            result = self._run_php(php)
            print(f"    -> {'already exists' if 'EXISTS' in result else 'created'}")

        print("  ✓ Aliases done")

    def configure_interface_ips(self):
        """Assign IP addresses to interfaces via PHP."""
        print("\n[*] Configuring interface IPs...")

        # (pfsense_key, physical_if, ip, subnet, description)
        interfaces = [
            ("wan",  "em0", "dhcp",          "",   "WAN"),
            ("lan",  "em1", "10.10.10.1",    "24", "MGMT"),
            ("opt1", "em2", "172.16.1.1",    "24", "CORP"),
            ("opt2", "em3", "192.168.100.1", "24", "DMZ"),
            ("opt3", "em4", "192.168.200.1", "24", "GUEST"),
        ]

        for key, iface, ipaddr, subnet, descr in interfaces:
            print(f"  [+] {key} / {descr} ({iface})")

            if ipaddr == "dhcp":
                php = f"""<?php
require_once('config.gui.inc');
global $config;
$config['interfaces']['{key}']['if']     = '{iface}';
$config['interfaces']['{key}']['ipaddr'] = 'dhcp';
$config['interfaces']['{key}']['descr']  = '{descr}';
$config['interfaces']['{key}']['enable'] = '';
write_config('SSH auto-config: interface {key}');
echo "OK\\n";
"""
            else:
                php = f"""<?php
require_once('config.gui.inc');
global $config;
$config['interfaces']['{key}']['if']     = '{iface}';
$config['interfaces']['{key}']['ipaddr'] = '{ipaddr}';
$config['interfaces']['{key}']['subnet'] = '{subnet}';
$config['interfaces']['{key}']['descr']  = '{descr}';
$config['interfaces']['{key}']['enable'] = '';
write_config('SSH auto-config: interface {key}');
echo "OK\\n";
"""
            result = self._run_php(php)
            print(f"    -> {'ok' if 'OK' in result else 'unexpected: ' + result.strip()}")

        print("  ✓ Interfaces configured")

    def create_firewall_rules(self):
        """Push firewall rules via PHP.

        Rule order matters in pfSense — they are evaluated top-to-bottom,
        first match wins. The GUEST block-RFC1918 rule must precede the
        GUEST internet-allow rule.
        """
        print("\n[*] Creating firewall rules...")

        # (interface, action, protocol, src_alias, dst_alias, descr, dst_port, log)
        rules = [
            # MGMT (lan/em1) — full unrestricted access
            ("lan",  "pass",  "any", "NET_MGMT",  "any",         "MGMT Full Access",     "",   False),
            # CORP (opt1/em2)
            ("opt1", "pass",  "any", "NET_CORP",  "NET_DMZ",     "CORP to DMZ",          "",   False),
            ("opt1", "pass",  "any", "NET_CORP",  "NET_CORP",    "CORP Internal",        "",   False),
            ("opt1", "pass",  "any", "NET_CORP",  "any",         "CORP to Internet",     "",   False),
            # DMZ (opt2/em3) — internal only
            ("opt2", "pass",  "any", "NET_DMZ",   "NET_DMZ",     "DMZ Internal",         "",   False),
            # GUEST (opt3/em4) — Task 2: block RFC1918 first, then allow DNS, then internet
            ("opt3", "block", "any", "NET_GUEST", "RFC1918_ALL", "GUEST Block RFC1918",  "",   True),
            ("opt3", "pass",  "udp", "NET_GUEST", "PUBLIC_DNS",  "GUEST Allow DNS",      "53", True),
            ("opt3", "pass",  "any", "NET_GUEST", "any",         "GUEST Allow Internet", "",   True),
        ]

        for iface, action, proto, src, dst, descr, dstport, log in rules:
            print(f"  [+] [{action.upper():5}] {descr}")

            src_php = "['any' => '']" if src == "any" else f"['network' => '{src}']"
            if dst == "any":
                dst_php = "['any' => '']"
            elif dstport:
                dst_php = f"['network' => '{dst}', 'port' => '{dstport}']"
            else:
                dst_php = f"['network' => '{dst}']"

            log_php = "'log' => ''," if log else ""

            php = f"""<?php
require_once('config.gui.inc');
require_once('util.inc');
global $config;
if (!is_array($config['filter']['rule'])) $config['filter']['rule'] = [];
$config['filter']['rule'][] = [
    'type'        => '{action}',
    'interface'   => '{iface}',
    'ipprotocol'  => 'inet',
    'protocol'    => '{proto}',
    'source'      => {src_php},
    'destination' => {dst_php},
    'descr'       => '{descr}',
    {log_php}
];
write_config('SSH auto-config: rule {descr}');
echo "OK\\n";
"""
            result = self._run_php(php)
            print(f"    -> {'ok' if 'OK' in result else 'unexpected: ' + result.strip()}")

        print("  ✓ Firewall rules created")

    def configure_nat(self):
        """Set outbound NAT to automatic mode."""
        print("\n[*] Configuring outbound NAT...")

        php = """<?php
require_once('config.gui.inc');
global $config;
if (!isset($config['nat']['outbound'])) $config['nat']['outbound'] = [];
$config['nat']['outbound']['mode'] = 'automatic';
write_config('SSH auto-config: outbound NAT automatic');
echo "OK\n";
"""
        result = self._run_php(php)
        print(f"  -> {'ok' if 'OK' in result else result.strip()}")
        print("  ✓ NAT configured")

    def apply_configuration(self):
        """Reload the pfSense packet filter to activate all changes."""
        print("\n[*] Applying configuration (reloading packet filter)...")
        result = self._run_cmd("pfSsh.php playback filter reload", timeout=60)
        print(f"  -> {result.strip() or 'filter reloaded'}")
        print("  ✓ Done")

    def run_full_setup(self):
        """Run the complete pfSense configuration sequence over SSH."""
        print("=" * 70)
        print("pfSense SSH Auto-Configuration (paramiko)")
        print("Task 1 + Task 2: Network Segmentation with Guest ACL")
        print("=" * 70)

        try:
            self.connect()
            self.create_aliases()
            self.configure_interface_ips()
            self.create_firewall_rules()
            self.configure_nat()
            self.apply_configuration()
        finally:
            self.disconnect()

        print("\n" + "=" * 70)
        print("✓ Configuration Complete!")
        print("=" * 70)
        print("\nVerify in pfSense GUI:")
        print("  https://10.10.10.1  →  Firewall → Aliases")
        print("  https://10.10.10.1  →  Firewall → Rules")
        print("  https://10.10.10.1  →  Status → System Logs → Firewall")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("pfSense Configuration Options")
    print("=" * 70)
    print("\n1. Configure via SSH  (paramiko — live push to pfSense)")
    print("2. Generate CLI commands  (copy-paste into pfSense console)")

    choice = input("\nSelect option (1-2): ").strip()

    if choice == "1":
        print("\n[*] SSH Configuration — paramiko")
        print("[!] Prerequisite: SSH enabled on pfSense:")
        print("    System → Advanced → Admin Access → Enable Secure Shell")
        print()
        host     = input("pfSense IP   [10.10.10.1]: ").strip() or "10.10.10.1"
        username = input("SSH Username [admin]:       ").strip() or "admin"
        password = input("SSH Password:              ").strip()
        port_in  = input("SSH Port     [22]:         ").strip()
        port     = int(port_in) if port_in else 22

        configurator = pfSenseSSHConfigurator(host, username, password, port)
        configurator.run_full_setup()

    elif choice == "2":
        print("\n[*] Generating CLI commands...")
        print("\n# Copy-paste these into the pfSense SSH console or shell:\n")
        print("""
# --- Aliases ---
pfSsh.php playback alias add NET_MGMT    network 10.10.10.0/24                            "Management Network"
pfSsh.php playback alias add NET_CORP    network 172.16.1.0/24                            "Corporate Network"
pfSsh.php playback alias add NET_DMZ     network 192.168.100.0/24                         "DMZ Network"
pfSsh.php playback alias add NET_GUEST   network 192.168.200.0/24                         "Guest Network"
pfSsh.php playback alias add RFC1918_ALL network "10.0.0.0/8 172.16.0.0/12 192.168.0.0/16" "RFC1918 Private"
pfSsh.php playback alias add PUBLIC_DNS  host    "8.8.8.8 8.8.4.4 1.1.1.1 1.0.0.1"       "Public DNS"

# --- Reload filter ---
pfSsh.php playback filter reload
        """)

    else:
        print("[!] Invalid selection.")


if __name__ == "__main__":
    main()
