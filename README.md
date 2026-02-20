# Network Lab Project - Client Demo Infrastructure

## Project Overview

This project builds a complete network infrastructure lab for client demonstration purposes. The lab includes multiple network segments with access controls, FortiGate firewall configuration, and automated testing capabilities.

**Primary Use Case:** Enterprise network simulation with segmented architecture for MGMT, CORP, DMZ, and GUEST networks.

## Technology Stack

- **Network Simulation:** GNS3
- **Firewall:** FortiGate 121F (FortiOS)
- **Switches:** Aruba switches
- **Automation:** Python 3.10+ and Ansible
- **Development Environment:** VSCode on macOS, testing on Windows Server

## Project Structure

```
network_lab_project/
├── requirements.txt                    # Python dependencies
├── README.md                          # This file
├── task1_device_discovery/            # Task 1: Network Segmentation
│   ├── README.md                      # Task-specific documentation
│   ├── device_discovery.py            # Network scanner and discovery
│   ├── fortigate_config.py            # FortiGate configuration generator
│   ├── gns3_topology.py              # GNS3 topology automation
│   ├── ansible_inventory.yml          # Ansible device inventory
│   └── ansible_playbook.yml           # Automated testing playbook
├── task2_[next_task]/                 # Future tasks
└── shared/                            # Shared utilities and libraries
    ├── utils.py
    └── config_templates/
```

## Task 1: Device Discovery and Reachability

### Objective
Implement network segmentation with controlled access between segments, demonstrating both allowed and denied traffic flows.

### Network Architecture

**Segments:**
- **MGMT** (10.10.10.0/24) - Management network with full access
- **CORP** (172.16.1.0/24) - Corporate users with limited access
- **DMZ** (192.168.100.0/24) - Public-facing services (web, database)
- **GUEST** (192.168.200.0/24) - Guest network with minimal access

**Access Control Matrix:**
```
         MGMT  CORP  DMZ  GUEST
MGMT      ✓     ✓    ✓     ✓
CORP      ✗     ✓    ✓     ✗
DMZ       ✗     ✗    ✓     ✗
GUEST     ✗     ✗    ✓     ✓
```

## Setup Instructions

### 1. Prerequisites

#### On macOS (Development):
```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.10+
brew install python@3.11

# Install nmap for network scanning
brew install nmap

# Install GNS3 (download from gns3.com)
# Download from: https://www.gns3.com/software/download
```

#### On Windows Server (Testing):
```powershell
# Install Python from python.org
# Install nmap from nmap.org
# Install GNS3 from gns3.com
```

### 2. Python Environment Setup

```bash
# Clone or navigate to project directory
cd network_lab_project

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Ansible Setup

```bash
# Install Ansible (macOS)
brew install ansible

# Verify installation
ansible --version

# Test inventory
cd task1_device_discovery
ansible-inventory -i ansible_inventory.yml --list
```

### 4. GNS3 Configuration

1. **Start GNS3** and ensure the server is running
2. **Import Appliances:**
   - FortiGate 121F VM image
   - Ubuntu Docker images for Linux endpoints
   - Aruba switch images (if available)
   - VPCS for simple endpoints

3. **Configure GNS3 Server:**
   - Go to Edit → Preferences → Server
   - Ensure local server is enabled on port 3080
   - Enable remote connections if needed

### 5. FortiGate Image Setup

```bash
# FortiGate image should be:
# - Version 7.x or later
# - Imported as a QEMU VM in GNS3
# - Configured with at least 4 network interfaces

# Default credentials (change in production):
# Username: admin
# Password: (blank initially, set to Admin123!)
```

## Running Task 1

### Step 1: Generate FortiGate Configuration

```bash
cd task1_device_discovery

# Generate FortiGate configuration file
python3 fortigate_config.py

# Output: fortigate_task1_config.txt
```

### Step 2: Build GNS3 Topology

```bash
# Option A: Use Python script (requires GNS3 API)
python3 gns3_topology.py

