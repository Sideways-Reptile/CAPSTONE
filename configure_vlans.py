#!/usr/bin/env python3
"""
Task 7: VLAN Configuration Automation
Creates VLANs and configures trunk ports on Cisco switches
Based on YAML inventory - uses SSH key authentication
"""

import yaml
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
import time
from typing import List, Dict
import json
from datetime import datetime
from pathlib import Path


class VLANConfigurator:
    """Automate VLAN configuration on Cisco switches from inventory"""
    
    def __init__(self, inventory_file: str = "vlan_inventory.yaml"):
        """
        Initialize configurator with inventory file
        
        Args:
            inventory_file: Path to YAML inventory file
        """
        self.inventory_file = inventory_file
        self.inventory = self._load_inventory()
        self.switches = self._extract_switches()
        
    def _load_inventory(self) -> Dict:
        """Load YAML inventory file"""
        
        with open(self.inventory_file, 'r') as f:
            inventory = yaml.safe_load(f)
        
        print(f"[+] Loaded inventory from {self.inventory_file}")
        return inventory
    
    def _extract_switches(self) -> List[Dict]:
        """Extract switch configuration from inventory"""
        
        switches = []
        
        # Navigate inventory structure
        cisco_switches = self.inventory['all']['children']['cisco_switches']
        
        # Get global vars
        global_vars = cisco_switches['vars']
        
        # Iterate through switch groups (core, distribution, access)
        for group_name, group_data in cisco_switches['children'].items():
            for hostname, host_data in group_data['hosts'].items():
                switch = {
                    'hostname': hostname,
                    'host': host_data['ansible_host'],
                    'role': host_data['role'],
                    'vlans': host_data.get('vlans', []),
                    'trunk_ports': host_data.get('trunk_ports', []),
                    'access_ports': host_data.get('access_ports', {}),
                    'device_type': 'cisco_ios',
                    'username': global_vars['ansible_user'],
                    'password': global_vars.get('ansible_password', 'sidewaays'),
                    'secret': global_vars.get('ansible_password', 'sidewaays'),
                }
                switches.append(switch)
        
        print(f"[+] Found {len(switches)} switches in inventory")
        return switches
    
    def _get_connection_params(self, switch: Dict) -> Dict:
        """Extract Netmiko connection parameters"""
        
        return {
            'device_type': switch['device_type'],
            'host': switch['host'],
            'username': switch['username'],
            'password': switch['password'],
            'secret': switch['secret'],
        }
    
    def generate_vlan_commands(self, vlan: Dict) -> List[str]:
        """Generate VLAN creation commands"""
        
        commands = [
            f"vlan {vlan['vlan_id']}",
            f"name {vlan['name']}",
        ]
        
        if 'description' in vlan:
            commands.append(f"exit")
            commands.append(f"description {vlan['description']}")
        
        commands.append("exit")
        
        return commands
    
    def generate_trunk_commands(self, port: str, vlan_list: List[int]) -> List[str]:
        """Generate trunk port configuration commands"""
        
        allowed_vlans = ",".join(str(v) for v in sorted(vlan_list))
        
        commands = [
            f"interface {port}",
            "switchport trunk encapsulation dot1q",
            "switchport mode trunk",
            f"switchport trunk allowed vlan {allowed_vlans}",
            "no shutdown",
            "exit"
        ]
        
        return commands
    
    def generate_access_commands(self, port: str, config: Dict) -> List[str]:
        """Generate access port configuration commands"""
        
        commands = [
            f"interface {port}",
            "switchport mode access",
            f"switchport access vlan {config['vlan']}",
        ]
        
        if 'description' in config:
            commands.append(f"description {config['description']}")
        
        commands.append("no shutdown")
        commands.append("exit")
        
        return commands
    
    def configure_switch(self, switch: Dict) -> Dict:
        """Configure VLANs and ports on a single switch"""
        
        result = {
            'hostname': switch['hostname'],
            'ip': switch['host'],
            'success': False,
            'vlans_created': [],
            'trunks_configured': [],
            'access_ports_configured': [],
            'output': '',
            'error': None
        }
        
        print(f"\n{'='*70}")
        print(f"Configuring {switch['hostname']} ({switch['host']})")
        print(f"Role: {switch['role']}")
        print(f"{'='*70}")
        
        try:
            # Connect to switch
            conn_params = self._get_connection_params(switch)
            connection = ConnectHandler(**conn_params)
            connection.enable()
            
            print(f"[+] Connected successfully (using password)")
            
            # Configure VLANs
            if switch['vlans']:
                print(f"\n[*] Configuring {len(switch['vlans'])} VLANs...")
                
                for vlan in switch['vlans']:
                    print(f"  [+] Creating VLAN {vlan['vlan_id']} ({vlan['name']})")
                    
                    commands = self.generate_vlan_commands(vlan)
                    output = connection.send_config_set(commands)
                    result['vlans_created'].append(vlan['vlan_id'])
                    result['output'] += f"\n=== VLAN {vlan['vlan_id']} ===\n{output}\n"
            
            # Configure trunk ports
            if switch['trunk_ports']:
                print(f"\n[*] Configuring {len(switch['trunk_ports'])} trunk ports...")
                
                # Get all VLAN IDs for trunk allowed list
                vlan_ids = [v['vlan_id'] for v in switch['vlans']]
                
                for port in switch['trunk_ports']:
                    print(f"  [+] Configuring trunk: {port}")
                    
                    commands = self.generate_trunk_commands(port, vlan_ids)
                    output = connection.send_config_set(commands)
                    result['trunks_configured'].append(port)
                    result['output'] += f"\n=== Trunk {port} ===\n{output}\n"
            
            # Configure access ports
            if switch['access_ports']:
                print(f"\n[*] Configuring {len(switch['access_ports'])} access ports...")
                
                for port, config in switch['access_ports'].items():
                    print(f"  [+] Configuring access port: {port} (VLAN {config['vlan']})")
                    
                    commands = self.generate_access_commands(port, config)
                    output = connection.send_config_set(commands)
                    result['access_ports_configured'].append(port)
                    result['output'] += f"\n=== Access {port} ===\n{output}\n"
            
            # Save configuration
            print(f"\n[+] Saving configuration...")
            save_output = connection.send_command('write memory')
            result['output'] += f"\n=== Save ===\n{save_output}\n"
            
            connection.disconnect()
            
            result['success'] = True
            print(f"\n[✓] {switch['hostname']} configured successfully!")
            
        except NetmikoTimeoutException:
            error = f"Timeout connecting to {switch['host']}"
            result['error'] = error
            print(f"\n[!] {error}")
            
        except NetmikoAuthenticationException:
            error = f"Authentication failed for {switch['host']} - check SSH keys"
            result['error'] = error
            print(f"\n[!] {error}")
            
        except Exception as e:
            error = str(e)
            result['error'] = error
            print(f"\n[!] Error: {error}")
        
        return result
    
    def verify_vlans(self, switch: Dict) -> Dict:
        """Verify VLAN configuration on a switch"""
        
        result = {
            'hostname': switch['hostname'],
            'vlans_found': [],
            'output': ''
        }
        
        print(f"\n[*] Verifying VLANs on {switch['hostname']}...")
        
        try:
            conn_params = self._get_connection_params(switch)
            connection = ConnectHandler(**conn_params)
            connection.enable()
            
            # Get VLAN info
            vlan_output = connection.send_command('show vlan brief')
            result['output'] = vlan_output
            
            # Parse VLANs from output
            for vlan in switch['vlans']:
                vlan_id = str(vlan['vlan_id'])
                if vlan_id in vlan_output:
                    result['vlans_found'].append(vlan['vlan_id'])
                    print(f"  [✓] VLAN {vlan_id} ({vlan['name']}) - Found")
                else:
                    print(f"  [!] VLAN {vlan_id} ({vlan['name']}) - NOT FOUND")
            
            # Get trunk info
            trunk_output = connection.send_command('show interfaces trunk')
            result['trunk_output'] = trunk_output
            
            print(f"\n  Trunk Ports:")
            for port in switch['trunk_ports']:
                if port in trunk_output:
                    print(f"    [✓] {port} - Trunking")
                else:
                    print(f"    [!] {port} - Not trunking")
            
            connection.disconnect()
            
        except Exception as e:
            print(f"  [!] Verification error: {e}")
            result['error'] = str(e)
        
        return result
    
    def configure_all(self) -> List[Dict]:
        """Configure VLANs on all switches"""
        
        print("\n" + "="*70)
        print("Task 7: VLAN Configuration Automation")
        print("="*70)
        print(f"\nInventory: {self.inventory_file}")
        print(f"Switches: {len(self.switches)}")
        print(f"Authentication: Password (case/sidewaays)")
        
        results = []
        
        # Configure each switch
        for switch in self.switches:
            result = self.configure_switch(switch)
            results.append(result)
            time.sleep(2)
        
        # Summary
        print("\n" + "="*70)
        print("Configuration Summary")
        print("="*70)
        
        success_count = sum(1 for r in results if r['success'])
        total_vlans = sum(len(r['vlans_created']) for r in results)
        total_trunks = sum(len(r['trunks_configured']) for r in results)
        
        print(f"\nSwitches Configured: {success_count}/{len(results)}")
        print(f"Total VLANs Created: {total_vlans}")
        print(f"Total Trunks Configured: {total_trunks}")
        
        if success_count < len(results):
            print("\n[!] Failed switches:")
            for r in results:
                if not r['success']:
                    print(f"  - {r['hostname']} ({r['ip']}): {r['error']}")
        
        return results
    
    def verify_all(self) -> List[Dict]:
        """Verify VLAN configuration on all switches"""
        
        print("\n" + "="*70)
        print("VLAN Verification")
        print("="*70)
        
        results = []
        
        for switch in self.switches:
            result = self.verify_vlans(switch)
            results.append(result)
            time.sleep(1)
        
        return results
    
    def generate_report(self, config_results: List, verify_results: List):
        """Generate deployment report"""
        
        report = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'task': 'Task 7 - VLAN Configuration',
            'inventory_file': self.inventory_file,
            'configuration': config_results,
            'verification': verify_results,
            'summary': {
                'total_switches': len(config_results),
                'configured': sum(1 for r in config_results if r['success']),
                'total_vlans': sum(len(r['vlans_created']) for r in config_results),
                'total_trunks': sum(len(r['trunks_configured']) for r in config_results),
            }
        }
        
        filename = 'task7_vlan_deployment_report.json'
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n[+] Report saved: {filename}")
        
        return report
    
    def display_topology(self):
        """Display VLAN topology"""
        
        print("\n" + "="*70)
        print("VLAN Topology")
        print("="*70)
        
        for switch in self.switches:
            print(f"\n{switch['hostname']} ({switch['role']}):")
            print(f"  VLANs:")
            for vlan in switch['vlans']:
                print(f"    - VLAN {vlan['vlan_id']}: {vlan['name']}")
            
            if switch['trunk_ports']:
                print(f"  Trunk Ports:")
                for port in switch['trunk_ports']:
                    print(f"    - {port}")
            
            if switch['access_ports']:
                print(f"  Access Ports:")
                for port, config in switch['access_ports'].items():
                    print(f"    - {port}: VLAN {config['vlan']}")


