"""
Build Script for Overcontrol
Creates production executable using PyInstaller with WebView2 Bootstrapper approach.
This creates a ~5-10MB installer instead of ~400MB by not bundling WebView2.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

# Configuration
APP_NAME = "Overcontrol"
MAIN_SCRIPT = "run.py"
ICON_PATH = "app/assets/icons/app-icon.ico"  # Create this if you have one
VERSION = "1.0.0"

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# Read version from app/version.py
try:
    sys.path.append(str(PROJECT_ROOT))
    from app.version import APP_VERSION
    VERSION = APP_VERSION
except ImportError:
    VERSION = "1.0.2"

def clean_build_dirs():
    """Remove previous build artifacts."""
    print("Cleaning previous build directories...")
    
    def on_rm_error(func, path, exc_info):
        """
        Error handler for ``shutil.rmtree``.
        If the error is due to an access error (read only file)
        it attempts to add write permission and then retries.
        If the error is because the file is being used by another process, it waits and retries.
        """
        import stat
        import time
        
        # Is the error an access error?
        if not os.access(path, os.W_OK):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        else:
            # Maybe locked? Wait a bit
            try:
                time.sleep(0.1)
                func(path)
            except Exception as e:
                print(f"  [WARNING] Could not delete {path}: {e}")

    for dir_path in [DIST_DIR, BUILD_DIR]:
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path, onerror=on_rm_error)
                print(f"  [OK] Removed {dir_path}")
            except Exception as e:
                print(f"  [ERROR] Failed to remove {dir_path}: {e}")
                print("  Please close any folders or files in the build directory and try again.")
    print()

def create_pyinstaller_spec():
    """Create PyInstaller spec file with WebView2 bootstrapper approach."""
    

    # Dynamic datas generation
    data_items = [
        ("app/assets", "app/assets"),           # Include HTML/CSS/JS assets
        ("config.template.json", "."),          # Include config template
    ]
    
    # Optional files/folders
    checks = {
        "config.json": ".",
        ".env.example": ".",
        "firmware": "firmware"
    }
    
    for path, dst in checks.items():
        if (PROJECT_ROOT / path).exists():
            data_items.append((path, dst))
            print(f"  [INFO] Including found optional item: {path}")
        else:
            print(f"  [INFO] Skipping missing optional item: {path}")

    # Format into python list string
    datas_str = ",\n        ".join([f"('{src}', '{dst}')" for src, dst in data_items])

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# Collect data for jaraco.text (fixes Lorem ipsum.txt error) and others
tmp_ret = collect_all('jaraco.text')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Fix: setuptools vendored jaraco.text expects files in specific location
# Duplicate jaraco.text datas to setuptools/_vendor/jaraco/text
jaraco_datas = tmp_ret[0]
for src, dst in jaraco_datas:
    if dst.startswith('jaraco'):
        # Create new destination path inside setuptools/_vendor
        new_dst = os.path.join('setuptools', '_vendor', dst)
        datas.append((src, new_dst))

tmp_ret = collect_all('jaraco.classes')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

block_cipher = None

a = Analysis(
    ['{MAIN_SCRIPT}'],
    pathex=[],
    binaries=binaries,
    datas=datas + [
        {datas_str}
    ],
    hiddenimports=hiddenimports + [
        'PIL._tkinter_finder',
        'pystray._win32',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
# Filter out unnecessary files
a.datas = [x for x in a.datas if not x[0].startswith('tcl')]
a.datas = [x for x in a.datas if not x[0].startswith('tk')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='scripts/version_info.txt',
    # icon='{ICON_PATH}',  # Uncomment if you have an icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='{APP_NAME}',
)
'''
    
    spec_path = PROJECT_ROOT / f"{APP_NAME.replace(' ', '_')}.spec"
    with open(spec_path, 'w') as f:
        f.write(spec_content)
    
    print(f"[OK] Created PyInstaller spec: {spec_path}")
    return spec_path

def build_executable(spec_path):
    """Run PyInstaller to create the executable."""
    print(f"\nBuilding executable using PyInstaller...")
    print("This may take a few minutes...\n")
    
    try:
        result = subprocess.run(
            ["pyinstaller", "--clean", "--noconfirm", str(spec_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("[OK] Build completed successfully!")
            return True
        else:
            print("[ERROR] Build failed!")
            print("\nError output:")
            print(result.stderr)
            return False
            
    except FileNotFoundError:
        print("[ERROR] PyInstaller not found!")
        print("Install it with: pip install pyinstaller")
        return False
    except Exception as e:
        print(f"[ERROR] Build error: {e}")
        return False

def create_readme():
    """Create README for distribution."""
    readme_content = f"""# {APP_NAME} v{VERSION}

## Installation

1. Extract all files to a folder
2. Run `{APP_NAME}.exe`
3. On first run, WebView2 Runtime will be downloaded and installed automatically if not present

## System Requirements

- Windows 10/11 (64-bit)
- .NET Framework 4.7.2 or higher
- USB port for NodeMCU device
- Internet connection (first run only, for WebView2)

## Configuration

Create a `.env` file in the same directory as the executable with your GitHub token:

```
GITHUB_TOKEN=your_github_token_here
```

See `.env.example` for more details.

## Troubleshooting

**WebView2 Installation Issues:**
If automatic WebView2 installation fails, download and install manually:
https://developer.microsoft.com/microsoft-edge/webview2/

**Application won't start:**
- Ensure .NET Framework 4.7.2+ is installed
- Run as Administrator
- Check Windows Defender / Antivirus

## Support

For issues and updates, visit the project repository.
"""
    
    dist_path = DIST_DIR / APP_NAME
    readme_path = dist_path / "README.txt"
    
    if dist_path.exists():
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        print(f"[OK] Created README: {readme_path}")

def get_dist_size():
    """Calculate total size of distribution folder."""
    dist_path = DIST_DIR / APP_NAME
    if not dist_path.exists():
        return 0
    
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(dist_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            total_size += os.path.getsize(filepath)
    
    return total_size / (1024 * 1024)  # Convert to MB

def main():
    """Main build process."""
    print("="*60)
    print(f"Building {APP_NAME} v{VERSION}")
    print("Using WebView2 Bootstrapper Approach (No bundled runtime)")
    print("="*60)
    print()
    
    # Step 1: Clean
    clean_build_dirs()
    
    # Step 2: Create spec file
    spec_path = create_pyinstaller_spec()
    
    # Step 3: Build
    if not build_executable(spec_path):
        print("\n[ERROR] Build process failed!")
        sys.exit(1)
    
    # Step 4: Create README
    create_readme()
    
    # Step 5: Report results
    size_mb = get_dist_size()
    print("\n" + "="*60)
    print("BUILD SUMMARY")
    print("="*60)
    print(f"Distribution folder: {DIST_DIR / APP_NAME}")
    print(f"Total size: {size_mb:.1f} MB")
    print(f"Estimated installer size: ~{size_mb + 2:.1f} MB")
    print("\nCompare to bundled WebView2 approach: ~400 MB")
    print(f"Size reduction: ~{400 - size_mb:.0f} MB ({((400-size_mb)/400*100):.0f}%)")
    print("="*60)
    print("\n[OK] Build complete! Ready for installer creation.")

if __name__ == "__main__":
    main()
