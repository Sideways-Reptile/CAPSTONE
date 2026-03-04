#!/usr/bin/env python3
"""
Task 5: Automated STP Configuration
Configures Rapid Spanning Tree Protocol (802.1w) on Cisco switches via SSH
"""

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
import time
from typing import List, Dict
import json


class STPConfigurator:
    """Automate STP configuration on Cisco switches"""
    
    def __init__(self):
        self.switches = [
            {
                'device_type': 'cisco_ios',
                'host': '10.10.10.11',
                'username': 'admin',
                'password': 'Admin123!',
                'secret': 'Admin123!',
                'hostname': 'SW1-CORE',
                'priority': 4096,
                'role': 'Root Bridge'
            },
            {
                'device_type': 'cisco_ios',
                'host': '10.10.10.12',
                'username': 'admin',
                'password': 'Admin123!',
                'secret': 'Admin123!',
                'hostname': 'SW2-CORP',
                'priority': 8192,
                'role': 'Distribution'
            },
            {
                'device_type': 'cisco_ios',
                'host': '10.10.10.13',
                'username': 'admin',
                'password': 'Admin123!',
                'secret': 'Admin123!',
                'hostname': 'SW3-DMZ',
                'priority': 32768,
                'role': 'Access'
            }
        ]
    
    def generate_stp_config(self, switch: Dict) -> List[str]:
        """Generate STP configuration commands"""
        
        commands = [
            # Enable Rapid Spanning Tree
            'spanning-tree mode rapid-pvst',
            
            # Set priority for VLAN 1
            f'spanning-tree vlan 1 priority {switch["priority"]}',
            
            # Enable all interfaces
            'interface range GigabitEthernet0/0 - 3',
            'no shutdown',
            'switchport mode access',
            'exit',
            
            # Enable logging for STP events
            'logging console informational',
            'logging monitor informational',
        ]
        
        # Add PortFast to access ports (only for access switches)
        if switch['role'] == 'Access':
            commands.extend([
                'interface GigabitEthernet0/3',
                'spanning-tree portfast',
                'description Access port to end devices',
                'exit'
            ])
        
        return commands
    
    def configure_switch(self, switch: Dict) -> Dict:
        """Configure a single switch via SSH"""
        
        result = {
            'hostname': switch['hostname'],
            'ip': switch['host'],
            'success': False,
            'output': '',
            'error': None
        }
        
        print(f"\n[*] Configuring {switch['hostname']} ({switch['host']})...")
        
        try:
            # Connect to switch
            connection = ConnectHandler(**switch)
            
            # Enter enable mode
            connection.enable()
            
            # Get configuration commands
            commands = self.generate_stp_config(switch)
            
            # Send configuration
            output = connection.send_config_set(commands)
            result['output'] = output
            
            # Save configuration
            save_output = connection.send_command('write memory')
            result['output'] += f"\n{save_output}"
            
            # Disconnect
            connection.disconnect()
            
            result['success'] = True
            print(f"  [+] {switch['hostname']} configured successfully")
            
        except NetmikoTimeoutException:
            error = f"Timeout connecting to {switch['host']}"
            result['error'] = error
            print(f"  [!] {error}")
            
        except NetmikoAuthenticationException:
            error = f"Authentication failed for {switch['host']}"
            result['error'] = error
            print(f"  [!] {error}")
            
        except Exception as e:
            error = str(e)
            result['error'] = error
            print(f"  [!] Error: {error}")
        
        return result
    
    def verify_stp(self, switch: Dict) -> Dict:
        """Verify STP configuration on a switch"""
        
        result = {
            'hostname': switch['hostname'],
            'ip': switch['host'],
            'is_root': False,
            'priority': None,
            'blocked_ports': [],
            'output': ''
        }
        
        print(f"\n[*] Verifying STP on {switch['hostname']}...")
        
        try:
            connection = ConnectHandler(**switch)
            connection.enable()
            
            # Get STP summary
            stp_output = connection.send_command('show spanning-tree summary')
            result['output'] = stp_output
            
            # Check if root bridge
            stp_root = connection.send_command('show spanning-tree root')
            if 'This bridge is the root' in stp_root:
                result['is_root'] = True
                print(f"  [+] {switch['hostname']} is the ROOT BRIDGE")
            else:
                print(f"  [+] {switch['hostname']} is NOT root")
            
            # Get blocked ports
            blocked_output = connection.send_command('show spanning-tree blockedports')
            result['blocked_ports'] = blocked_output
            
            if 'No blocked ports' not in blocked_output:
                print(f"  [+] Has blocked ports (redundant paths detected)")
            
            connection.disconnect()
            
        except Exception as e:
            print(f"  [!] Verification error: {e}")
            result['error'] = str(e)
        
        return result
    
    def configure_all(self):
        """Configure STP on all switches"""
        print("=" * 70)
        print("Automated STP Configuration - Task 5")
        print("=" * 70)
        
        results = []
        
        # Configure each switch
        for switch in self.switches:
            result = self.configure_switch(switch)
            results.append(result)
            time.sleep(2)  # Brief pause between switches
        
        # Summary
        print("\n" + "=" * 70)
        print("Configuration Summary")
        print("=" * 70)
        
        success_count = sum(1 for r in results if r['success'])
        print(f"\nTotal Switches: {len(results)}")
        print(f"Successful: {success_count}")
        print(f"Failed: {len(results) - success_count}")
        
        if success_count < len(results):
            print("\nFailed switches:")
            for r in results:
                if not r['success']:
                    print(f"  - {r['hostname']} ({r['ip']}): {r['error']}")
        
        return results
    
    def verify_all(self):
        """Verify STP on all switches"""
        print("\n" + "=" * 70)
        print("STP Verification")
        print("=" * 70)
        
        results = []
        
        for switch in self.switches:
            result = self.verify_stp(switch)
            results.append(result)
            time.sleep(1)
        
        # Check for root bridge
        root_bridges = [r for r in results if r.get('is_root')]
        
        print("\n" + "=" * 70)
        print("Verification Summary")
        print("=" * 70)
        
        if len(root_bridges) == 1:
            print(f"\n✓ Single root bridge detected: {root_bridges[0]['hostname']}")
        elif len(root_bridges) == 0:
            print("\n✗ No root bridge detected - STP may not be working!")
        else:
            print(f"\n✗ Multiple root bridges detected - STP configuration error!")
        
        return results
    
    def generate_report(self, config_results: List, verify_results: List):
        """Generate deployment report"""
        
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'task': 'Task 5 - STP Configuration',
            'configuration': config_results,
            'verification': verify_results,
            'summary': {
                'total_switches': len(config_results),
                'configured': sum(1 for r in config_results if r['success']),
                'root_bridge': next((r['hostname'] for r in verify_results if r.get('is_root')), 'None')
            }
        }
        
        with open('stp_deployment_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print("\n[+] Report saved: stp_deployment_report.json")


def main():
    """Main execution"""
    
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║          Task 5: Automated STP Configuration                      ║
║                                                                   ║
║  Prerequisites:                                                   ║
║  • Switches have management IPs configured                       ║
║  • SSH is enabled on all switches                                ║
║  • Switches are reachable from this host                         ║
║                                                                   ║
║  This script will:                                                ║
║  1. Enable Rapid Spanning Tree (802.1w)                          ║
║  2. Set root bridge priority                                     ║
║  3. Configure interfaces                                          ║
║  4. Verify STP operation                                          ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    # Check for netmiko
    try:
        from netmiko import ConnectHandler
    except ImportError:
        print("[!] Missing required module: netmiko")
        print("[!] Install with: pip install netmiko")
        return
    
    configurator = STPConfigurator()
    
    # Configure all switches
    config_results = configurator.configure_all()
    
    # Wait for STP to converge
    print("\n[*] Waiting for STP convergence (10 seconds)...")
    time.sleep(10)
    
    # Verify configuration
    verify_results = configurator.verify_all()
    
    # Generate report
    configurator.generate_report(config_results, verify_results)
    
    print("\n" + "=" * 70)
    print("Task 5 Complete!")
    print("=" * 70)
    print("""
Next steps:
1. Review stp_deployment_report.json
2. Manually verify: ssh admin@10.10.10.11
   Run: show spanning-tree
3. Test link failure convergence
4. Document topology for client demo
    """)


if __name__ == "__main__":
    main()
