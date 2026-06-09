"""
WebView2 Runtime Bootstrapper
Checks for WebView2 installation and downloads if needed.
This dramatically reduces installer size from ~400MB to ~5MB.
"""
import os
import sys
import subprocess
import urllib.request
import winreg
from pathlib import Path

class WebView2Bootstrapper:
    """Handles WebView2 runtime detection and installation."""
    
    # Official Microsoft WebView2 Runtime bootstrapper
    WEBVIEW2_BOOTSTRAPPER_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
    BOOTSTRAPPER_FILENAME = "MicrosoftEdgeWebview2Setup.exe"
    
    def __init__(self):
        self.bootstrapper_path = Path(self.BOOTSTRAPPER_FILENAME)
    
    def is_webview2_installed(self):
        """
        Check if WebView2 Runtime is installed on the system.
        Checks the registry for the installation.
        """
        try:
            # Check both 64-bit and 32-bit registry paths
            registry_paths = [
                r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
                r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
            ]
            
            for reg_path in registry_paths:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                        version, _ = winreg.QueryValueEx(key, "pv")
                        if version:
                            print(f"[OK] WebView2 Runtime found: v{version}")
                            return True
                except FileNotFoundError:
                    continue
                except Exception as e:
                    print(f"Warning: Registry check error: {e}")
                    continue
            
            # Also check current user registry
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                   r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}") as key:
                    version, _ = winreg.QueryValueEx(key, "pv")
                    if version:
                        print(f"[OK] WebView2 Runtime found (User): v{version}")
                        return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"Error checking WebView2 installation: {e}")
            return False
    
    def download_bootstrapper(self):
        """Download the WebView2 Runtime bootstrapper."""
        print(f"Downloading WebView2 Runtime installer...")
        
        import time
        start_time = time.time()
        last_update = [0.0]  # Store state in a mutable structure
        
        def reporthook(block_num, block_size, total_size):
            current_time = time.time()
            # Throttle console updates to max once per 0.2 seconds to avoid console lag
            if current_time - last_update[0] < 0.2 and block_num * block_size < total_size:
                return
            last_update[0] = current_time
            
            downloaded = block_num * block_size
            elapsed_time = current_time - start_time
            if elapsed_time <= 0:
                elapsed_time = 0.01
                
            speed = downloaded / elapsed_time  # Bytes per second
            
            # Format speed
            if speed > 1024 * 1024:
                speed_str = f"{speed / (1024 * 1024):.2f} MB/s"
            elif speed > 1024:
                speed_str = f"{speed / 1024:.1f} KB/s"
            else:
                speed_str = f"{speed:.0f} B/s"
                
            downloaded_mb = downloaded / (1024 * 1024)
            
            if total_size > 0:
                total_mb = total_size / (1024 * 1024)
                percent = (downloaded / total_size) * 100
                sys.stdout.write(f"\rDownloaded {downloaded_mb:.2f} MB of {total_mb:.2f} MB ({percent:.1f}%) at {speed_str}...")
            else:
                sys.stdout.write(f"\rDownloaded {downloaded_mb:.2f} MB at {speed_str}...")
            sys.stdout.flush()

        try:
            urllib.request.urlretrieve(
                self.WEBVIEW2_BOOTSTRAPPER_URL,
                self.bootstrapper_path,
                reporthook=reporthook
            )
            print("\n[OK] Download complete!")
            return True
        except Exception as e:
            print(f"\n[ERROR] Failed to download WebView2 installer: {e}")
            return False
    
    def install_webview2(self, silent=True):
        """
        Run the WebView2 Runtime installer.
        
        Args:
            silent: If True, runs silent installation. If False, shows UI.
        """
        if not self.bootstrapper_path.exists():
            if not self.download_bootstrapper():
                return False
        
        print("Installing WebView2 Runtime...")
        try:
            if silent:
                # Silent installation
                result = subprocess.run(
                    [str(self.bootstrapper_path), "/silent", "/install"],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
            else:
                # Interactive installation
                result = subprocess.run(
                    [str(self.bootstrapper_path), "/install"],
                    timeout=300
                )
            
            if result.returncode == 0:
                print("[OK] WebView2 Runtime installed successfully")
                # Clean up installer
                self.cleanup()
                return True
            else:
                print(f"[ERROR] Installation failed with code: {result.returncode}")
                if result.stderr:
                    print(f"Error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("[ERROR] Installation timed out")
            return False
        except Exception as e:
            print(f"[ERROR] Installation error: {e}")
            return False
    
    def cleanup(self):
        """Remove the downloaded bootstrapper."""
        try:
            if self.bootstrapper_path.exists():
                self.bootstrapper_path.unlink()
                print("[OK] Cleaned up installer file")
        except Exception as e:
            print(f"Warning: Could not remove installer: {e}")
    
    def ensure_runtime(self, interactive=False):
        """
        Ensure WebView2 Runtime is installed.
        If not installed, download and install it.
        
        Args:
            interactive: If True, shows installation UI. If False, silent install.
        
        Returns:
            bool: True if runtime is available, False otherwise
        """
        if self.is_webview2_installed():
            return True
        
        print("\nWebView2 Runtime not found.")
        print("MacroPad Pro requires Microsoft Edge WebView2 Runtime to function.")
        
        if interactive:
            response = input("\nWould you like to install it now? (y/n): ")
            if response.lower() != 'y':
                print("\nCannot continue without WebView2 Runtime.")
                print("Please install it manually from:")
                print("https://developer.microsoft.com/microsoft-edge/webview2/")
                return False
        else:
            print("Attempting automatic installation...")
        
        # Download and install
        if self.install_webview2(silent=not interactive):
            # Verify installation
            if self.is_webview2_installed():
                return True
            else:
                print("\n[ERROR] Installation completed but runtime not detected.")
                print("Please restart the application or install manually.")
                return False
        else:
            print("\n[ERROR] Failed to install WebView2 Runtime.")
            print("Please install manually from:")
            print("https://developer.microsoft.com/microsoft-edge/webview2/")
            return False


def ensure_webview2_runtime(interactive=False):
    """
    Convenience function to ensure WebView2 is installed.
    Call this at the start of your application.
    
    Args:
        interactive: If True, prompts user. If False, tries silent install.
    
    Returns:
        bool: True if WebView2 is available, False otherwise
    """
    bootstrapper = WebView2Bootstrapper()
    return bootstrapper.ensure_runtime(interactive=interactive)


if __name__ == "__main__":
    """
    Run standalone to check/install WebView2 Runtime.
    Usage: python webview2_bootstrapper.py [--interactive]
    """
    interactive = "--interactive" in sys.argv or "-i" in sys.argv
    
    print("="*60)
    print("WebView2 Runtime Checker & Installer")
    print("="*60)
    
    success = ensure_webview2_runtime(interactive=interactive)
    
    if success:
        print("\n[OK] WebView2 Runtime is ready!")
        sys.exit(0)
    else:
        print("\n[ERROR] WebView2 Runtime is not available.")
        sys.exit(1)
