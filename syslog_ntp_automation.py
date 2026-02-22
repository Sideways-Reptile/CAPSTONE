#!/usr/bin/env python3
"""
Task 6: Syslog & NTP Configuration Automation
Configures centralized logging and time synchronization on network devices
"""

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
import time
from typing import List, Dict
import json
from datetime import datetime


class SyslogNTPConfigurator:
    """Automate syslog and NTP configuration on Cisco switches"""
    
    def __init__(self, syslog_server: str = "10.10.10.1", ntp_server: str = "10.10.10.1"):
        self.syslog_server = syslog_server
        self.ntp_server = ntp_server
        
        self.switches = [
            {
                'device_type': 'cisco_ios',
                'host': '10.10.10.11',
                'username': 'case',
                'password': 'sidewaays',
                'secret': 'sidewaays',
                'hostname': 'SW1-CORE',
            },
            {
                'device_type': 'cisco_ios',
                'host': '10.10.10.12',
                'username': 'case',
                'password': 'sidewaays',
                'secret': 'sidewaays',
                'hostname': 'SW2-CORP',
            },
            {
                'device_type': 'cisco_ios',
                'host': '10.10.10.13',
                'username': 'case',
                'password': 'sidewaays',
                'secret': 'sidewaays',
                'hostname': 'SW3-DMZ',
            }
        ]
    
    def _get_connection_params(self, switch: Dict) -> Dict:
        """Extract only Netmiko connection parameters"""
        return {k: v for k, v in switch.items() if k != 'hostname'}
    
    def generate_syslog_config(self) -> List[str]:
        """Generate syslog configuration commands"""
        
        commands = [
            f'logging host {self.syslog_server}',
            'logging trap informational',
            'logging facility local7',
            'logging source-interface vlan 1',
            'logging buffered 51200 informational',
            'service timestamps log datetime msec localtime show-timezone',
            'service sequence-numbers',
        ]
        
        return commands
    
    def generate_ntp_config(self, timezone: str = "EST", offset: int = -5) -> List[str]:
        """Generate NTP configuration commands"""
        
        commands = [
            f'ntp server {self.ntp_server}',
            'ntp source vlan 1',
            f'clock timezone {timezone} {offset}',
            'service timestamps debug datetime msec localtime show-timezone',
        ]
        
        return commands
    
    def configure_switch(self, switch: Dict) -> Dict:
        """Configure syslog and NTP on a single switch"""
        
        result = {
            'hostname': switch['hostname'],
            'ip': switch['host'],
            'success': False,
            'syslog_configured': False,
            'ntp_configured': False,
            'output': '',
            'error': None
        }
        
        print(f"\n[*] Configuring {switch['hostname']} ({switch['host']})...")
        
        try:
            # Connect to switch
            conn_params = self._get_connection_params(switch)
            connection = ConnectHandler(**conn_params)
            connection.enable()
            
            # Configure syslog
            print(f"  [+] Configuring syslog...")
            syslog_commands = self.generate_syslog_config()
            syslog_output = connection.send_config_set(syslog_commands)
            result['output'] += "=== Syslog Configuration ===\n" + syslog_output + "\n"
            result['syslog_configured'] = True
            
            # Configure NTP
            print(f"  [+] Configuring NTP...")
            ntp_commands = self.generate_ntp_config()
            ntp_output = connection.send_config_set(ntp_commands)
            result['output'] += "=== NTP Configuration ===\n" + ntp_output + "\n"
            result['ntp_configured'] = True
            
            # Save configuration
            print(f"  [+] Saving configuration...")
            save_output = connection.send_command('write memory')
            result['output'] += "=== Save ===\n" + save_output + "\n"
            
            connection.disconnect()
            
            result['success'] = True
            print(f"  [✓] {switch['hostname']} configured successfully")
            
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
    
    def verify_syslog(self, switch: Dict) -> Dict:
        """Verify syslog configuration on a switch"""
        
        result = {
            'hostname': switch['hostname'],
            'syslog_server_configured': False,
            'logging_enabled': False,
            'output': ''
        }
        
        print(f"\n[*] Verifying syslog on {switch['hostname']}...")
        
        try:
            conn_params = self._get_connection_params(switch)
            connection = ConnectHandler(**conn_params)
            connection.enable()
            
            logging_output = connection.send_command('show logging')
            result['output'] = logging_output
            
            if self.syslog_server in logging_output:
                result['syslog_server_configured'] = True
                print(f"  [✓] Syslog server {self.syslog_server} configured")
            else:
                print(f"  [!] Syslog server not found in configuration")
            
            if 'Logging to' in logging_output and self.syslog_server in logging_output:
                result['logging_enabled'] = True
                print(f"  [✓] Logging to {self.syslog_server} is active")
            
            connection.disconnect()
            
        except Exception as e:
            print(f"  [!] Verification error: {e}")
            result['error'] = str(e)
        
        return result
    
    def verify_ntp(self, switch: Dict) -> Dict:
        """Verify NTP configuration and synchronization"""
        
        result = {
            'hostname': switch['hostname'],
            'ntp_server_configured': False,
            'ntp_synchronized': False,
            'clock_time': '',
            'output': ''
        }
        
        print(f"\n[*] Verifying NTP on {switch['hostname']}...")
        
        try:
            conn_params = self._get_connection_params(switch)
            connection = ConnectHandler(**conn_params)
            connection.enable()
            
            ntp_output = connection.send_command('show ntp associations')
            result['output'] = ntp_output
            
            if self.ntp_server in ntp_output:
                result['ntp_server_configured'] = True
                print(f"  [✓] NTP server {self.ntp_server} configured")
            else:
                print(f"  [!] NTP server not found in associations")
            
            if '*' in ntp_output or 'synced' in ntp_output.lower():
                result['ntp_synchronized'] = True
                print(f"  [✓] NTP synchronized")
            else:
                print(f"  [!] NTP not yet synchronized (may take a few minutes)")
            
            clock_output = connection.send_command('show clock')
            result['clock_time'] = clock_output.strip()
            print(f"  [i] Current time: {result['clock_time']}")
            
            connection.disconnect()
            
        except Exception as e:
            print(f"  [!] Verification error: {e}")
            result['error'] = str(e)
        
        return result
    
    def configure_all(self) -> List[Dict]:
        """Configure syslog and NTP on all switches"""
        
        print("=" * 70)
        print("Task 6: Syslog & NTP Configuration")
        print("=" * 70)
        print(f"\nSyslog Server: {self.syslog_server}")
        print(f"NTP Server: {self.ntp_server}")
        
        results = []
        
        for switch in self.switches:
            result = self.configure_switch(switch)
            results.append(result)
            time.sleep(2)
        
        print("\n" + "=" * 70)
        print("Configuration Summary")
        print("=" * 70)
        
        success_count = sum(1 for r in results if r['success'])
        print(f"\nTotal Switches: {len(results)}")
        print(f"✓ Successful: {success_count}")
        print(f"✗ Failed: {len(results) - success_count}")
        
        if success_count < len(results):
            print("\nFailed switches:")
            for r in results:
                if not r['success']:
                    print(f"  - {r['hostname']} ({r['ip']}): {r['error']}")
        
        return results
    
    def verify_all(self) -> Dict:
        """Verify syslog and NTP on all switches"""
        
        print("\n" + "=" * 70)
        print("Verification")
        print("=" * 70)
        
        syslog_results = []
        ntp_results = []
        
        for switch in self.switches:
            syslog_result = self.verify_syslog(switch)
            syslog_results.append(syslog_result)
            time.sleep(1)
            
            ntp_result = self.verify_ntp(switch)
            ntp_results.append(ntp_result)
            time.sleep(1)
        
        print("\n" + "=" * 70)
        print("Verification Summary")
        print("=" * 70)
        
        syslog_ok = sum(1 for r in syslog_results if r['syslog_server_configured'])
        ntp_ok = sum(1 for r in ntp_results if r['ntp_server_configured'])
        ntp_synced = sum(1 for r in ntp_results if r['ntp_synchronized'])
        
        print(f"\nSyslog Configuration: {syslog_ok}/{len(syslog_results)} switches")
        print(f"NTP Configuration: {ntp_ok}/{len(ntp_results)} switches")
        print(f"NTP Synchronized: {ntp_synced}/{len(ntp_results)} switches")
        
        if ntp_synced < len(ntp_results):
            print("\n[i] Note: NTP synchronization can take 5-10 minutes")
        
        return {'syslog': syslog_results, 'ntp': ntp_results}
    
    def generate_report(self, config_results: List, verify_results: Dict):
        """Generate deployment report"""
        
        report = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'task': 'Task 6 - Syslog & NTP Configuration',
            'syslog_server': self.syslog_server,
            'ntp_server': self.ntp_server,
            'configuration': config_results,
            'verification': verify_results,
            'summary': {
                'total_switches': len(config_results),
                'configured': sum(1 for r in config_results if r['success']),
                'syslog_verified': sum(1 for r in verify_results['syslog'] 
                                      if r['syslog_server_configured']),
                'ntp_verified': sum(1 for r in verify_results['ntp'] 
                                   if r['ntp_server_configured']),
                'ntp_synchronized': sum(1 for r in verify_results['ntp'] 
                                       if r['ntp_synchronized'])
            }
        }
        
        filename = 'task6_syslog_ntp_report.json'
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n[+] Report saved: {filename}")


def main():
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║          Task 6: Syslog & NTP Automation                          ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        from netmiko import ConnectHandler
    except ImportError:
        print("[!] Missing required module: netmiko")
        print("[!] Install with: pip install netmiko")
        return
    
    configurator = SyslogNTPConfigurator(
        syslog_server="10.10.10.1",
        ntp_server="10.10.10.1"
    )
    
    config_results = configurator.configure_all()
    
    print("\n[*] Waiting 30 seconds for NTP synchronization...")
    time.sleep(30)
    
    verify_results = configurator.verify_all()
    
    configurator.generate_report(config_results, verify_results)
    
    print("\n" + "=" * 70)
    print("Task 6 Complete!")
    print("=" * 70)
    print("\nCheck pfSense: Status → System Logs → System")
    print("Look for messages from 10.10.10.11-13")


if __name__ == "__main__":
    main()