# Option B: Manual setup in GNS3 GUI
# 1. Create new project "Task1_NetworkSegmentation"
# 2. Add FortiGate node (4 interfaces)
# 3. Add 4 Ethernet switches
# 4. Add endpoint devices as specified in README
# 5. Connect devices according to topology diagram
```

### Step 3: Configure FortiGate

```bash
# Method 1: Copy configuration via console
# 1. Start FortiGate in GNS3
# 2. Open console
# 3. Paste configuration from fortigate_task1_config.txt

# Method 2: Use SSH (after basic network is up)
ssh admin@10.10.10.1
# Paste configuration sections
```

### Step 4: Configure Endpoints

```bash
# For each endpoint, configure IP addresses:

# Admin Workstation (MGMT):
# IP: 10.10.10.100/24
# Gateway: 10.10.10.1

# Corp PC (CORP):
# IP: 172.16.1.100/24
# Gateway: 172.16.1.1

# Corp Linux (CORP):
# IP: 172.16.1.101/24
# Gateway: 172.16.1.1

# DMZ Web Server:
# IP: 192.168.100.10/24
# Gateway: 192.168.100.1

# DMZ DB Server:
# IP: 192.168.100.11/24
# Gateway: 192.168.100.1

# Guest Laptop:
# IP: 192.168.200.50/24
# Gateway: 192.168.200.1
```

### Step 5: Run Discovery and Testing

```bash
# Run Python-based discovery
python3 device_discovery.py

# This will:
# 1. Scan all network segments
# 2. Discover active hosts
# 3. Test connectivity between segments
# 4. Generate reports (discovery_report.json, reachability_report.json)

# Run Ansible playbook for comprehensive testing
ansible-playbook -i ansible_inventory.yml ansible_playbook.yml

# View results
cat test_results/task1_test_report.json
```

### Step 6: Verify Access Controls

Test connectivity manually:

```bash
# From MGMT (should work):
ping 172.16.1.100     # To CORP
ping 192.168.100.10   # To DMZ
ping 192.168.200.50   # To GUEST

# From CORP (should work):
ping 192.168.100.10   # To DMZ

# From CORP (should fail):
ping 10.10.10.100     # To MGMT - SHOULD TIMEOUT
ping 192.168.200.50   # To GUEST - SHOULD TIMEOUT

# From GUEST (should work):
ping 192.168.100.10   # To DMZ

# From GUEST (should fail):
ping 172.16.1.100     # To CORP - SHOULD TIMEOUT
```

## Troubleshooting

### GNS3 Issues
- **Server not responding:** Check GNS3 → Preferences → Server settings
- **Nodes not starting:** Verify VM images are properly imported
- **No connectivity:** Check cable connections in topology

### FortiGate Issues
- **Can't access console:** Right-click node → Console
- **Configuration not applying:** Check syntax, use `diagnose debug config-error-log read` for errors
- **Policies not working:** Verify with `diagnose firewall policy list`

### Python Issues
- **Import errors:** Ensure virtual environment is activated and requirements are installed
- **Permission denied:** Run with appropriate privileges or adjust file permissions
- **Network unreachable:** Verify you're running from a host that can reach the management network

## Validation Checklist

- [ ] All network segments are discoverable
- [ ] FortiGate has 4 configured interfaces
- [ ] MGMT can reach all other segments
- [ ] CORP can reach DMZ but not MGMT or GUEST
- [ ] GUEST can only reach DMZ
- [ ] DMZ cannot initiate connections to other segments
- [ ] Discovery script finds all expected hosts
- [ ] Reachability tests pass/fail as expected
- [ ] Firewall logs show blocked traffic attempts

## Next Steps

After completing Task 1:
1. Review test reports and logs
2. Document any deviations from expected behavior
3. Prepare for Task 2 (TBD based on client requirements)
4. Consider adding monitoring/alerting capabilities

## Resources

- **FortiGate CLI Reference:** https://docs.fortinet.com/product/fortigate
- **GNS3 Documentation:** https://docs.gns3.com/
- **Ansible Networking:** https://docs.ansible.com/ansible/latest/network/index.html
- **Python Networking:** https://realpython.com/python-sockets/

## Support

For questions or issues:
1. Check troubleshooting section above
2. Review task-specific README files
3. Consult vendor documentation
4. Review code comments for implementation details

## License

Internal use only - Client demonstration project
