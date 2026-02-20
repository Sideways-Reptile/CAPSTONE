#!/usr/bin/env python3
"""
Task 3: Login Banner Automation Script
Generates and deploys login banners across network devices
"""

import paramiko
import time
import json
from typing import Dict, List
from datetime import datetime


class BannerGenerator:
    """Generate customizable login banners"""
    
    def __init__(self, company_name: str = "Your Company", 
                 contact_email: str = "support@company.com"):
        self.company_name = company_name
        self.contact_email = contact_email
    
    def generate_standard_banner(self) -> str:
        """Generate standard AUP login banner"""
        banner = f"""
{'*' * 79}
                        AUTHORIZED ACCESS ONLY
                           {self.company_name}
{'*' * 79}

WARNING: This system is for authorized use only.

By accessing this system, you acknowledge and agree to the following:

  • All activity is monitored and logged
  • Unauthorized access is strictly prohibited and will be prosecuted
  • No expectation of privacy exists on this network
  • Usage implies consent to monitoring and auditing
  • Violators will be prosecuted to the fullest extent of applicable law
  • System administrators may access and disclose any data on this system

If you are not an authorized user, disconnect immediately.

For assistance, contact IT Support: {self.contact_email}

{'*' * 79}
        """
        return banner.strip()
    
    def generate_ssh_banner(self) -> str:
        """Generate SSH pre-login banner"""
        banner = f"""
{'=' * 79}
           NOTICE: AUTHORIZED ACCESS ONLY - {self.company_name}
{'=' * 79}

This system is restricted to authorized users only. Individuals using this
system without authority, or in excess of their authority, are subject to
having all of their activities monitored and recorded.

Anyone using this system expressly consents to such monitoring and is advised
that if monitoring reveals possible evidence of criminal activity, system
personnel may provide the evidence to law enforcement officials.

Unauthorized access or use may result in criminal prosecution.

{'=' * 79}
        """
        return banner.strip()
    
    def generate_motd(self) -> str:
        """Generate Message of the Day (post-login)"""
        motd = f"""
Welcome to {self.company_name} Network

REMINDER: Your activities on this system are monitored and logged.

Last Login: {{last_login_time}}
System Uptime: {{uptime}}

For support: {self.contact_email}

{'=' * 79}
        """
        return motd.strip()
    
    def generate_windows_banner(self) -> Dict[str, str]:
        """Generate Windows registry-compatible banner"""
        return {
            "caption": "AUTHORIZED ACCESS ONLY",
            "text": f"""This computer system is the property of {self.company_name} and is for authorized use only.

By using this system, you consent to monitoring. Unauthorized access is prohibited and will be prosecuted.

All activities are logged and may be used as evidence in legal proceedings.

Contact IT Support: {self.contact_email}"""
        }
    
    def save_banners_to_files(self):
        """Save all banner types to files"""
        banners = {
            "standard_banner.txt": self.generate_standard_banner(),
            "ssh_banner.txt": self.generate_ssh_banner(),
            "motd.txt": self.generate_motd(),
            "windows_banner.json": json.dumps(self.generate_windows_banner(), indent=2)
        }
        
        for filename, content in banners.items():
            with open(filename, 'w') as f:
                f.write(content)
            print(f"[+] Created: {filename}")


