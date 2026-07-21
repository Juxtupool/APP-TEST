# Overcontrol - Setup and Build Guide

## Overview

This document provides complete instructions for setting up the development environment, building production executables, and creating installers for Overcontrol.

---

## Development Setup

### Prerequisites

- **Windows 10/11** (64-bit)
- **Python 3.8+** 
- **Git** (for version control)
- **NodeMCU Device** (for testing)

### Installation Steps

1. **Clone or Extract Project**
   ```powershell
   cd "C:\Users\pulak\Desktop\V4_Webview_NodeMCU - Main"
   ```

2. **Create Virtual Environment** (Recommended)
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install Dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**
   
   Copy `.env.example` to `.env` if custom environment settings are needed:
   ```powershell
   Copy-Item .env.example .env
   ```

5. **Run Application**
   ```powershell
   python run.py
   ```

---

## Production Build

### Building the Executable

The application uses a **WebView2 Bootstrapper** approach, which:
- Reduces installer size from ~400MB to ~5-10MB
- Downloads WebView2 Runtime automatically if not installed
- Creates a professional, production-ready package

### Build Steps

1. **Install PyInstaller** (if not already installed)
   ```powershell
   pip install pyinstaller
   ```

2. **Clean Up Debug Code** (Optional but recommended)
   ```powershell
   python scripts\clean_js.py
   ```
   This comments out console.log statements in JavaScript files.

3. **Run Build Script**
   ```powershell
   python scripts\build_exe.py
   ```

4. **Build Output**
   - Executable: `dist\MacroPad_Pro\MacroPad Pro.exe`
   - Size: ~5-10 MB (without bundled WebView2)
   - All assets and dependencies included

### Build Configuration Files Created

The build script auto-generates:
- `MacroPad_Pro.spec` - PyInstaller configuration
- `dist/MacroPad_Pro/` - Distribution folder
- `dist/MacroPad_Pro/README.txt` - User instructions

---

## WebView2 Bootstrapper

### How It Works

WebView2 installation is handled automatically by the **Inno Setup Installer** during installation:
- Automatically detects if WebView2 is installed.
- Downloads the official Microsoft WebView2 Evergreen Bootstrapper if needed.
- Installs WebView2 silently before launching the app.

---

## Creating an Installer (Recommended)

For professional deployment, create a proper installer using Inno Setup.

### Inno Setup (Recommended)

1. **Download Inno Setup**
   - Get from: https://jrsoftware.org/isdl.php
   - Install the latest version.

2. **Open the Installer Script**
   - Open `setup.iss` in the Inno Setup Compiler IDE.
   - The script is pre-configured with `SetupIconFile=Icon\Logo.ico` to compile the installer using the custom Logo icon.

3. **Compile Installer**
   - Click "Build" → "Compile" inside Inno Setup.
   - Output: `installer_output\Overcontrol_Setup_v1.0.0.exe`

---

## File Structure

```
V4_Webview_NodeMCU - Main/
├── app/
│   ├── assets/              # HTML, CSS, JS, icons
│   ├── tests/               # Unit tests for services
│   ├── api.py               # Consolidated backend services & API exposure
│   ├── macro_manager.py     # Keyboard/mouse macro execution & recording
│   ├── main.py              # Application entry point & tray manager
│   ├── serial_manager.py    # Serial communication & hardware flashing
│   └── version.py           # App version definitions
│
├── scripts/
│   ├── build_exe.py         # Build automation
│   └── clean_js.py          # JavaScript cleanup
│
├── firmware/                # NodeMCU firmware files
├── profiles.json            # User profiles (generated)
├── config.json              # App configuration
├── run.py                   # Application launcher
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
├── .gitignore               # Git exclusions
└── config.template.json     # Safe config template
```

---

## Configuration

### config.json

Application settings:
- Serial port configuration
- Firmware settings
- Knob behavior
- Auto-switching rules
- GitHub repository links

**Important:** Never commit `config.json` with sensitive data!


---

## Security Best Practices

1. **Never Commit Secrets**
   - Use `.env` for sensitive data
   - `.gitignore` excludes `.env` automatically
   - Use `config.template.json` for examples

3. **Code Signing** (Recommended for distribution)
   - Sign executable with code signing certificate
   - Prevents Windows SmartScreen warnings
   - Builds trust with users

---

## Testing

### Development Testing

```powershell
# Run directly
python run.py



# Clean JavaScript
python scripts\clean_js.py
```

### Production Testing

1. **Build executable**
2. **Test on clean Windows VM** (no Python installed)
3. **Verify WebView2 auto-install**
4. **Test all features**
5. **Check file paths and permissions**

---

## Deployment Checklist

- [ ] Update version numbers (`app/assets/`, `config.json`)
- [ ] Run JavaScript cleanup script
- [ ] Build production executable
- [ ] Test on clean VM
- [ ] Create installer
- [ ] Sign executable (if you have certificate)
- [ ] Test installer on clean VM
- [ ] Create release notes
- [ ] Backup current version
- [ ] Deploy to distribution platform

---

## Troubleshooting

### Build Issues

**"PyInstaller not found"**
```powershell
pip install pyinstaller
```

**"Module not found" errors**
```powershell
pip install -r requirements.txt
```

### Runtime Issues

**"Windows Smart App Control is blocking the app"**
Smart App Control (SAC) often blocks unsigned applications with low reputation. To resolve this:
1. **Unblock files**: Run the unblock script provided:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\unblock_app.ps1
   ```
2. **Rebuild**: Rebuild the application with the new metadata included in the latest version.
3. **Exclusion**: If still blocked, you may need to add the installation folder to the Windows Security exclusions list (Settings > Update & Security > Windows Security > Virus & threat protection > Manage settings > Add or remove exclusions).

**"WebView2 not available"**
- Manual download: https://developer.microsoft.com/microsoft-edge/webview2/
- Run as Administrator

**"Serial port not found"**
- Check NodeMCU connection
- Install USB drivers
- Try different USB port


---

## Size Comparison

| Approach | Installer Size | Notes |
|----------|---------------|-------|
| **Bundled WebView2** | ~400 MB | Large but self-contained |
| **Bootstrapper** (current) | ~5-10 MB | Small, downloads on demand |
| **System WebView2 Only** | ~3-5 MB | Smallest, requires pre-installed WebView2 |

**Recommended:** Bootstrapper approach (current implementation)
- Best balance of size and user experience
- Automatic installation
- Professional deployment

---

## Support & Maintenance

### Updating Dependencies

```powershell
# Update all packages
pip install --upgrade -r requirements.txt

# Freeze current versions
pip freeze > requirements.txt
```

### Updating WebView2

WebView2 Runtime updates automatically via Windows Update.
No action needed from users.

---

## Additional Resources

- **WebView2 Documentation**: https://learn.microsoft.com/en-us/microsoft-edge/webview2/
- **PyInstaller Manual**: https://pyinstaller.org/en/stable/
- **Inno Setup Help**: https://jrsoftware.org/ishelp/

---

## License & Credits

Ensure you include appropriate licenses for:
- Python packages (see `requirements.txt`)
- WebView2 Runtime (Microsoft)
- Font Awesome icons
- Any other third-party components

---

**Version**: 1.0.0  
**Last Updated**: 2025-12-22  
**Build System**: PyInstaller + WebView2 Bootstrapper
