# pfSense Configuration Guide - Task 1
## Network Segmentation with Access Control

## Initial Setup (Console)

After pfSense boots, you'll see a console menu.

### Step 1: Assign Interfaces

```
Select option: 1) Assign Interfaces

Should VLANs be set up now? n

Enter the WAN interface name: em0
Enter the LAN interface name: em1
Enter the Optional 1 interface name: em2
Enter the Optional 2 interface name: em3
Enter the Optional 3 interface name: (press Enter - none)

Proceed? y
```

### Step 2: Set Interface IPs

#### Configure WAN (MGMT Network)
```
Select option: 2) Set interface(s) IP address

Select interface: 1 (WAN/em0)

Configure IPv4 address via DHCP? n
Enter IPv4 address: 10.10.10.1
Enter subnet bit count: 24
Enter upstream gateway: (press Enter - none)

Configure IPv6 address via DHCP6? n
Enter IPv6 address: (press Enter - none)

Enable DHCP server on WAN? n
Revert to HTTP as webConfigurator protocol? n
```

#### Configure LAN (CORP Network)
```
Select option: 2) Set interface(s) IP address

Select interface: 2 (LAN/em1)

Configure IPv4 address via DHCP? n
Enter IPv4 address: 172.16.1.1
Enter subnet bit count: 24
Enter upstream gateway: (press Enter - none)

Configure IPv6 address via DHCP6? n
Enter IPv6 address: (press Enter - none)

Enable DHCP server on LAN? y
Start address: 172.16.1.100
End address: 172.16.1.200

Revert to HTTP as webConfigurator protocol? n
```

#### Configure OPT1 (DMZ Network)
```
Select option: 2) Set interface(s) IP address

Select interface: 3 (OPT1/em2)

Configure IPv4 address via DHCP? n
Enter IPv4 address: 192.168.100.1
Enter subnet bit count: 24
Enter upstream gateway: (press Enter - none)

Configure IPv6 address via DHCP6? n

Enable DHCP server on OPT1? y
Start address: 192.168.100.10
End address: 192.168.100.100

Revert to HTTP as webConfigurator protocol? n
```

#### Configure OPT2 (GUEST Network)
```
Select option: 2) Set interface(s) IP address

Select interface: 4 (OPT2/em3)

Configure IPv4 address via DHCP? n
Enter IPv4 address: 192.168.200.1
Enter subnet bit count: 24
Enter upstream gateway: (press Enter - none)

Configure IPv6 address via DHCP6? n

Enable DHCP server on OPT2? y
Start address: 192.168.200.50
End address: 192.168.200.100

Revert to HTTP as webConfigurator protocol? n
```

---

## Web GUI Configuration

### Access the GUI

From PC1 (10.10.10.100), open browser:
```
http://10.10.10.1
or
https://10.10.10.1

Default credentials:
Username: admin
Password: pfsense
```

### Step 3: Rename Interfaces (for clarity)

```
Interfaces → WAN
  Description: MGMT
  Save → Apply Changes

Interfaces → LAN
  Description: CORP
  Save → Apply Changes

Interfaces → OPT1
  Description: DMZ
  Save → Apply Changes

Interfaces → OPT2
  Description: GUEST
  Save → Apply Changes
```

---

## Step 4: Create Firewall Aliases (Address Objects)

**Firewall → Aliases → IP**

### Create Network Aliases
```
Name: NET_MGMT
Type: Network(s)
Network: 10.10.10.0/24
Description: Management Network
Save

Name: NET_CORP
Type: Network(s)
Network: 172.16.1.0/24
Description: Corporate Network
Save

Name: NET_DMZ
Type: Network(s)
Network: 192.168.100.0/24
Description: DMZ Network
Save

Name: NET_GUEST
Type: Network(s)
Network: 192.168.200.0/24
Description: Guest Network
Save

Apply Changes
```

---

## Step 5: Configure Firewall Rules

pfSense processes rules **top-to-bottom** on each interface tab.
Default: **Block all** unless explicitly allowed.

### MGMT Interface Rules (Full Access)

**Firewall → Rules → MGMT**

```
Rule 1: MGMT to ALL
  Action: Pass
  Interface: MGMT
  Protocol: Any
  Source: NET_MGMT
  Destination: Any
  Description: Management full access to all networks
  
  Save → Apply Changes
```

### CORP Interface Rules (Limited Access)

**Firewall → Rules → CORP**

```
Rule 1: CORP to DMZ
  Action: Pass
  Interface: CORP
  Protocol: Any
  Source: NET_CORP
  Destination: NET_DMZ
  Description: Corporate can access DMZ services
  
  Save

Rule 2: CORP Internal
  Action: Pass
  Interface: CORP
  Protocol: Any
  Source: NET_CORP
  Destination: NET_CORP
  Description: Corporate internal communication
  
  Save → Apply Changes
```

**Note:** CORP to MGMT is blocked by default (implicit deny)

### DMZ Interface Rules (Inbound Only)

**Firewall → Rules → DMZ**

```
Rule 1: DMZ Internal
  Action: Pass
  Interface: DMZ
  Protocol: Any
  Source: NET_DMZ
  Destination: NET_DMZ
  Description: DMZ internal communication
  
  Save → Apply Changes
```

**Note:** DMZ cannot initiate to other networks (implicit deny)

### GUEST Interface Rules (Minimal)

**Firewall → Rules → GUEST**

```
Rule 1: GUEST Internal
  Action: Pass
  Interface: GUEST
  Protocol: Any
  Source: NET_GUEST
  Destination: NET_GUEST
  Description: Guest internal communication
  
  Save → Apply Changes
```

