# Improved version with additional features and better error handling
import sys
import argparse
import logging
from datetime import datetime, timedelta
import subprocess
import platform
from pathlib import Path
import asyncio
import signal
from typing import Set, List
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_admin() -> bool:
    """Check if the script has administrative privileges."""
    try:
        if platform.system() == "Windows":
            return subprocess.run("net session", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0
        return subprocess.run(["sudo", "-n", "true"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0
    except:
        return False

def get_admin_command() -> str:
    """Return the appropriate admin command based on the OS."""
    if platform.system() == "Windows":
        return "runas /user:Administrator "
    return "sudo "

class WebsiteBlocker:
    def __init__(self):
        self.HOSTS_PATH = Path("/etc/hosts" if platform.system() != "Windows" else r"C:\Windows\System32\drivers\etc\hosts")
        self.LOCALHOST = "127.0.0.1"
        self.BLOCK_MARKER = "# Website blocks added by blocker script"
        self._validate_hosts_path()

    def _validate_hosts_path(self) -> None:
        """Validate that the hosts file exists and is accessible."""
        if not self.HOSTS_PATH.exists():
            raise FileNotFoundError(f"Hosts file not found at {self.HOSTS_PATH}")
        if not self.HOSTS_PATH.is_file():
            raise ValueError(f"Hosts path {self.HOSTS_PATH} is not a regular file")

    @staticmethod
    def is_valid_domain(domain: str) -> bool:
        """Validate domain name format."""
        pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        return bool(re.match(pattern, domain))

    def expand_domains(self, domains: Set[str]) -> Set[str]:
        """Add www. variant for each domain if not present."""
        expanded = set()
        for domain in domains:
            if not self.is_valid_domain(domain):
                logger.warning(f"Skipping invalid domain: {domain}")
                continue
            expanded.add(domain)
            if not domain.startswith('www.'):
                expanded.add('www.' + domain)
        return expanded

    async def flush_dns_cache(self) -> None:
        """Flush DNS cache asynchronously with better error handling."""
        try:
            if platform.system() == "Windows":
                await asyncio.create_subprocess_shell("ipconfig /flushdns")
            elif platform.system() == "Darwin":  # macOS
                await asyncio.create_subprocess_shell("dscacheutil -flushcache")
                await asyncio.create_subprocess_shell("killall -HUP mDNSResponder")
            else:  # Linux
                try:
                    await asyncio.create_subprocess_shell("sudo systemctl restart systemd-resolved")
                except:
                    await asyncio.create_subprocess_shell("sudo service network-manager restart")
            
            logger.info("DNS cache flushed successfully")
        except Exception as e:
            logger.warning(f"Could not flush DNS cache: {e}")
            logger.info("You may need to restart your browser for changes to take effect")

    async def modify_hosts_file(self, domains: Set[str], add_blocks: bool = True) -> None:
        """Modify hosts file to add or remove domain blocks."""
        try:
            hosts_content = self.HOSTS_PATH.read_text().splitlines()
            
            # Remove existing blocks
            hosts_content = [line for line in hosts_content 
                           if not any(domain in line for domain in domains) 
                           and self.BLOCK_MARKER not in line]

            if add_blocks:
                hosts_content.append(self.BLOCK_MARKER)
                for domain in domains:
                    hosts_content.append(f"{self.LOCALHOST} {domain}")

            self.HOSTS_PATH.write_text('\n'.join(hosts_content) + '\n')
            await self.flush_dns_cache()
            
        except Exception as e:
            logger.error(f"Error modifying hosts file: {e}")
            raise

    async def block_websites(self, websites: List[str], duration: float) -> None:
        """Block specified websites for a given duration."""
        if not check_admin():
            raise PermissionError("Administrative privileges required")

        domains = self.expand_domains(set(websites))
        end_time = datetime.now() + timedelta(minutes=duration)
        
        try:
            # Set up signal handlers
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.cleanup(domains, s)))

            logger.info(f"Blocking {len(domains)} domains until {end_time.strftime('%H:%M:%S')}")
            await self.modify_hosts_file(domains, add_blocks=True)
            
            try:
                await asyncio.sleep(duration * 60)
            except asyncio.CancelledError:
                logger.info("Blocking interrupted by user")
            
            await self.cleanup(domains)

        except Exception as e:
            logger.error(f"Error during website blocking: {e}")
            await self.cleanup(domains)
            raise

    async def cleanup(self, domains: Set[str], sig = None) -> None:
        """Clean up blocks and handle program termination."""
        if sig:
            logger.info(f"Received signal {sig.name}, cleaning up...")
        
        await self.modify_hosts_file(domains, add_blocks=False)
        logger.info("Websites unblocked")

def parse_duration(time_str: str) -> float:
    """Parse time string with improved validation and error handling."""
    units = {
        's': 1/60,
        'm': 1,
        'h': 60,
        'd': 1440
    }
    
    match = re.match(r'^(\d+)([smhd])?$', time_str.lower())
    if not match:
        raise ValueError(
            "Invalid time format. Use: \n"
            "- Plain number (e.g., '30') for minutes\n"
            "- Time with units: '45s', '30m', '2h', '1d'"
        )
    
    number, unit = match.groups()
    return int(number) * units.get(unit, 1)  # Default to minutes if no unit specified

async def main():
    parser = argparse.ArgumentParser(
        description='Block distracting websites for a specified duration.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-f', '--file', type=Path, default='distractions.txt',
                      help='Path to text file containing websites to block (one per line)')
    parser.add_argument('-t', '--time', type=str, default='30s',
                        help='Duration to block (e.g., 10s, 45m, 2h, 1d). Default: 30s')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')

    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        websites = [line.strip() for line in args.file.read_text().splitlines() 
                   if line.strip() and not line.startswith('#')]
        duration = parse_duration(args.time)
        
        blocker = WebsiteBlocker()
        await blocker.block_websites(websites, duration)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

