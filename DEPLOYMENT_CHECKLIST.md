# Complete Deployment Checklist
## Network Lab Project - Step-by-Step Guide

---

## Pre-Deployment Requirements

### Software Prerequisites
```
☐ GNS3 2.2.x or later installed
☐ VMware Workstation Pro 17.x installed
☐ Python 3.10+ installed
☐ pip package manager available
☐ Git installed (optional, for version control)
```

### GNS3 Appliances Required
```
☐ pfSense VM image (7.0.x recommended, NOT 7.6+)
☐ Cisco IOSv L2 switch image (3 instances needed)
☐ Ubuntu Docker image (optional, for servers)
☐ Windows 10 image (optional, for workstations)
☐ VPCS (built-in to GNS3)
```

### Network Configuration
```
☐ VMware NAT network (VMnet8) functional
☐ Host machine has internet connectivity
☐ Npcap installed (Windows) for bridging
```

---

## Task 1: Network Segmentation & Reachability

### Time Estimate: 45 minutes

### Step 1: GNS3 Topology Setup (15 mins)

```
☐ Create new GNS3 project: "NetworkLab_Production"

☐ Add devices:
   ☐ 1x pfSense firewall node
   ☐ 4x Ethernet Switch (basic) OR 3x Cisco switches
   ☐ 4x VPCS nodes (PC1, PC2, PC3, PC4)
   ☐ 1x NAT cloud
   ☐ 1x Windows 10 VM (optional)

☐ Connect topology:
   ☐ NAT → pfSense em0 (WAN)
   ☐ pfSense em1 → Switch-MGMT → PC1
   ☐ pfSense em2 → Switch-CORP → PC2
   ☐ pfSense em3 → Switch-DMZ → PC3
   ☐ pfSense em4 → Switch-GUEST → PC4

☐ Start all nodes
☐ Wait for pfSense to boot (2-3 minutes)
```

### Step 2: pfSense Initial Configuration (10 mins)

```
☐ Access pfSense console
☐ Configure WAN interface (em0):
   ☐ Select DHCP
   ☐ Verify IP obtained from NAT

☐ Configure LAN interfaces:
   ☐ em1 (MGMT): 10.10.10.1/24
   ☐ em2 (CORP): 172.16.1.1/24
   ☐ em3 (DMZ): 192.168.100.1/24
   ☐ em4 (GUEST): 192.168.200.1/24

☐ Access Web GUI: https://10.10.10.1
   ☐ Username: admin
   ☐ Password: pfsense (change immediately)
```

### Step 3: Configure Endpoint IPs (5 mins)

```
☐ PC1 (MGMT VPCS):
   ip 10.10.10.100/24 10.10.10.1
   save

☐ PC2 (CORP VPCS):
   ip 172.16.1.100/24 172.16.1.1
   save

☐ PC3 (DMZ VPCS):
   ip 192.168.100.10/24 192.168.100.1
   save

☐ PC4 (GUEST VPCS):
   ip 192.168.200.50/24 192.168.200.1
   save
```

### Step 4: Generate & Apply Firewall Rules (10 mins)

```
☐ On your host machine:
   cd task1_device_discovery
   python3 fortigate_config.py

☐ Open: fortigate_task1_config.txt

☐ In pfSense GUI:
   ☐ Firewall → Aliases → Create NET_MGMT, NET_CORP, NET_DMZ, NET_GUEST
   ☐ Firewall → Rules → MGMT → Add "MGMT to ALL"
   ☐ Firewall → Rules → CORP → Add "CORP to DMZ"
   ☐ Apply Changes

☐ Alternative: Copy-paste CLI config via console
```

### Step 5: Validation (5 mins)

```
☐ Test connectivity:
   From PC1 (MGMT):
   ☐ ping 10.10.10.1 (should work)
   ☐ ping 172.16.1.1 (should work)
   ☐ ping 192.168.100.1 (should work)

   From PC2 (CORP):
   ☐ ping 192.168.100.10 (should work)
   ☐ ping 10.10.10.1 (should FAIL - timeout)

☐ Run automated tests:
   python3 device_discovery.py

☐ Check results:
   cat discovery_report.json
   cat reachability_report.json
```

### Task 1 Success Criteria
```
✓ All 4 network segments operational
✓ MGMT can reach all segments
✓ CORP can reach DMZ but not MGMT
✓ Discovery script finds all devices
✓ Reachability tests pass as expected
```

---

## Task 2: Guest ACL for Internet-Only Access

### Time Estimate: 20 minutes

### Step 1: Generate ACL Configuration (2 mins)

```
☐ cd task2_guest_acl
☐ python3 fortigate_acl_config.py
☐ Review: fortigate_guest_acl_config.txt
```

### Step 2: Create Address Objects (5 mins)

