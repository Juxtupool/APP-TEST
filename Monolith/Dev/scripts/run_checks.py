#!/usr/bin/env python
"""
Overcontrol Automatic Verification Checks Script.
Validates dependencies, Python syntax, configuration files, frontend assets,
and packaging environment status.
"""

import os
import sys
import re
import py_compile
import importlib.util
from pathlib import Path

# Paths Setup
SCRIPT_DIR = Path(__file__).parent
DEV_DIR = SCRIPT_DIR.parent
APP_DIR = DEV_DIR / "app"
REQUIREMENTS_PATH = DEV_DIR / "requirements.txt"

def print_section(title):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def check_python_syntax():
    print("\n[+] Checking Python File Syntax...")
    errors = 0
    py_files = list(APP_DIR.glob("**/*.py")) + list(DEV_DIR.glob("*.py"))
    
    for py_file in py_files:
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as e:
            print(f"  [FAIL] Syntax error in {py_file.relative_to(DEV_DIR)}:")
            print(f"    {e.msg}")
            errors += 1
            
    if errors == 0:
        print("  [PASS] All Python files compile successfully.")
        return True
    else:
        print(f"  [FAIL] Found {errors} syntax error(s).")
        return False

def check_dependencies():
    print("\n[+] Checking Dependencies...")
    if not REQUIREMENTS_PATH.exists():
        print("  [FAIL] requirements.txt not found!")
        return False
        
    errors = 0
    with open(REQUIREMENTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Simple parsing of package names (e.g. pywebview>=4.0.0 or pywin32>=305; sys_platform == 'win32')
            pkg_spec = line.split(";")[0].strip()
            pkg_name = re.split(r"[<>=~]", pkg_spec)[0].strip()
            
            # Special import name mappings
            import_name = pkg_name
            mapping = {
                "pywebview": "webview",
                "Pillow": "PIL",
                "pywin32": "win32gui",
                "pynput": "pynput",
                "pystray": "pystray",
                "pyserial": "serial",
            }
            if pkg_name in mapping:
                import_name = mapping[pkg_name]
                
            try:
                # Attempt importing package
                spec = importlib.util.find_spec(import_name)
                if spec is None:
                    # Fallback for win32 modules which may not have normal specs
                    __import__(import_name)
                print(f"  [OK] {pkg_name} is installed (module: {import_name})")
            except Exception:
                print(f"  [FAIL] Missing package: {pkg_name} (failed to import {import_name})")
                errors += 1
                
    if errors == 0:
        print("  [PASS] All requirements are satisfied.")
        return True
    else:
        print(f"  [FAIL] Missing {errors} dependency/dependencies. Run 'pip install -r requirements.txt'")
        return False

def check_configurations():
    print("\n[+] Checking Configurations & Assets...")
    passed = True
    
    # Check .env
    env_path = DEV_DIR / ".env"
    env_example_path = DEV_DIR / ".env.example"
    if not env_path.exists():
        print("  [WARN] .env file is missing.")
        if env_example_path.exists():
            print("    Please copy .env.example to .env and configure GITHUB_TOKEN.")
        passed = False
    else:
        print("  [OK] .env file exists.")
        
    # Check config.json
    config_path = DEV_DIR / "config.json"
    config_template = DEV_DIR / "config.template.json"
    if not config_path.exists():
        print("  [WARN] config.json is missing.")
        if config_template.exists():
            print("    Please copy config.template.json to config.json.")
        passed = False
    else:
        print("  [OK] config.json exists.")
        
    # Check Logo png
    logo_path = DEV_DIR / "Icon" / "Logo.png"
    if not logo_path.exists():
        print("  [WARN] Icon/Logo.png is missing. Required for build_exe.py.")
        passed = False
    else:
        print("  [OK] Icon/Logo.png is present.")
        
    return passed

def check_js_cleanliness():
    print("\n[+] Checking JS Assets Cleanliness...")
    js_dir = APP_DIR / "assets" / "js"
    if not js_dir.exists():
        print("  [OK] No JS directory found (Assets bundled inside binary or custom path).")
        return True
        
    js_files = list(js_dir.glob("**/*.js"))
    active_logs = 0
    
    for js_file in js_files:
        try:
            with open(js_file, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Exclude commented-out console.logs
            # Matches console.log not preceded by // or /*
            matches = re.findall(r"(?<!//)(?<!/\*)\bconsole\.log\s*\(", content)
            if matches:
                # Ensure it's not a block comment block
                # Simple check: filter lines
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    clean_line = line.strip()
                    if clean_line.startswith("//") or clean_line.startswith("*"):
                        continue
                    if "console.log" in line:
                        print(f"  [WARN] Active console.log in {js_file.relative_to(DEV_DIR)} at line {i+1}")
                        active_logs += len(re.findall(r"\bconsole\.log\s*\(", line))
        except Exception as e:
            print(f"  [ERROR] Failed to read {js_file.name}: {e}")
            
    if active_logs == 0:
        print("  [PASS] JS assets are clean (no active console.log statements found).")
        return True
    else:
        print(f"  [WARN] Found {active_logs} active console.log statement(s).")
        print("    Run 'python scripts/clean_js.py' to clean before release.")
        return True  # Warnings do not fail validation but alert developer

def check_pyinstaller():
    print("\n[+] Checking PyInstaller Availability...")
    spec = importlib.util.find_spec("PyInstaller")
    if spec is not None:
        print("  [OK] PyInstaller is available for packaging executable.")
        return True
    else:
        print("  [WARN] PyInstaller is not installed. Will not be able to build executable.")
        return False

def main():
    print_section("Overcontrol Verification Suite")
    
    syntax_ok = check_python_syntax()
    deps_ok = check_dependencies()
    configs_ok = check_configurations()
    js_ok = check_js_cleanliness()
    pyinstaller_ok = check_pyinstaller()
    
    print_section("Summary of Verification Checks")
    print(f"  Python Syntax Check:     {'PASS' if syntax_ok else 'FAIL'}")
    print(f"  Dependencies Check:      {'PASS' if deps_ok else 'FAIL'}")
    print(f"  Configurations Check:    {'PASS' if configs_ok else 'WARN/FAIL'}")
    print(f"  JS Assets Check:         {'PASS' if js_ok else 'WARN'}")
    print(f"  PyInstaller Check:       {'PASS' if pyinstaller_ok else 'WARN'}")
    print("=" * 60)
    
    if not (syntax_ok and deps_ok):
        print("\n[!] Errors found! Fix compilation errors and install dependencies.")
        sys.exit(1)
    else:
        print("\n[OK] Basic checks passed successfully.")
        sys.exit(0)

if __name__ == "__main__":
    main()
