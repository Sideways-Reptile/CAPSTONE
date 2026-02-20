#!/usr/bin/env python3
"""
pfSense Auto-Configuration Script
Configures interfaces, aliases, and firewall rules via:
  - Netmiko SSH   (Option 2 — replaces FauxAPI)
  - XML generation (Option 1 — no connection needed)
  - CLI commands   (Option 3 — copy-paste into console)

SSH prerequisites:
  1. Enable SSH on pfSense: System → Advanced → Admin Access → Enable Secure Shell
  2. Set admin shell to /bin/sh so SSH drops to shell (not the console menu):
       System → User Manager → admin → Shell → /bin/sh
  3. pip install netmiko
"""

import base64

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException


# ---------------------------------------------------------------------------
# SSH Configurator — Netmiko
# ---------------------------------------------------------------------------

class pfSenseSSHConfigurator:
    """Configure pfSense over SSH using Netmiko.

    PHP scripts are transferred via base64 to avoid all shell quoting issues:
        echo <base64_payload> | base64 -d | php
    """

    def __init__(self, host: str, username: str, password: str, port: int = 22):
        self.host = host
        self.device_params = {
            "device_type": "linux",   # pfSense is FreeBSD; 'linux' works fine for shell access
            "host": host,
            "username": username,
            "password": password,
            "port": port,
            "timeout": 30,
            "global_delay_factor": 2,
        }
        self.connection = None

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def connect(self):
        """Open SSH connection to pfSense."""
        print(f"\n[*] Connecting to pfSense at {self.host}:{self.device_params['port']}...")
        try:
            self.connection = ConnectHandler(**self.device_params)
            print("  ✓ SSH connection established")
        except NetmikoAuthenticationException:
            print("  [!] Authentication failed — check SSH credentials.")
            raise
        except NetmikoTimeoutException:
            print("  [!] Connection timed out — verify SSH is enabled on pfSense.")
            raise

    def disconnect(self):
        """Close SSH connection."""
        if self.connection:
            self.connection.disconnect()
            print("\n[*] SSH session closed")

    # ------------------------------------------------------------------
    # Low-level execution helpers
    # ------------------------------------------------------------------

    def _run_php(self, php_code: str) -> str:
        """Execute a PHP script on pfSense.

        Encodes the script as base64 and pipes it through php to avoid
        any shell quoting or escaping problems:
            echo <b64> | base64 -d | php
        """
        encoded = base64.b64encode(php_code.encode()).decode()
        return self.connection.send_command(
            f"echo {encoded} | base64 -d | php",
            read_timeout=30,
        )

    def _run_cmd(self, command: str, timeout: int = 30) -> str:
        """Run a plain shell command on pfSense."""
        return self.connection.send_command(command, read_timeout=timeout)

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
            ("wan",  "em0", "10.10.10.1",    "24", "MGMT"),
            ("lan",  "em1", "172.16.1.1",    "24", "CORP"),
            ("opt1", "em2", "192.168.100.1", "24", "DMZ"),
            ("opt2", "em3", "192.168.200.1", "24", "GUEST"),
            ("opt3", "em4", "dhcp",          "",   "WAN"),
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
            # MGMT gets full unrestricted access
            ("wan",  "pass",  "any", "NET_MGMT",  "any",         "MGMT Full Access",     "",   False),
            # CORP segment
            ("lan",  "pass",  "any", "NET_CORP",  "NET_DMZ",     "CORP to DMZ",          "",   False),
            ("lan",  "pass",  "any", "NET_CORP",  "NET_CORP",    "CORP Internal",        "",   False),
            ("lan",  "pass",  "any", "NET_CORP",  "any",         "CORP to Internet",     "",   False),
            # DMZ internal only
            ("opt1", "pass",  "any", "NET_DMZ",   "NET_DMZ",     "DMZ Internal",         "",   False),
            # GUEST — Task 2: block RFC1918 first, then allow DNS, then internet
            ("opt2", "block", "any", "NET_GUEST", "RFC1918_ALL", "GUEST Block RFC1918",  "",   True),
            ("opt2", "pass",  "udp", "NET_GUEST", "PUBLIC_DNS",  "GUEST Allow DNS",      "53", True),
            ("opt2", "pass",  "any", "NET_GUEST", "any",         "GUEST Allow Internet", "",   True),
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
        print("pfSense SSH Auto-Configuration (Netmiko)")
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
# XML Config Generator — no connection needed
# ---------------------------------------------------------------------------

