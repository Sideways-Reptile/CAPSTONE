#!/usr/bin/env python3
"""
Task 5: Initial Switch Configuration
Sets up management IP and SSH access on Cisco switches
Run this AFTER manually configuring via console, or use output for manual setup
"""

class CiscoSwitchInitialConfig:
    """Generate initial configuration for Cisco switches"""
    
    def __init__(self):
        self.switches = [
            {
                'hostname': 'SW1-CORE',
                'mgmt_ip': '10.10.10.11',
                'role': 'Root Bridge',
                'priority': 4096
            },
            {
                'hostname': 'SW2-CORP',
                'mgmt_ip': '10.10.10.12',
                'role': 'Distribution',
                'priority': 8192
            },
            {
                'hostname': 'SW3-DMZ',
                'mgmt_ip': '10.10.10.13',
                'role': 'Access',
                'priority': 32768
            }
        ]
    
    def generate_initial_config(self, switch: dict) -> str:
        """Generate initial configuration for a switch"""
        
        config = f"""
! ============================================================
! Initial Configuration: {switch['hostname']}
! Management IP: {switch['mgmt_ip']}
! Role: {switch['role']}
! ============================================================

enable
configure terminal

! Set hostname
hostname {switch['hostname']}

! Configure management VLAN
interface vlan 1
 description Management Interface
 ip address {switch['mgmt_ip']} 255.255.255.0
 no shutdown
exit

! Set default gateway (pfSense)
ip default-gateway 10.10.10.1

! Configure domain name for SSH
ip domain-name lab.local

! Generate RSA keys for SSH (2048 bit)
crypto key generate rsa modulus 2048

! Create admin user
username admin privilege 15 secret Admin123!

! Enable SSH on VTY lines
line vty 0 15
 login local
 transport input ssh
 exec-timeout 30 0
exit

! Enable console
line console 0
 login local
 exec-timeout 30 0
exit

! Enable secret for privileged mode
enable secret Admin123!

! Save configuration
end
write memory

! ============================================================
! Initial setup complete for {switch['hostname']}
! You can now SSH to: {switch['mgmt_ip']}
! Username: admin
! Password: Admin123!
! ============================================================
"""
        return config
    
    def save_all_configs(self):
        """Save initial configs for all switches"""
        print("=" * 70)
        print("Cisco Switch Initial Configuration Generator")
        print("=" * 70)
        print()
        
        for switch in self.switches:
            filename = f"{switch['hostname']}_initial_config.txt"
            config = self.generate_initial_config(switch)
            
            with open(filename, 'w') as f:
                f.write(config)
            
            print(f"[+] Created: {filename}")
            print(f"    Hostname: {switch['hostname']}")
            print(f"    Management IP: {switch['mgmt_ip']}")
            print(f"    Role: {switch['role']}")
            print()
        
        print("=" * 70)
        print("Manual Setup Instructions")
        print("=" * 70)
        print("""
To configure each switch:

1. GNS3 → Right-click switch → Console
2. Wait for switch to boot (may take 2-3 minutes)
3. Press Enter to get prompt
4. Copy-paste the contents of [HOSTNAME]_initial_config.txt
5. Wait for crypto key generation (takes 30-60 seconds)
6. Verify SSH: ssh admin@[IP_ADDRESS]

After all switches are configured with IPs and SSH:
- Run: python3 stp_automation.py (to configure STP via SSH)
        """)


if __name__ == "__main__":
    generator = CiscoSwitchInitialConfig()
    generator.save_all_configs()
