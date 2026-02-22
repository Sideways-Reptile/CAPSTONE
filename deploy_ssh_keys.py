#!/usr/bin/env python3
"""
Deploy SSH public key to Cisco switches - FIXED VERSION
"""

from netmiko import ConnectHandler
import os

# Configuration
PUBLIC_KEY_PATH = "~/.ssh/id_rsa.pub"
USERNAME = "case"
PASSWORD = "sidewaays"

switches = [
    {'host': '10.10.10.11', 'hostname': 'SW1-CORE'},
    {'host': '10.10.10.12', 'hostname': 'SW2-CORP'},
    {'host': '10.10.10.13', 'hostname': 'SW3-DMZ'},
]

# Read public key
key_path = os.path.expanduser(PUBLIC_KEY_PATH)
with open(key_path, 'r') as f:
    public_key = f.read().strip()

print(f"Deploying SSH key for user: {USERNAME}")

for switch in switches:
    print(f"\n[*] Configuring {switch['hostname']} ({switch['host']})...")
    
    device = {
        'device_type': 'cisco_ios',
        'host': switch['host'],
        'username': USERNAME,
        'password': PASSWORD,
        'secret': PASSWORD,
    }
    
    try:
        connection = ConnectHandler(**device)
        connection.enable()
        
        # Enter config mode manually
        connection.send_command('configure terminal', expect_string=r'config')
        
        # Enter SSH pubkey mode
        connection.send_command('ip ssh pubkey-chain', expect_string=r'conf-ssh-pubkey')
        connection.send_command(f'username {USERNAME}', expect_string=r'conf-ssh-pubkey-user')
        
        # Enter key-string mode (multi-line)
        connection.send_command('key-string', expect_string=r'conf-ssh-pubkey-data')
        
        # Send the actual key (THIS IS THE FIX)
        connection.send_command(public_key, expect_string=r'conf-ssh-pubkey-data', 
                               read_timeout=10, cmd_verify=False)
        
        # Exit key-string mode
        connection.send_command('exit', expect_string=r'conf-ssh-pubkey-user')
        
        # Exit username mode
        connection.send_command('exit', expect_string=r'conf-ssh-pubkey')
        
        # Exit pubkey-chain mode
        connection.send_command('exit', expect_string=r'config')
        
        # Exit config mode
        connection.send_command('end', expect_string=r'#')
        
        # Save config
        connection.send_command('write memory')
        
        connection.disconnect()
        print(f"  [✓] SSH key deployed successfully")
        
    except Exception as e:
        print(f"  [!] Error: {e}")

print("\n[*] Deployment complete!")
print("[*] Test with: ssh -i ~/.ssh/id_rsa case@10.10.10.11")
