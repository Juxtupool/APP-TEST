# MacroPad Pro

Professional macro pad control software for NodeMCU-based hardware.

## Features

- ✨ **Custom Macros**: Create keyboard shortcuts, launch apps, or run commands
- 🎛️ **Programmable Knob**: Volume control, timeline scrubbing, app switching
- 📋 **Multiple Profiles**: Switch between different macro configurations
- 🔄 **Auto-Switching**: Automatically switch profiles based on active application
- 🌐 **Community Hub**: Download and share macros with the community
- 🔌 **Serial Communication**: Direct control of NodeMCU hardware
- 🎨 **Modern UI**: Dark/Light themes with smooth animations
- 🔧 **Firmware Updates**: Flash new firmware directly from the app

## Quick Start

### Installation

1. Download the latest release
2. Run `MacroPad_Pro_Setup.exe`
3. Launch MacroPad Pro from Start Menu or Desktop
4. Connect your NodeMCU device
5. Start creating macros!

> **Note:** WebView2 Runtime will be installed automatically if not present.

### First Time Setup

1. **Connect Device**: Plug in your NodeMCU via USB
2. **Select Port**: Click the connection toggle in the sidebar
3. **Create Profile**: Add a new profile for your workflow
4. **Assign Macros**: Click keys to assign macros

## System Requirements

- Windows 10/11 (64-bit)
- .NET Framework 4.7.2+
- USB port for NodeMCU
- Internet connection (first run only)

## Configuration

### GitHub Token (Optional)

For community features, create a `.env` file next to the executable:

```
GITHUB_TOKEN=your_github_personal_access_token
```

Get a token from: https://github.com/settings/tokens

### Profiles

Profiles are stored in `profiles.json` and are automatically backed up.

## Development

### Prerequisites

- Python 3.8+
- NodeMCU device (ESP8266)

### Setup

```powershell
# Clone repository
git clone <repository-url>
cd V4_Webview_NodeMCU-Main

# Create virtual environment  
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment
Copy-Item .env.example .env
# Edit .env and add your GITHUB_TOKEN

# Run application
python run.py
```

### Building

```powershell
# Build executable
python scripts\build_exe.py

# Output: dist\MacroPad_Pro\MacroPad Pro.exe
```

See [BUILD_GUIDE.md](BUILD_GUIDE.md) for detailed instructions.

## Project Structure

```
├── app/
│   ├── assets/         # UI files (HTML, CSS, JS)
│   ├── services/       # Backend services
│   ├── utils/          # Utilities & bootstrapper
│   ├── api.py          # Main API
│   └── main.py         # Entry point
├── scripts/            # Build automation
├── firmware/           # NodeMCU firmware
└── requirements.txt    # Dependencies
```

## Technology Stack

**Frontend:**
- HTML5, CSS3, JavaScript
- Font Awesome icons
- Custom animations & transitions

**Backend:**
- Python 3.8+
- PyWebView (Microsoft Edge WebView2)
- PySerial (device communication)
- Pystray (system tray)

**Build:**
- PyInstaller (executable creation)
- WebView2 Bootstrapper (runtime management)

## Security

- ✅ Environment variables for sensitive data
- ✅ No hardcoded credentials in source
- ✅ .gitignore excludes secrets
- ✅ Template configuration files for sharing

Never commit `.env` or `config.json` with real credentials!

## Troubleshooting

### "WebView2 not found"

Install manually: https://developer.microsoft.com/microsoft-edge/webview2/

### "Serial port not detected"

- Check USB connection
- Try different USB port
- Install CH340G drivers (for most NodeMCU boards)

### "GitHub API errors"

- Verify GITHUB_TOKEN in `.env`
- Check token hasn't expired
- Ensure token has `repo` scope

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

See LICENSE file for details.

## Credits

- Font Awesome for icons
- Microsoft for WebView2 Runtime
- Python open-source community

## Support

For issues and feature requests, please use the GitHub Issues page.

---

**Version**: 1.0.0  
**WebView2 Bootstrapper**: Enabled  
**Installer Size**: ~5-10 MB (vs ~400 MB traditional)