def main():
    """Main execution"""
    
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║          Task 7: VLAN & 802.1q Configuration                      ║
║                                                                   ║
║  Prerequisites:                                                   ║
║  • SSH keys configured on all switches                           ║
║  • vlan_inventory.yaml configured                                ║
║  • Network connectivity to switches                              ║
║                                                                   ║
║  This script will:                                                ║
║  1. Create VLANs on each switch                                  ║
║  2. Configure trunk ports (802.1q)                               ║
║  3. Configure access ports                                        ║
║  4. Verify configuration                                          ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    # Check for required modules
    try:
        from netmiko import ConnectHandler
        import yaml
    except ImportError as e:
        print(f"[!] Missing required module: {e}")
        print("[!] Install with: pip install netmiko pyyaml")
        return
    
    # Check inventory file exists
    inventory_file = "vlan_inventory.yaml"
    if not Path(inventory_file).exists():
        print(f"[!] Inventory file not found: {inventory_file}")
        print("[!] Create vlan_inventory.yaml first")
        return
    
    # Initialize configurator
    configurator = VLANConfigurator(inventory_file)
    
    # Display topology
    configurator.display_topology()
    
    # Confirm before proceeding
    print("\n" + "="*70)
    response = input("Proceed with VLAN configuration? (yes/no): ").lower()
    
    if response != 'yes':
        print("[!] Configuration cancelled")
        return
    
    # Configure all switches
    config_results = configurator.configure_all()
    
    # Wait for convergence
    print("\n[*] Waiting 10 seconds for network convergence...")
    time.sleep(10)
    
    # Verify configuration
    verify_results = configurator.verify_all()
    
    # Generate report
    configurator.generate_report(config_results, verify_results)
    
    print("\n" + "="*70)
    print("Task 7 VLAN Configuration Complete!")
    print("="*70)
    print("""
Next Steps:
1. Review task7_vlan_deployment_report.json
2. Verify VLANs: SSH to switches, run 'show vlan brief'
3. Verify trunks: Run 'show interfaces trunk'
4. Configure pfSense sub-interfaces (router-on-a-stick)
5. Test inter-VLAN routing
    """)


if __name__ == "__main__":
    main()