```
☐ In pfSense GUI:
   Firewall → Aliases → IP

☐ Create RFC1918_ALL:
   ☐ Type: Network(s)
   ☐ Networks: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
   ☐ Description: "All RFC1918 private networks"

☐ Create PUBLIC_DNS:
   ☐ Type: Host(s)
   ☐ Hosts: 8.8.8.8, 8.8.4.4, 1.1.1.1, 1.0.0.1
   ☐ Description: "Public DNS servers"

☐ Apply Changes
```

### Step 3: Configure GUEST Firewall Rules (8 mins)

```
☐ Firewall → Rules → GUEST
☐ Delete any existing allow-all rules

☐ Add Rule 1 (HIGHEST PRIORITY):
   ☐ Action: Block
   ☐ Interface: GUEST
   ☐ Protocol: Any
   ☐ Source: GUEST net
   ☐ Destination: RFC1918_ALL
   ☐ Description: "Block RFC1918 - Internal Networks"
   ☐ Log: ✓ Checked
   ☐ Save

☐ Add Rule 2:
   ☐ Action: Pass
   ☐ Interface: GUEST
   ☐ Protocol: UDP
   ☐ Source: GUEST net
   ☐ Destination: PUBLIC_DNS, Port 53
   ☐ Description: "Allow DNS Queries"
   ☐ Log: ✓ Checked
   ☐ Save

☐ Add Rule 3:
   ☐ Action: Pass
   ☐ Interface: GUEST
   ☐ Protocol: Any
   ☐ Source: GUEST net
   ☐ Destination: Any
   ☐ Description: "Allow Internet Access"
   ☐ Log: ✓ Checked
   ☐ Save

☐ Apply Changes
```

### Step 4: Validation (5 mins)

```
☐ From PC4 (GUEST - 192.168.200.50):

   Should FAIL (timeout):
   ☐ ping 10.10.10.1
   ☐ ping 172.16.1.1
   ☐ ping 192.168.100.1

   Should SUCCEED:
   ☐ ping 8.8.8.8
   ☐ ping 1.1.1.1
   ☐ ping google.com

☐ Run validation script:
   python3 validate_task2.py

☐ Review pfSense logs:
   Status → System Logs → Firewall
   ☐ Look for blocked RFC1918 attempts
   ☐ Verify internet traffic allowed
```

### Task 2 Success Criteria
```
✓ Guest cannot ping internal gateways (10.x, 172.16.x, 192.168.100.x)
✓ Guest CAN ping 8.8.8.8 and 1.1.1.1
✓ Guest can resolve domain names
✓ Guest can browse internet
✓ Firewall logs show blocked internal attempts
✓ MGMT can still ping guest devices
```

---

## Task 3: Login Banners for Compliance

### Time Estimate: 15 minutes

### Step 1: Generate Banner Files (2 mins)

```
☐ cd task3_login_banners
☐ python3 deploy_banners.py
☐ Select option 1 (Generate banner files)

☐ Files created:
   ☐ standard_banner.txt
   ☐ ssh_banner.txt
   ☐ deploy_windows_banner.ps1
```

### Step 2: pfSense SSH Banner (3 mins)

```
☐ pfSense Console → Option 8 (Shell)

☐ Paste:
   cat > /etc/issue.net << 'EOF'
   [paste banner text from ssh_banner.txt]
   EOF

☐ Enable in SSH config:
   echo 'Banner /etc/issue.net' >> /etc/ssh/sshd_config
   /etc/rc.d/sshd restart

☐ Exit shell (Ctrl+D twice)
```

### Step 3: Windows Login Banner (5 mins)

```
☐ On Windows VM:
   ☐ Right-click deploy_windows_banner.ps1
   ☐ Run with PowerShell (as Administrator)
   ☐ Reboot Windows VM

☐ Test:
   ☐ Lock screen (Windows + L)
   ☐ Click user
   ☐ Banner should appear before password prompt
```

### Step 4: Validation (5 mins)

```
☐ Test pfSense banner:
   ssh admin@10.10.10.1
   ☐ Banner should display BEFORE password prompt

☐ Test Windows banner:
   ☐ Lock screen
   ☐ Click user account
   ☐ Banner popup should require "OK" click

☐ Document:
   ☐ Screenshot pfSense SSH banner
   ☐ Screenshot Windows login banner
```

### Task 3 Success Criteria
```
✓ pfSense SSH displays banner before login
✓ Windows shows banner on login screen
✓ Banner text includes "AUTHORIZED ACCESS ONLY"
✓ Banner mentions monitoring and legal consequences
✓ Screenshots captured for documentation
```

---

## Task 4: DHCP & Static Addressing

### Time Estimate: 10 minutes (mostly verification)

### Step 1: Configure DHCP Pools (5 mins)

