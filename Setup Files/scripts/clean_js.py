"""
JavaScript Cleanup Script
Removes or replaces console.log statements from production JavaScript files.
"""
import re
from pathlib import Path

def clean_console_logs(file_path, remove=True):
    """
    Clean console.log statements from JavaScript file.
    
    Args:
        file_path: Path to JavaScript file
        remove: If True, remove console.logs. If False, comment them out.
    
    Returns:
        int: Number of console.logs found
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        original_content = content
    
    # Count occurrences
    count = len(re.findall(r'console\.log\s*\(', content))
    
    if count == 0:
        return 0
    
    if remove:
        # Remove console.log statements (handle multi-line)
        # Match console.log(...); including nested parentheses
        content = re.sub(
            r'^\s*console\.log\s*\([^;]*\);\s*$',
            '',
            content,
            flags=re.MULTILINE
        )
        
        # Also handle inline console.logs
        content = re.sub(
            r'console\.log\s*\([^;]*\);\s*',
            '',
            content
        )
    else:
        # Comment out console.log statements
        content = re.sub(
            r'(^\s*)(console\.log\s*\([^;]*\);)',
            r'\1// \2  // [DEBUG - Disabled in production]',
            content,
            flags=re.MULTILINE
        )
    
    # Only write if changes were made
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return count
    
    return 0

def main():
    """Clean console.logs from all JavaScript files."""
    print("="*60)
    print("JavaScript Console.log Cleanup")
    print("="*60)
    print()
    
    js_dir = Path(__file__).parent.parent / 'app' / 'assets' / 'js'
    js_files = list(js_dir.glob('*.js'))
    
    if not js_files:
        print("No JavaScript files found!")
        return
    
    total_removed = 0
    
    for js_file in js_files:
        print(f"Processing: {js_file.name}...")
        count = clean_console_logs(js_file, remove=False)  # Comment out instead of remove
        
        if count > 0:
            print(f"  ✓ Cleaned {count} console.log statement(s)")
            total_removed += count
        else:
            print(f"  - No console.logs found")
    
    print()
    print("="*60)
    print(f"Total console.logs cleaned: {total_removed}")
    print("="*60)
    print("\nNote: Console.logs were commented out, not removed.")
    print("To remove them completely, edit the script.")

if __name__ == "__main__":
    main()