**Note:** GUEST blocked from all other networks (implicit deny)

---

## Step 6: Enable Logging

For each rule you created:
1. Click edit (pencil icon)
2. Scroll to "Extra Options"
3. Check "Log packets that are handled by this rule"
4. Save → Apply Changes

---

## Verification Commands (Diagnostics Menu)

### Test Connectivity

**Diagnostics → Ping**
```
Hostname: 172.16.1.100
Source Address: 10.10.10.1 (MGMT)
Click Ping

Should succeed (MGMT can reach CORP)
```

**Diagnostics → Ping**
```
Hostname: 10.10.10.1
Source Address: 172.16.1.1 (CORP)
Click Ping

Should FAIL (CORP cannot reach MGMT)
```

### View Firewall Logs

**Status → System Logs → Firewall**
```
Shows all blocked and passed traffic
Filter by interface, source, destination
Real-time updates
```

### View States (Active Connections)

**Diagnostics → States**
```
Shows active connections
Similar to FortiGate session table
```

---

## Testing Matrix - Task 1

| Test | Source | Destination | Expected | Why |
|------|--------|-------------|----------|-----|
| 1 | MGMT (10.10.10.100) | CORP (172.16.1.100) | PASS | Policy: MGMT to ALL |
| 2 | MGMT (10.10.10.100) | DMZ (192.168.100.10) | PASS | Policy: MGMT to ALL |
| 3 | CORP (172.16.1.100) | DMZ (192.168.100.10) | PASS | Policy: CORP to DMZ |
| 4 | CORP (172.16.1.100) | CORP (172.16.1.101) | PASS | Policy: CORP Internal |
| 5 | CORP (172.16.1.100) | MGMT (10.10.10.1) | FAIL | Implicit deny |
| 6 | DMZ (192.168.100.10) | CORP (172.16.1.100) | FAIL | Implicit deny |
| 7 | GUEST (192.168.200.50) | CORP (172.16.1.100) | FAIL | Implicit deny |

---

## pfSense vs FortiGate Translation

| FortiGate Concept | pfSense Equivalent |
|-------------------|-------------------|
| Address Object | Alias (Firewall → Aliases) |
| Address Group | Alias with multiple entries |
| Firewall Policy | Firewall Rule (per-interface) |
| Interface Zone | Interface assignment |
| Policy Order | Rule order (top-to-bottom) |
| Implicit Deny | Default Deny (automatic) |
| Session Table | States (Diagnostics → States) |
| Traffic Logs | System Logs → Firewall |

---

## Key Differences from FortiGate

### 1. Rule Processing
```
FortiGate: Central policy table, all policies in one list
pfSense: Per-interface rules, evaluated on INBOUND interface
```

### 2. Rule Direction
```
FortiGate: srcintf + dstintf (both specified)
pfSense: Rules on source interface only (destination implied)
```

### 3. Default Behavior
```
FortiGate: Explicit deny-all at end
pfSense: Implicit deny-all (always active)
```

### 4. Stateful Inspection
```
Both: Automatically allow return traffic for established connections
```

---

## Common Issues & Solutions

### Issue: Can't access GUI
```
Check: Interface has correct IP (10.10.10.1)
Check: PC1 has IP in same subnet (10.10.10.x)
Check: PC1 gateway points to 10.10.10.1
Try: http://10.10.10.1 (not https initially)
```

### Issue: Rules not working
```
Check: Rule order (top-to-bottom matters)
Check: Applied changes after creating rules
Check: Interface assignment correct
View: Status → System Logs → Firewall
```

### Issue: Can ping gateway but not devices
```
Check: Device has correct IP and gateway
Check: DHCP enabled if using auto-IP
Check: Return traffic allowed (stateful should handle)
Check: ARP table (Diagnostics → ARP Table)
```

### Issue: Asymmetric routing
```
Fix: System → Advanced → Firewall & NAT
     Disable "Disable reply-to"
     Enable "Disable hardware checksum offload"
```

---

## Task 2 Preview (Guest ACL)

For Task 2, you'll modify GUEST rules:

```
GUEST Interface:
  Rule 1: Block RFC1918 (DENY to internal)
  Rule 2: Allow DNS (to specific servers)
  Rule 3: Allow Internet (with NAT)
```

This will be much easier in pfSense - no license limits!

---

## Backup Configuration

Once working, backup your config:

**Diagnostics → Backup & Restore**
```
Download configuration as XML
Save: pfsense-task1-config.xml
```

Can restore anytime or migrate to different pfSense instance.

---

## Next Steps

1. ✓ Set up interfaces (console)
2. ✓ Access GUI
3. ✓ Rename interfaces
4. ✓ Create aliases
5. ✓ Configure firewall rules
6. ✓ Test connectivity
7. ✓ Review logs
8. → Ready for Task 2!

---

## Quick Reference Commands

```bash
# pfSense Console Menu

1) Assign Interfaces
2) Set interface(s) IP address
8) Shell (for advanced commands)
9) pfTop (like "top" for firewall)
11) Restart webConfigurator
12) pfSense Developer Shell

# From Shell (option 8):
pfctl -sr           # Show rules
pfctl -ss           # Show states
pfctl -si           # Show statistics
tcpdump -i em0      # Packet capture on interface
```

---

## Resources

- pfSense Docs: https://docs.netgate.com/pfsense/
- Rule troubleshooting: Status → System Logs → Firewall
- Packet capture: Diagnostics → Packet Capture
- Traffic graphs: Status → Traffic Graph

**No license restrictions, unlimited rules, full logging!** 🎉