class BannerDeployer:
    """Deploy banners to network devices"""
    
    def __init__(self, banner_text: str):
        self.banner_text = banner_text
    
    def deploy_to_pfsense(self, host: str, username: str, password: str):
        """Deploy banner to pfSense via SSH"""
        print(f"\n[*] Deploying banner to pfSense ({host})...")
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username=username, password=password, timeout=10)
            
            # pfSense uses PHP for config
            # This is a simplified approach - in production, use pfSense API
            
            commands = [
                # Option 8 = Shell
                "8",
                # Edit config file
                f"echo '{self.banner_text}' > /etc/banner.txt",
                # Exit shell
                "exit"
            ]
            
            shell = ssh.invoke_shell()
            time.sleep(2)
            
            for cmd in commands:
                shell.send(cmd + "\n")
                time.sleep(1)
            
            output = shell.recv(4096).decode()
            ssh.close()
            
            print(f"  [+] Banner deployed to pfSense")
            
        except Exception as e:
            print(f"  [!] Error deploying to pfSense: {e}")
    
    def deploy_to_linux(self, host: str, username: str, password: str):
        """Deploy banner to Linux/Ubuntu device"""
        print(f"\n[*] Deploying banner to Linux ({host})...")
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username=username, password=password, timeout=10)
            
            commands = [
                # Create banner file
                f"echo '{self.banner_text}' | sudo tee /etc/issue.net > /dev/null",
                
                # Update SSH config to use banner
                "sudo sed -i 's/#Banner none/Banner \\/etc\\/issue.net/' /etc/ssh/sshd_config",
                
                # Also update /etc/issue for console login
                f"echo '{self.banner_text}' | sudo tee /etc/issue > /dev/null",
                
                # Restart SSH service
                "sudo systemctl restart sshd",
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                stdout.channel.recv_exit_status()  # Wait for completion
            
            ssh.close()
            print(f"  [+] Banner deployed to Linux")
            
        except Exception as e:
            print(f"  [!] Error deploying to Linux: {e}")
    
    def generate_windows_script(self, output_file: str = "deploy_windows_banner.ps1"):
        """Generate PowerShell script for Windows banner deployment"""
        print(f"\n[*] Generating Windows PowerShell script...")
        
        # Escape quotes for PowerShell
        banner_escaped = self.banner_text.replace('"', '`"')
        
        script = f'''# Windows Login Banner Deployment Script
# Run as Administrator

# Set registry values for login banner
$caption = "AUTHORIZED ACCESS ONLY"
$text = @"
{banner_escaped}
"@

# Set legal notice caption
Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" `
    -Name "legalnoticecaption" -Value $caption -Type String

# Set legal notice text
Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" `
    -Name "legalnoticetext" -Value $text -Type String

Write-Host "[+] Login banner configured successfully" -ForegroundColor Green
Write-Host "[!] Reboot required to take effect" -ForegroundColor Yellow
'''
        
        with open(output_file, 'w') as f:
            f.write(script)
        
        print(f"  [+] PowerShell script created: {output_file}")
        print(f"  [!] Copy to Windows device and run as Administrator")
    
    def generate_switch_config(self, output_file: str = "switch_banner_config.txt"):
        """Generate switch configuration snippet"""
        print(f"\n[*] Generating switch configuration...")
        
        # Aruba/HP switch format
        config = f'''! Switch Banner Configuration
! Copy-paste into switch CLI

configure
banner motd #
{self.banner_text}
#

write memory
exit

! Verify with: show banner
'''
        
        with open(output_file, 'w') as f:
            f.write(config)
        
        print(f"  [+] Switch config created: {output_file}")


class BannerValidator:
    """Validate banner deployment"""
    
    def __init__(self):
        self.results = []
    
    def test_ssh_banner(self, host: str, port: int = 22) -> bool:
        """Test if SSH banner is present"""
        print(f"\n[*] Testing SSH banner on {host}...")
        
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            
            # Read SSH banner
            banner = sock.recv(1024).decode()
            sock.close()
            
            if "AUTHORIZED" in banner or "authorized" in banner:
                print(f"  [+] Banner detected on {host}")
                return True
            else:
                print(f"  [!] No banner detected on {host}")
                return False
                
        except Exception as e:
            print(f"  [!] Error testing {host}: {e}")
            return False
    
    def generate_validation_report(self, devices: List[Dict]) -> str:
        """Generate validation report"""
        report = f"""
{'=' * 79}
Task 3: Login Banner Deployment Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 79}

Device Testing Results:

"""
        for device in devices:
            status = "✓ PASS" if device['has_banner'] else "✗ FAIL"
            report += f"{status} | {device['name']} ({device['ip']})\n"
        
        report += f"\n{'=' * 79}\n"
        
        return report


def main():
    """Main execution"""
    print("=" * 79)
    print("Task 3: Login Banner Automation")
    print("Security Compliance - Login Banners")
    print("=" * 79)
    print()
    
    # Get customization
    print("[*] Banner Configuration")
    company = input("Company Name [Your Company]: ") or "Your Company"
    contact = input("Support Email [support@company.com]: ") or "support@company.com"
    
    # Generate banners
    print("\n[*] Generating banner templates...")
    generator = BannerGenerator(company, contact)
    banner_text = generator.generate_standard_banner()
    
    print("\nGenerated Banner:")
    print("-" * 79)
    print(banner_text)
    print("-" * 79)
    
    # Save to files
    print("\n[*] Saving banner files...")
    generator.save_banners_to_files()
    
    # Deployment options
    print("\n" + "=" * 79)
    print("Deployment Options:")
    print("=" * 79)
    print("\n1. Deploy to pfSense (via SSH)")
    print("2. Deploy to Linux devices (via SSH)")
    print("3. Generate Windows PowerShell script")
    print("4. Generate Switch configuration")
    print("5. Deploy to all devices (automated)")
    print("6. Validate existing banners")
    print("7. Exit")
    
    deployer = BannerDeployer(banner_text)
    
    while True:
        choice = input("\nSelect option (1-7): ")
        
        if choice == "1":
            host = input("pfSense IP [10.10.10.1]: ") or "10.10.10.1"
            user = input("Username [admin]: ") or "admin"
            password = input("Password: ")
            deployer.deploy_to_pfsense(host, user, password)
            
        elif choice == "2":
            host = input("Linux IP: ")
            user = input("Username: ")
            password = input("Password: ")
            deployer.deploy_to_linux(host, user, password)
            
        elif choice == "3":
            deployer.generate_windows_script()
            
        elif choice == "4":
            deployer.generate_switch_config()
            
        elif choice == "5":
            print("\n[*] Automated Deployment")
            print("[!] Reading device inventory...")
            
            # Load from inventory file if exists
            try:
                with open("device_inventory.json", "r") as f:
                    inventory = json.load(f)
                
                for device in inventory.get("devices", []):
                    if device["type"] == "pfsense":
                        deployer.deploy_to_pfsense(
                            device["ip"], 
                            device["username"], 
                            device["password"]
                        )
                    elif device["type"] == "linux":
                        deployer.deploy_to_linux(
                            device["ip"],
                            device["username"],
                            device["password"]
                        )
                        
            except FileNotFoundError:
                print("[!] device_inventory.json not found")
                print("[!] Create it with format:")
                print('''
{
  "devices": [
    {"type": "pfsense", "ip": "10.10.10.1", "username": "admin", "password": "pfsense"},
    {"type": "linux", "ip": "192.168.100.10", "username": "root", "password": "password"}
  ]
}
                ''')
                
        elif choice == "6":
            print("\n[*] Validating Banner Deployment")
            validator = BannerValidator()
            
            test_devices = [
                {"name": "pfSense", "ip": "10.10.10.1"},
                {"name": "DMZ-Web", "ip": "192.168.100.10"},
                {"name": "DMZ-DB", "ip": "192.168.100.11"},
            ]
            
            for device in test_devices:
                device['has_banner'] = validator.test_ssh_banner(device['ip'])
            
            report = validator.generate_validation_report(test_devices)
            print(report)
            
            with open("banner_validation_report.txt", "w") as f:
                f.write(report)
            print("[+] Report saved: banner_validation_report.txt")
            
        elif choice == "7":
            print("\n[*] Exiting...")
            break
        
        else:
            print("[!] Invalid option")
    
    print("\n" + "=" * 79)
    print("Task 3 Deployment Summary")
    print("=" * 79)
    print("""
Files Created:
  • standard_banner.txt - Standard login banner
  • ssh_banner.txt - SSH pre-login banner
  • motd.txt - Message of the day
  • windows_banner.json - Windows banner data
  • deploy_windows_banner.ps1 - Windows deployment script
  • switch_banner_config.txt - Switch configuration

Next Steps:
  1. Test SSH access to devices (should see banner)
  2. Test Web GUI access to pfSense (should see banner)
  3. Deploy Windows script on Windows devices
  4. Apply switch config to managed switches
  5. Document banner locations for compliance audit

Task 3 Complete! ✓
    """)


if __name__ == "__main__":
    # Check for required modules
    try:
        import paramiko
    except ImportError:
        print("[!] Missing required module: paramiko")
        print("[!] Install with: pip install paramiko")
        print()
        
        # Still allow banner generation even without SSH capability
        proceed = input("Continue without SSH deployment? (y/n): ")
        if proceed.lower() != 'y':
            exit(1)
    
    main()
