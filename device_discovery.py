#!/usr/bin/env python3
"""
Device Discovery and Reachability Testing Module
Supports ping sweeps, port scans, and connectivity validation across network segments
"""

import subprocess
import ipaddress
import socket
import concurrent.futures
from typing import List, Dict, Tuple
import json
from datetime import datetime


class NetworkScanner:
    """Handles device discovery across network segments"""
    
    def __init__(self, segments: Dict[str, str]):
        """
        Initialize scanner with network segments
        
        Args:
            segments: Dictionary of segment names to CIDR notation
                     e.g., {'MGMT': '10.10.10.0/24', 'CORP': '172.16.1.0/24'}
        """
        self.segments = segments
        self.discovered_hosts = {}
    
    def ping_host(self, ip: str, timeout: int = 2) -> bool:
        """
        Ping a single host to check reachability
        
        Args:
            ip: IP address to ping
            timeout: Timeout in seconds
            
        Returns:
            True if host is reachable, False otherwise
        """
        try:
            # Use -c 1 for Linux/Mac, -n 1 for Windows
            param = '-n' if subprocess.os.name == 'nt' else '-c'
            command = ['ping', param, '1', '-W', str(timeout), ip]
            
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout + 1
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception):
            return False
    
    def scan_port(self, ip: str, port: int, timeout: float = 1.0) -> bool:
        """
        Check if a specific port is open on a host
        
        Args:
            ip: Target IP address
            port: Port number to check
            timeout: Connection timeout
            
        Returns:
            True if port is open, False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def scan_segment(self, segment_name: str, max_workers: int = 50) -> List[str]:
        """
        Scan an entire network segment for active hosts
        
        Args:
            segment_name: Name of segment to scan (must be in self.segments)
            max_workers: Number of concurrent threads
            
        Returns:
            List of active IP addresses
        """
        if segment_name not in self.segments:
            raise ValueError(f"Segment {segment_name} not defined")
        
        network = ipaddress.ip_network(self.segments[segment_name])
        active_hosts = []
        
        print(f"[*] Scanning {segment_name} ({self.segments[segment_name]})...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit ping jobs for all hosts in subnet
            future_to_ip = {
                executor.submit(self.ping_host, str(ip)): str(ip) 
                for ip in network.hosts()
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    if future.result():
                        active_hosts.append(ip)
                        print(f"  [+] Found: {ip}")
                except Exception as e:
                    print(f"  [!] Error scanning {ip}: {e}")
        
        self.discovered_hosts[segment_name] = active_hosts
        return active_hosts
    
    def scan_all_segments(self) -> Dict[str, List[str]]:
        """
        Scan all defined network segments
        
        Returns:
            Dictionary mapping segment names to lists of active hosts
        """
        print(f"\n{'='*60}")
        print(f"Starting Network Discovery - {datetime.now()}")
        print(f"{'='*60}\n")
        
        for segment_name in self.segments:
            self.scan_segment(segment_name)
        
        return self.discovered_hosts
    
    def port_scan_host(self, ip: str, ports: List[int] = None) -> Dict[int, bool]:
        """
        Scan multiple ports on a single host
        
        Args:
            ip: Target IP address
            ports: List of ports to scan (default: common ports)
            
        Returns:
            Dictionary mapping port numbers to open/closed status
        """
        if ports is None:
            ports = [22, 80, 443, 3389, 8080, 8443]  # Common ports
        
        results = {}
        print(f"\n[*] Port scanning {ip}...")
        
        for port in ports:
            is_open = self.scan_port(ip, port)
            results[port] = is_open
            status = "OPEN" if is_open else "closed"
            print(f"  Port {port}: {status}")
        
        return results
    
    def generate_report(self, filename: str = "discovery_report.json"):
        """
        Generate a JSON report of discovered devices
        
        Args:
            filename: Output filename
        """
        report = {
            "scan_time": datetime.now().isoformat(),
            "segments": self.segments,
            "discovered_hosts": self.discovered_hosts,
            "summary": {
                segment: len(hosts) 
                for segment, hosts in self.discovered_hosts.items()
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n[*] Report saved to {filename}")


class ReachabilityTester:
    """Tests connectivity between network segments according to access policies"""
    
    def __init__(self, access_matrix: Dict[str, Dict[str, bool]]):
        """
        Initialize with access control matrix
        
        Args:
            access_matrix: Nested dict defining allowed connections
                          e.g., {'MGMT': {'CORP': True, 'GUEST': False}}
        """
        self.access_matrix = access_matrix
        self.test_results = []
    
    def test_connectivity(self, source_ip: str, dest_ip: str, 
                         source_segment: str, dest_segment: str) -> Dict:
        """
        Test connectivity between two hosts and validate against policy
        
        Args:
            source_ip: Source host IP
            dest_ip: Destination host IP
            source_segment: Name of source segment
            dest_segment: Name of destination segment
            
        Returns:
            Dictionary with test results
        """
        # Check if connection should be allowed
        expected = self.access_matrix.get(source_segment, {}).get(dest_segment, False)
        
        # Test actual connectivity
        scanner = NetworkScanner({})
        actual = scanner.ping_host(dest_ip)
        
        result = {
            "source": f"{source_ip} ({source_segment})",
            "destination": f"{dest_ip} ({dest_segment})",
            "expected": "ALLOW" if expected else "DENY",
            "actual": "REACHABLE" if actual else "BLOCKED",
            "status": "PASS" if (expected == actual) else "FAIL",
            "timestamp": datetime.now().isoformat()
        }
        
        self.test_results.append(result)
        return result
    
    def run_test_suite(self, test_scenarios: List[Tuple[str, str, str, str]]):
        """
        Run a suite of connectivity tests
        
        Args:
            test_scenarios: List of tuples (source_ip, dest_ip, src_seg, dst_seg)
        """
        print(f"\n{'='*60}")
        print(f"Running Reachability Tests")
        print(f"{'='*60}\n")
        
        for source_ip, dest_ip, src_seg, dst_seg in test_scenarios:
            result = self.test_connectivity(source_ip, dest_ip, src_seg, dst_seg)
            
            status_symbol = "✓" if result["status"] == "PASS" else "✗"
            print(f"{status_symbol} {result['source']} → {result['destination']}")
            print(f"  Expected: {result['expected']}, Actual: {result['actual']}")
            print()
    
    def generate_report(self, filename: str = "reachability_report.json"):
        """Generate test results report"""
        passed = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed = sum(1 for r in self.test_results if r["status"] == "FAIL")
        
        report = {
            "test_time": datetime.now().isoformat(),
            "summary": {
                "total": len(self.test_results),
                "passed": passed,
                "failed": failed,
                "pass_rate": f"{(passed/len(self.test_results)*100):.1f}%" if self.test_results else "N/A"
            },
            "results": self.test_results
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n[*] Test report saved to {filename}")


if __name__ == "__main__":
    # Example usage
    segments = {
        'MGMT': '10.10.10.0/24',
        'CORP': '172.16.1.0/24',
        'DMZ': '192.168.100.0/24',
        'GUEST': '192.168.200.0/24'
    }
    
    # Discover devices
    scanner = NetworkScanner(segments)
    discovered = scanner.scan_all_segments()
    scanner.generate_report()
    
    # Define access control policy
    access_matrix = {
        'MGMT': {'MGMT': True, 'CORP': True, 'DMZ': True, 'GUEST': True},
        'CORP': {'MGMT': False, 'CORP': True, 'DMZ': True, 'GUEST': False},
        'DMZ': {'MGMT': False, 'CORP': False, 'DMZ': True, 'GUEST': False},
        'GUEST': {'MGMT': False, 'CORP': False, 'DMZ': True, 'GUEST': True}
    }
    
    # Test reachability (examples - adjust IPs based on your actual devices)
    tester = ReachabilityTester(access_matrix)
    test_scenarios = [
        ('10.10.10.100', '172.16.1.100', 'MGMT', 'CORP'),      # Should work
        ('172.16.1.100', '10.10.10.100', 'CORP', 'MGMT'),      # Should fail
        ('172.16.1.100', '192.168.100.10', 'CORP', 'DMZ'),     # Should work
        ('192.168.200.50', '172.16.1.100', 'GUEST', 'CORP'),   # Should fail
    ]
    
    tester.run_test_suite(test_scenarios)
    tester.generate_report()
