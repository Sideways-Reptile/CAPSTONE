#!/usr/bin/env python3
"""
Deploy SSH public key to Cisco switches
"""

from netmiko import ConnectHandler
import os
from pathlib import Path

# Configuration
PUBLIC_KEY_PATH = "~/.ssh/id_rsa.pub"
USERNAME = "case"

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
print(f"Public key: {public_key[:50]}...")

for switch in switches:
    print(f"\n[*] Configuring {switch['hostname']} ({switch['host']})...")
    
    # Initial connection with password
    device = {
        'device_type': 'cisco_ios',
        'host': switch['host'],
        'username': USERNAME,
        'password': 'sidewaays',  # Last time using password!
        'secret': 'sidewaays',
    }
    
    try:
        connection = ConnectHandler(**device)
        connection.enable()
        
        # Configure SSH key
        commands = [
            'ip ssh pubkey-chain',
            f'username {USERNAME}',
            'key-string',
            public_key,
            'exit',
            'exit',
            'exit',
        ]
        
        output = connection.send_config_set(commands)
        
        # Save config
        connection.send_command('write memory')
        
        connection.disconnect()
        print(f"  [✓] SSH key deployed successfully")
        
    except Exception as e:
        print(f"  [!] Error: {e}")

print("\n[*] Deployment complete!")
print("[*] Test with: ssh -i ~/.ssh/id_rsa case@10.10.10.11")
