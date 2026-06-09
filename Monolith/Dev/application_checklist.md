# Application Development & Deployment Checklist

This checklist provides guidelines for setting up, running, checking, and compiling the **Overcontrol / MacroPad Pro** application.

---

## 📋 1. Development & Setup Checklist
Before writing code or running the application, make sure the development environment is correctly prepared.

- [ ] **Install Prerequisites**:
  - Python 3.8+ (64-bit) installed and added to `PATH`.
  - NodeMCU or RP2040 device connected via USB (for hardware testing).
- [ ] **Create Virtual Environment**:
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
- [ ] **Install Dependencies**:
  ```powershell
  pip install -r requirements.txt
  ```
- [ ] **Configure Environment Secrets**:
  - Copy `.env.example` to `.env`.
  - Edit `.env` and configure `GITHUB_TOKEN=your_github_token_here` (needed for community features).
- [ ] **Configure Application Settings**:
  - Verify `config.json` exists in `Monolith/Dev/` (or copy from `config.template.json` if missing).

---

## ⚙️ 2. Verification Checks Checklist
Use these checks to ensure the application has no syntax issues and all files are ready.

- [ ] **Check Dependencies & Syntax**:
  Run the automatic checking script:
  ```powershell
  python scripts/run_checks.py
  ```
- [ ] **Review Results**:
  Ensure the following checks pass:
  - **Python File Syntax Check**: Checks for compilation errors in all Python files.
  - **Dependencies Check**: Verifies all requirements are installed in the active environment.
  - **Configurations Check**: Validates that `.env`, `config.json`, and logo files exist.
  - **JS Assets Cleanliness Check**: Alerts you if there are active `console.log` statements in JS files.
  - **PyInstaller Check**: Confirms if PyInstaller is available for building the executable.

---

## 💻 3. Local Execution & Manual Verification
Verify that the application is running correctly in the local environment.

- [ ] **Launch Application**:
  ```powershell
  python run.py
  ```
- [ ] **Verify WebView2 Startup**:
  - Check if WebView2 bootstrapper starts (it checks for the runtime and downloads if missing).
  - Launch with debug mode if needed:
    ```powershell
    python app/utils/webview2_bootstrapper.py --interactive
    ```
- [ ] **Hardware Communication**:
  - Connect NodeMCU/RP2040 and toggle connection in the sidebar.
  - Ensure the system tray icon updates status (green = connected, gray = disconnected).
- [ ] **Testing Features**:
  - Create and save profiles.
  - Assign macros and verify they trigger key events/commands.
  - Test programmable knob scrolling, volume adjustment, and profile switching.

---

## 🧹 4. Pre-Build Code Optimization
Clean and optimize frontend assets prior to compiler packaging.

- [ ] **Clean Debug Messages**:
  Run the JS cleaner to automatically comment out `console.log` statements in frontend assets:
  ```powershell
  python scripts/clean_js.py
  ```
  *(Note: This keeps code clean for production and minimizes performance overhead. Run `run_checks.py` again to verify JS assets are clean).*

---

## 📦 5. Production Executable Build
Package the application into a standalone Windows directory or executable.

- [ ] **Generate Icon**:
  - Ensure `Icon/Logo.png` is present.
  - Running `scripts/build_exe.py` will generate the multi-resolution `Logo.ico` file automatically.
- [ ] **Build Application**:
  ```powershell
  python scripts/build_exe.py
  ```
  This creates:
  - Spec configuration file: `Overcontrol.spec` or `MacroPad_Pro.spec`.
  - Distribution folder: `dist/Overcontrol/` or `dist/MacroPad_Pro/` containing all runtime files.
  - Dynamic bootstrapper bundle, making the app package only ~5-10MB (without bundling the massive 400MB WebView2 setup).
- [ ] **Local EXE Check**:
  - Launch the generated `.exe` from the `dist/` directory to verify it runs standalone.

---

## 🛠️ 6. Installer Creation
Compile the final installer executable using Inno Setup.

- [ ] **Open Installer Script**:
  - Open `setup.iss` inside the Inno Setup Compiler IDE.
- [ ] **Verify Setup Parameters**:
  - Check application name, version parameters, and target folders.
  - Ensure `SetupIconFile=Icon\Logo.ico` is properly linked.
- [ ] **Compile Installer**:
  - Click **Build** → **Compile** inside Inno Setup.
  - This compiles and builds the installer package inside `installer_output/` (or `installer/output/`).
- [ ] **Clean VM Verification**:
  - Run the setup installer on a clean Windows machine (one without Python or WebView2 pre-installed) to confirm the auto-bootstrapper successfully deploys Edge WebView2 and runs correctly.

---

## 🌐 7. Landing Webpage Deployment
Deploy the companion website using Cloudflare Pages.

- [ ] **Navigate to Webpage folder**:
  ```powershell
  cd Webpage
  ```
- [ ] **Deploy via Wrangler**:
  Deploy static site assets to Cloudflare:
  ```powershell
  npx wrangler pages deploy .
  ```

---

## 🚨 8. Troubleshooting Checklist
If something goes wrong during checks or runtime, follow these troubleshooting guidelines:

- **Missing PyInstaller/Packages**:
  - Active environment is not the virtual environment. Ensure you ran `.\venv\Scripts\Activate.ps1` before installing requirements.
- **Windows Smart App Control (SAC) Blocking**:
  - Windows security might block unsigned binaries. Run the unblock utility script:
    ```powershell
    powershell -ExecutionPolicy Bypass -File scripts\unblock_app.ps1
    ```
- **Serial Port Connection Issues**:
  - Ensure correct USB drivers are installed (like CH340 or CP210x for NodeMCU).
  - Verify that no other serial terminal (like Arduino IDE serial monitor) is holding the port open.