class pfSenseXMLGenerator:
    """Generate a pfSense configuration XML file for manual import."""

    def generate_config_xml(self) -> str:
        """Generate complete pfSense configuration XML."""
        return """<?xml version="1.0"?>
<pfsense>
  <version>21.0</version>

  <!-- Aliases (Address Objects) -->
  <aliases>
    <alias>
      <name>NET_MGMT</name>
      <type>network</type>
      <address>10.10.10.0/24</address>
      <descr>Management Network</descr>
    </alias>
    <alias>
      <name>NET_CORP</name>
      <type>network</type>
      <address>172.16.1.0/24</address>
      <descr>Corporate Network</descr>
    </alias>
    <alias>
      <name>NET_DMZ</name>
      <type>network</type>
      <address>192.168.100.0/24</address>
      <descr>DMZ Network</descr>
    </alias>
    <alias>
      <name>NET_GUEST</name>
      <type>network</type>
      <address>192.168.200.0/24</address>
      <descr>Guest Network</descr>
    </alias>
    <alias>
      <name>RFC1918_ALL</name>
      <type>network</type>
      <address>10.0.0.0/8 172.16.0.0/12 192.168.0.0/16</address>
      <descr>All RFC1918 Private Networks</descr>
    </alias>
    <alias>
      <name>PUBLIC_DNS</name>
      <type>host</type>
      <address>8.8.8.8 8.8.4.4 1.1.1.1 1.0.0.1</address>
      <descr>Public DNS Servers</descr>
    </alias>
  </aliases>

  <!-- Interface Configuration -->
  <interfaces>
    <wan>
      <descr>MGMT</descr>
      <if>em0</if>
      <ipaddr>10.10.10.1</ipaddr>
      <subnet>24</subnet>
      <enable></enable>
    </wan>
    <lan>
      <descr>CORP</descr>
      <if>em1</if>
      <ipaddr>172.16.1.1</ipaddr>
      <subnet>24</subnet>
      <enable></enable>
    </lan>
    <opt1>
      <descr>DMZ</descr>
      <if>em2</if>
      <ipaddr>192.168.100.1</ipaddr>
      <subnet>24</subnet>
      <enable></enable>
    </opt1>
    <opt2>
      <descr>GUEST</descr>
      <if>em3</if>
      <ipaddr>192.168.200.1</ipaddr>
      <subnet>24</subnet>
      <enable></enable>
    </opt2>
    <opt3>
      <descr>WAN</descr>
      <if>em4</if>
      <ipaddr>dhcp</ipaddr>
      <enable></enable>
    </opt3>
  </interfaces>

  <!-- Firewall Rules -->
  <filter>
    <rule>
      <type>pass</type>
      <interface>wan</interface>
      <ipprotocol>inet</ipprotocol>
      <protocol>any</protocol>
      <source><network>NET_MGMT</network></source>
      <destination><any/></destination>
      <descr>MGMT Full Access</descr>
      <log></log>
    </rule>
    <rule>
      <type>pass</type>
      <interface>lan</interface>
      <ipprotocol>inet</ipprotocol>
      <protocol>any</protocol>
      <source><network>NET_CORP</network></source>
      <destination><network>NET_DMZ</network></destination>
      <descr>CORP to DMZ</descr>
    </rule>
    <rule>
      <type>pass</type>
      <interface>lan</interface>
      <ipprotocol>inet</ipprotocol>
      <protocol>any</protocol>
      <source><network>NET_CORP</network></source>
      <destination><network>NET_CORP</network></destination>
      <descr>CORP Internal</descr>
    </rule>
    <rule>
      <type>pass</type>
      <interface>lan</interface>
      <ipprotocol>inet</ipprotocol>
      <protocol>any</protocol>
      <source><network>NET_CORP</network></source>
      <destination><any/></destination>
      <descr>CORP to Internet</descr>
      <log></log>
    </rule>
    <rule>
      <type>pass</type>
      <interface>opt1</interface>
      <ipprotocol>inet</ipprotocol>
      <protocol>any</protocol>
      <source><network>NET_DMZ</network></source>
      <destination><network>NET_DMZ</network></destination>
      <descr>DMZ Internal</descr>
    </rule>
    <!-- Task 2: GUEST rules — block RFC1918 MUST be first -->
    <rule>
      <type>block</type>
      <interface>opt2</interface>
      <ipprotocol>inet</ipprotocol>
      <protocol>any</protocol>
      <source><network>NET_GUEST</network></source>
      <destination><network>RFC1918_ALL</network></destination>
      <descr>Task 2: GUEST Block All Internal Networks (RFC1918)</descr>
      <log></log>
    </rule>
    <rule>
      <type>pass</type>
      <interface>opt2</interface>
      <ipprotocol>inet</ipprotocol>
      <protocol>udp</protocol>
      <source><network>NET_GUEST</network></source>
      <destination><network>PUBLIC_DNS</network><port>53</port></destination>
      <descr>Task 2: GUEST Allow DNS Queries Only</descr>
      <log></log>
    </rule>
    <rule>
      <type>pass</type>
      <interface>opt2</interface>
      <ipprotocol>inet</ipprotocol>
      <protocol>any</protocol>
      <source><network>NET_GUEST</network></source>
      <destination><any/></destination>
      <descr>Task 2: GUEST Allow Internet Access Only</descr>
      <log></log>
    </rule>
  </filter>

  <!-- Outbound NAT -->
  <nat>
    <outbound>
      <mode>automatic</mode>
    </outbound>
  </nat>

</pfsense>
"""

    def save_config(self, filename: str = "pfsense-autoconfig.xml"):
        """Save generated XML to a file."""
        with open(filename, "w") as f:
            f.write(self.generate_config_xml())
        print(f"[+] Configuration saved to {filename}")
        print("\nTo apply:")
        print("  1. Login to pfSense GUI")
        print("  2. Diagnostics → Backup & Restore")
        print("  3. Upload this XML file and restore")
        print("  4. pfSense will reboot with the new config")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("pfSense Configuration Options")
    print("=" * 70)
    print("\n1. Generate XML config file  (no connection needed)")
    print("2. Configure via SSH          (Netmiko — live push to pfSense)")
    print("3. Generate CLI commands      (copy-paste into pfSense console)")

    choice = input("\nSelect option (1-3): ").strip()

    if choice == "1":
        print("\n[*] Generating XML configuration file...")
        generator = pfSenseXMLGenerator()
        generator.save_config()

    elif choice == "2":
        print("\n[*] SSH Configuration — Netmiko")
        print("[!] Prerequisites:")
        print("    - SSH enabled: System → Advanced → Admin Access → Enable Secure Shell")
        print("    - Shell set to /bin/sh: System → User Manager → admin → Shell → /bin/sh")
        print()
        host     = input("pfSense IP   [10.10.10.1]: ").strip() or "10.10.10.1"
        username = input("SSH Username [admin]:       ").strip() or "admin"
        password = input("SSH Password:              ").strip()
        port_in  = input("SSH Port     [22]:         ").strip()
        port     = int(port_in) if port_in else 22

        configurator = pfSenseSSHConfigurator(host, username, password, port)
        configurator.run_full_setup()

    elif choice == "3":
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
