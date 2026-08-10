"""
Server Utilities: Port detection and management.
Handles port binding issues on Windows.
"""
import socket
import subprocess
import sys
import time
from typing import Optional, Tuple


class PortManager:
    """Manage port binding and process cleanup."""
    
    @staticmethod
    def is_port_in_use(host: str = "127.0.0.1", port: int = 8000) -> bool:
        """
        Check if a port is already in use.
        
        Args:
            host: Host address (127.0.0.1 or 0.0.0.0)
            port: Port number to check
            
        Returns:
            True if port is in use, False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            
            # result == 0 means connection succeeded = port is in use
            return result == 0
        except Exception as e:
            print(f"[WARNING] Error checking port {port}: {e}")
            return False
    
    @staticmethod
    def find_free_port(host: str = "127.0.0.1", start_port: int = 8000, max_attempts: int = 10) -> Optional[int]:
        """
        Find the first available port starting from start_port.
        
        Args:
            host: Host address
            start_port: Starting port to check
            max_attempts: Maximum attempts to find free port
            
        Returns:
            Free port number or None if not found
        """
        for port in range(start_port, start_port + max_attempts):
            if not PortManager.is_port_in_use(host, port):
                return port
        return None
    
    @staticmethod
    def get_process_using_port(port: int = 8000) -> Optional[Tuple[int, str]]:
        """
        Get PID and process name using the specified port (Windows only).
        
        Args:
            port: Port number
            
        Returns:
            Tuple of (PID, process_name) or None if not found
        """
        if sys.platform != "win32":
            return None
        
        try:
            import re
            # Use netstat to find process using port
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Look for the port in output
            pattern = rf":{port}\s+.*LISTENING\s+(\d+)"
            match = re.search(pattern, result.stdout)
            
            if match:
                pid = int(match.group(1))
                
                # Get process name from PID
                try:
                    tasklist = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}", "/V"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    lines = tasklist.stdout.split('\n')
                    if len(lines) > 3:
                        proc_name = lines[3].split()[0]
                        return (pid, proc_name)
                except:
                    return (pid, "Unknown")
            
            return None
        except Exception as e:
            print(f"[WARNING] Error getting process info: {e}")
            return None
    
    @staticmethod
    def kill_process_on_port(port: int = 8000, force: bool = True) -> bool:
        """
        Kill process using the specified port (Windows only).
        
        Args:
            port: Port number
            force: Use /F flag to force kill (optional /T to kill children)
            
        Returns:
            True if successful, False otherwise
        """
        if sys.platform != "win32":
            print("[ERROR] kill_process_on_port() only works on Windows")
            return False
        
        proc_info = PortManager.get_process_using_port(port)
        if not proc_info:
            print(f"[INFO] No process found using port {port}")
            return True
        
        pid, proc_name = proc_info
        print(f"[INFO] Found process using port {port}:")
        print(f"       PID: {pid}")
        print(f"       Process: {proc_name}")
        
        try:
            # Build command
            cmd = ["taskkill", "/PID", str(pid)]
            if force:
                cmd.append("/F")
            
            print(f"[ACTION] Killing process {pid}...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                print(f"[✓] Successfully killed process {pid}")
                time.sleep(1)  # Wait for port to be released
                return True
            else:
                print(f"[✗] Failed to kill process: {result.stderr}")
                return False
        except Exception as e:
            print(f"[ERROR] Error killing process: {e}")
            return False
    
    @staticmethod
    def ensure_port_free(host: str = "127.0.0.1", port: int = 8000, 
                        kill_existing: bool = False) -> bool:
        """
        Ensure port is free, optionally killing existing process.
        
        Args:
            host: Host address
            port: Port number
            kill_existing: If True, kill process using the port
            
        Returns:
            True if port is now free, False otherwise
        """
        if PortManager.is_port_in_use(host, port):
            print(f"[WARNING] Port {port} is already in use")
            
            if kill_existing and sys.platform == "win32":
                print("[ACTION] Attempting to free port...")
                if PortManager.kill_process_on_port(port):
                    time.sleep(1)
                    if PortManager.is_port_in_use(host, port):
                        print(f"[ERROR] Port {port} still in use after killing process")
                        return False
                    print(f"[✓] Port {port} is now free")
                    return True
                else:
                    return False
            else:
                return False
        
        print(f"[✓] Port {port} is free")
        return True


def print_port_diagnostics(host: str = "127.0.0.1", port: int = 8000):
    """Print diagnostic information about port usage."""
    print("\n" + "="*70)
    print("PORT DIAGNOSTIC INFORMATION")
    print("="*70)
    
    in_use = PortManager.is_port_in_use(host, port)
    print(f"\nPort {port} Status: {'IN USE ✗' if in_use else 'FREE ✓'}")
    
    if in_use and sys.platform == "win32":
        proc_info = PortManager.get_process_using_port(port)
        if proc_info:
            pid, proc_name = proc_info
            print(f"  PID: {pid}")
            print(f"  Process: {proc_name}")
            print(f"\n  To manually kill:")
            print(f"    > tasklist | findstr {pid}")
            print(f"    > taskkill /PID {pid} /F")
        else:
            print("  Could not determine process")
    
    # Check next 5 ports
    print(f"\n  Available ports:")
    for p in range(port, port + 5):
        if not PortManager.is_port_in_use(host, p):
            print(f"    ✓ {p}")
        else:
            print(f"    ✗ {p}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    # Quick test
    print("Testing port utilities...")
    
    print("\nPort 8000 in use?", PortManager.is_port_in_use("127.0.0.1", 8000))
    print("Free port starting from 8000:", PortManager.find_free_port("127.0.0.1", 8000))
    
    print_port_diagnostics("127.0.0.1", 8000)