```
☐ pfSense GUI → Services → DHCP Server

☐ CORP Interface:
   ☐ Enable: ✓
   ☐ Range: 172.16.1.100 to 172.16.1.200
   ☐ DNS: 8.8.8.8, 8.8.4.4
   ☐ Gateway: 172.16.1.1
   ☐ Save

☐ DMZ Interface:
   ☐ Enable: ✓
   ☐ Range: 192.168.100.50 to 192.168.100.100
   ☐ DNS: 8.8.8.8
   ☐ Gateway: 192.168.100.1
   ☐ Save

☐ GUEST Interface:
   ☐ Enable: ✓
   ☐ Range: 192.168.200.50 to 192.168.200.150
   ☐ DNS: 8.8.8.8, 1.1.1.1
   ☐ Gateway: 192.168.200.1
   ☐ Save
```

### Step 2: Configure Static IPs (5 mins)

```
☐ pfSense (already static):
   ☐ MGMT: 10.10.10.1 ✓
   ☐ CORP: 172.16.1.1 ✓
   ☐ DMZ: 192.168.100.1 ✓
   ☐ GUEST: 192.168.200.1 ✓

☐ Services requiring static (if applicable):
   ☐ DMZ Web Server: 192.168.100.10
   ☐ DMZ DB Server: 192.168.100.11
```

### Task 4 Success Criteria
```
✓ DHCP pools configured on CORP, DMZ, GUEST
✓ pfSense has static IPs on all interfaces
✓ At least one service has static IP (pfSense counts)
✓ Dynamic devices receive IPs from DHCP
```

---

## Task 5: Spanning Tree Protocol & Redundancy

### Time Estimate: 40 minutes

### Step 1: Replace Basic Switches with Cisco (10 mins)

```
☐ Stop all devices in GNS3

☐ Remove basic Ethernet Switch nodes

☐ Add 3x Cisco IOSv L2 switches:
   ☐ SW1-CORE
   ☐ SW2-CORP
   ☐ SW3-DMZ

☐ Reconnect topology:
   ☐ pfSense em1 → SW1-CORE Gi0/0
   ☐ pfSense em2 → SW2-CORP Gi0/0
   ☐ pfSense em3 → SW3-DMZ Gi0/0

☐ Create redundant links:
   ☐ SW1 Gi0/1 ↔ SW2 Gi0/1
   ☐ SW1 Gi0/2 ↔ SW3 Gi0/1
   ☐ SW2 Gi0/2 ↔ SW3 Gi0/2 (primary)
   ☐ SW2 Gi0/3 ↔ SW3 Gi0/3 (redundant - creates loop!)

☐ Start all switches
☐ Wait for boot (3-5 minutes)
```

### Step 2: Initial Switch Configuration (15 mins)

```
☐ Generate config files:
   cd task5_stp
   python3 initial_switch_setup.py

☐ Configure SW1-CORE:
   ☐ GNS3 → Right-click SW1-CORE → Console
   ☐ Copy-paste: SW1-CORE_initial_config.txt
   ☐ Wait for crypto key generation (60 seconds)

☐ Configure SW2-CORP:
   ☐ Copy-paste: SW2-CORP_initial_config.txt
   ☐ Wait for crypto key

☐ Configure SW3-DMZ:
   ☐ Copy-paste: SW3-DMZ_initial_config.txt
   ☐ Wait for crypto key

☐ Verify SSH access:
   ☐ ssh admin@10.10.10.11 (SW1)
   ☐ ssh admin@10.10.10.12 (SW2)
   ☐ ssh admin@10.10.10.13 (SW3)
```

### Step 3: Configure STP (10 mins)

```
☐ Option A - Automated:
   python3 stp_automation.py
   (Configures all switches via SSH)

☐ Option B - Manual (on each switch):
   
   SW1-CORE:
   ☐ spanning-tree mode rapid-pvst
   ☐ spanning-tree vlan 1 priority 4096

   SW2-CORP:
   ☐ spanning-tree mode rapid-pvst
   ☐ spanning-tree vlan 1 priority 8192

   SW3-DMZ:
   ☐ spanning-tree mode rapid-pvst
   ☐ spanning-tree vlan 1 priority 32768

   All switches:
   ☐ interface range GigabitEthernet0/0 - 3
   ☐ no shutdown
   ☐ write memory
```

### Step 4: Verification (5 mins)

```
☐ On all switches, run:
   show spanning-tree root
   ☐ Should show SW1-CORE as root (Priority 4096)

☐ On SW2 and SW3, run:
   show spanning-tree blockedports
   ☐ Should show at least one blocked port

☐ On SW1-CORE:
   show spanning-tree
   ☐ Should show "This bridge is the root"
   ☐ All ports should be "Designated" and "Forwarding"

☐ Test failover:
   ☐ On SW1, disable interface: shutdown Gi0/1
   ☐ On SW2, verify convergence (< 2 seconds)
   ☐ Previously blocked port should now forward
   ☐ Re-enable: no shutdown
```

