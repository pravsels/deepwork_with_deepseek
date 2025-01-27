#!/usr/bin/env python3
import sys
import time
import argparse
from datetime import datetime, timedelta
import subprocess
import platform

# The hosts file location varies by OS
HOSTS_PATH = "/etc/hosts" if platform.system() != "Windows" else r"C:\Windows\System32\drivers\etc\hosts"
LOCALHOST = "127.0.0.1"

def get_admin_command():
    """Return the appropriate admin command based on the OS."""
    if platform.system() == "Windows":
        return "runas /user:Administrator "
    return "sudo "

def check_admin():
    """Check if the script has administrative privileges."""
    try:
        if platform.system() == "Windows":
            return subprocess.run("net session", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0
        return subprocess.run(["sudo", "-n", "true"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0
    except:
        return False

def flush_dns_cache():
    """Flush DNS cache to ensure changes take effect immediately."""
    try:
        # Try systemd-resolved first (most common on modern Linux systems)
        subprocess.run(["sudo", "systemctl", "restart", "systemd-resolved"], 
                      check=True, 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE)
        print("DNS cache flushed successfully")
    except subprocess.CalledProcessError:
        print("Could not flush DNS cache. You may need to restart your browser for changes to take effect.")
        
def block_websites(websites, duration_minutes):
    """Block specified websites for a given duration."""
    if not check_admin():
        print(f"Please run this script with administrative privileges:")
        print(f"{get_admin_command()}{sys.executable} {sys.argv[0]} {' '.join(sys.argv[1:])}")
        sys.exit(1)

    end_time = datetime.now() + timedelta(minutes=duration_minutes)
    
    # Add www. variant for each website
    all_sites = set()
    for site in websites:
        all_sites.add(site)
        if not site.startswith('www.'):
            all_sites.add('www.' + site)

    try:
        # Read existing hosts file
        with open(HOSTS_PATH, 'r') as file:
            hosts_content = file.readlines()

        # Filter out any existing blocked sites
        hosts_content = [line for line in hosts_content if not any(site in line for site in all_sites)]

        # Add new blocks
        with open(HOSTS_PATH, 'w') as file:
            file.writelines(hosts_content)
            file.write("\n# Website blocks added by blocker script\n")
            for site in all_sites:
                file.write(f"{LOCALHOST} {site}\n")

        # Flush DNS cache after modifying hosts file
        flush_dns_cache()

        print(f"Websites blocked until {end_time.strftime('%H:%M:%S')}")
        
        try:
            # Wait for the specified duration
            time.sleep(duration_minutes * 60)
        except KeyboardInterrupt:
            print("\nBlocking interrupted by user.")
        finally:
            # Remove the blocks
            with open(HOSTS_PATH, 'r') as file:
                hosts_content = file.readlines()
            
            # Remove our blocks
            hosts_content = [line for line in hosts_content 
                           if not any(site in line for site in all_sites) and 
                           "Website blocks added by blocker script" not in line]
            
            with open(HOSTS_PATH, 'w') as file:
                file.writelines(hosts_content)
            
            # Flush DNS cache after unblocking
            flush_dns_cache()
            print("\nWebsites unblocked.")

    except PermissionError:
        print("Error: Permission denied. Please run with administrative privileges.")
        sys.exit(1)

def read_websites_from_file(file_path):
    """Read websites from a text file, one website per line."""
    try:
        with open(file_path, 'r') as file:
            # Read lines and remove whitespace, empty lines, and comments
            websites = [line.strip() for line in file 
                       if line.strip() and not line.startswith('#')]
        return websites
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

def parse_time(time_str):
    """Parse time string with units (e.g., '30s', '30m', '2h', '1d')."""
    units = {
        's': 1/60,       # seconds
        'm': 1,          # minutes
        'h': 60,         # hours
        'd': 60 * 24,    # days
    }
    
    if str(time_str).isdigit():  # If just a number, assume minutes
        return int(time_str)
        
    unit = time_str[-1].lower()
    if unit not in units:
        print(f"Invalid time unit. Please use 's' (seconds), 'm' (minutes), 'h' (hours), or 'd' (days)")
        sys.exit(1)
        
    try:
        number = int(time_str[:-1])
        return number * units[unit]
    except ValueError:
        print(f"Invalid time format. Example formats: 45s, 30m, 2h, 1d")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Block websites for a specified duration.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-w', '--websites', nargs='+', 
                      help='Websites to block (e.g., facebook.com twitter.com)')
    group.add_argument('-f', '--file', type=str,
                      help='Path to text file containing websites to block (one per line)')
    parser.add_argument('-t', '--time', type=str, default='30m',
                        help='Duration to block (e.g., 30m, 2h, 1d). Default: 30m')
    
    args = parser.parse_args()
    
    # Get websites either from command line or file
    websites = args.websites if args.websites else read_websites_from_file(args.file)
    duration_minutes = parse_time(args.time)
    
    block_websites(websites, duration_minutes)

if __name__ == "__main__":
    main()

    