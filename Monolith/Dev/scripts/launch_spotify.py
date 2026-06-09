import os
import sys
import time
import subprocess
import win32gui
import win32process
import win32con
import psutil

def kill_spotify():
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] and proc.info['name'].lower() == 'spotify.exe':
            try:
                proc.kill()
            except Exception:
                pass

def find_spotify_windows():
    hwnds = []
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            class_name = win32gui.GetClassName(hwnd)
            if class_name == 'Chrome_WidgetWin_0':
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc = psutil.Process(pid)
                    if proc.name().lower() == 'spotify.exe':
                        # Check that the window has a title (to filter out auxiliary background windows)
                        title = win32gui.GetWindowText(hwnd)
                        if title:
                            extra.append(hwnd)
                except Exception:
                    pass
        return True
    win32gui.EnumWindows(callback, hwnds)
    return hwnds

def main():
    print("Closing existing Spotify instances...")
    kill_spotify()
    time.sleep(0.5)
    
    spotify_path = os.path.expandvars('%APPDATA%\\Spotify\\Spotify.exe')
    if not os.path.exists(spotify_path):
        print(f"Error: Spotify.exe not found at {spotify_path}")
        sys.exit(1)
        
    print(f"Launching Spotify from {spotify_path}...")
    subprocess.Popen([spotify_path])
    
    # Wait for the Spotify window to appear and minimize it
    print("Waiting for Spotify window to minimize...")
    for _ in range(30): # Wait up to 15 seconds
        time.sleep(0.5)
        hwnds = find_spotify_windows()
        if hwnds:
            for hwnd in hwnds:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWMINIMIZED)
            print("Spotify minimized successfully!")
            return
            
    print("Timed out waiting for Spotify window.")

if __name__ == '__main__':
    main()