### Task 5 Success Criteria
```
✓ 3 Cisco switches deployed with redundant links
✓ Rapid STP (802.1w) enabled on all switches
✓ SW1-CORE elected as root bridge
✓ Redundant ports blocking (preventing loops)
✓ Failover tested successfully (< 2 sec convergence)
✓ Network remains functional after link failure
```

---

## Final Validation - Complete Lab

### Comprehensive Testing Checklist

```
Network Connectivity:
☐ MGMT can ping all segments
☐ CORP can ping DMZ but not MGMT
☐ DMZ cannot initiate outbound
☐ GUEST can only reach internet

Guest Network:
☐ Guest cannot ping 10.10.10.1, 172.16.1.1, 192.168.100.1
☐ Guest CAN ping 8.8.8.8, 1.1.1.1, google.com
☐ pfSense logs show blocked RFC1918 attempts

Security:
☐ Login banners displayed on pfSense SSH
☐ Login banners displayed on Windows login
☐ All firewall policies have logging enabled

High Availability:
☐ STP showing correct root bridge (SW1)
☐ Blocked ports present (redundancy working)
☐ Link failure causes failover < 2 seconds

Internet Connectivity:
☐ WAN interface has IP from DHCP
☐ MGMT can browse internet
☐ CORP can browse internet
☐ GUEST can browse internet
☐ DMZ cannot browse internet (by design)
```

---

## Troubleshooting Common Issues

### Issue: pfSense GUI won't load

```
☐ Check interface has https enabled:
   System → Advanced → Admin Access
   ☐ "allowaccess ping https ssh" should be set

☐ Clear browser cache
☐ Try different browser
☐ Access via: https://10.10.10.1 (not http://)
☐ Accept self-signed certificate warning
```

### Issue: Can ping gateway but not devices

```
☐ Check device has correct gateway configured
☐ Verify firewall rules allow return traffic
☐ Check pfSense is in NAT mode (not transparent):
   System → Advanced → Firewall & NAT
   
☐ Verify routing:
   Diagnostics → Routes
```

### Issue: Guest network can access internal

```
☐ Verify policy order in pfSense:
   Firewall → Rules → GUEST
   ☐ Block RFC1918 MUST be rule #1 (highest priority)

☐ Check RFC1918_ALL alias includes all ranges:
   ☐ 10.0.0.0/8
   ☐ 172.16.0.0/12
   ☐ 192.168.0.0/16
```

### Issue: SSH to Cisco switches fails

```
☐ Ubuntu/modern SSH - edit ~/.ssh/config:
   Host 10.10.10.*
       KexAlgorithms +diffie-hellman-group14-sha1
       HostKeyAlgorithms +ssh-rsa
       PubkeyAcceptedKeyTypes +ssh-rsa

☐ Windows - reinstall Npcap with WinPcap compatibility mode
```

### Issue: STP not blocking any ports

```
☐ Verify redundant links exist (SW2 ↔ SW3 should have 2 cables)
☐ Check STP enabled:
   show spanning-tree summary
   ☐ Should show "rapid-pvst" mode

☐ Verify priorities set correctly:
   show spanning-tree root
```

---

## Post-Deployment Tasks

### Documentation

```
☐ Capture topology screenshot from GNS3
☐ Screenshot pfSense firewall rules
☐ Screenshot STP output showing root bridge
☐ Export pfSense configuration backup:
   Diagnostics → Backup & Restore → Download
☐ Save all test reports (JSON files)
```

### Backup & Version Control

```
☐ Save GNS3 project file
☐ Export switch configurations:
   On each switch: show running-config
   Copy to text files
☐ Commit all files to Git repository
☐ Tag release: git tag -a v1.0 -m "Production ready"
```

### Client Demo Preparation

```
☐ Review EXECUTIVE_SUMMARY.md
☐ Practice demonstration flow
☐ Prepare talking points for each task
☐ Test all automation scripts work
☐ Have topology diagram ready to show
```

---

## Time Summary

```
Task 1: Network Segmentation          → 45 minutes
Task 2: Guest ACL                      → 20 minutes
Task 3: Login Banners                  → 15 minutes
Task 4: DHCP & Static IPs              → 10 minutes
Task 5: STP Redundancy                 → 40 minutes
                                       ─────────────
Total Initial Deployment:              → ~2.5 hours

With automation scripts:               → ~1 hour
With this checklist:                   → ~1.5 hours
```

---

## Success! 🎉

If you've checked off all items above, you have:

✅ A fully functional, enterprise-grade network lab  
✅ Five completed security tasks  
✅ Complete automation scripts  
✅ Professional documentation  
✅ A working environment ready for client demos  

**Congratulations on completing the Network Lab Project!**
