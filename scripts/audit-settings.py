#!/usr/bin/env python3
"""
Settings Audit Script
Scans the codebase to find all settings.* references and compares them
with what's actually declared in app/config.py
"""

import ast
import os
import re
from pathlib import Path
from typing import Set, List, Tuple, Dict

# Root directory of the project
PROJECT_ROOT = Path(__file__).parent.parent


def extract_settings_from_config() -> Set[str]:
    """Extract all declared settings from app/config.py"""
    config_path = PROJECT_ROOT / "app" / "config.py"
    
    with open(config_path, 'r') as f:
        tree = ast.parse(f.read())
    
    declared_settings = set()
    
    # Find the Settings class
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            # Extract all class-level assignments
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    declared_settings.add(item.target.id)
    
    return declared_settings


def find_settings_usage() -> Dict[str, List[Tuple[str, int]]]:
    """Find all settings.* references in the codebase"""
    # Pattern to match settings.SOMETHING
    pattern = re.compile(r'settings\.([A-Z_][A-Z0-9_]*)')
    
    used_settings = {}
    
    # Directories to scan
    scan_dirs = ['app', 'scripts', 'tests']
    
    for dir_name in scan_dirs:
        dir_path = PROJECT_ROOT / dir_name
        if not dir_path.exists():
            continue
            
        for py_file in dir_path.rglob('*.py'):
            # Skip __pycache__ directories
            if '__pycache__' in str(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Find all matches
                for line_num, line in enumerate(content.splitlines(), 1):
                    matches = pattern.findall(line)
                    for match in matches:
                        if match not in used_settings:
                            used_settings[match] = []
                        used_settings[match].append((str(py_file.relative_to(PROJECT_ROOT)), line_num))
                        
            except Exception as e:
                print(f"Error reading {py_file}: {e}")
    
    return used_settings


def analyze_discrepancies(declared: Set[str], used: Dict[str, List[Tuple[str, int]]]) -> Tuple[Set[str], Set[str]]:
    """Compare declared vs used settings"""
    used_names = set(used.keys())
    
    missing_in_config = used_names - declared
    unused_in_code = declared - used_names
    
    return missing_in_config, unused_in_code


def print_report(declared: Set[str], used: Dict[str, List[Tuple[str, int]]],
                 missing: Set[str], unused: Set[str]):
    """Print a detailed report"""
    print("=" * 80)
    print("SETTINGS AUDIT REPORT")
    print("=" * 80)
    print()
    
    # Summary
    print(f"Total declared settings: {len(declared)}")
    print(f"Total used settings: {len(used)}")
    print(f"Missing in config.py: {len(missing)}")
    print(f"Declared but unused: {len(unused)}")
    print()
    
    # Missing settings details
    if missing:
        print("-" * 80)
        print("MISSING SETTINGS (causing AttributeErrors):")
        print("-" * 80)
        for setting in sorted(missing):
            print(f"\n{setting}:")
            for file_path, line_num in used[setting][:5]:  # Show first 5 occurrences
                print(f"  - {file_path}:{line_num}")
            if len(used[setting]) > 5:
                print(f"  ... and {len(used[setting]) - 5} more occurrences")
    
    # Unused settings
    if unused:
        print("\n" + "-" * 80)
        print("UNUSED SETTINGS (declared but not referenced):")
        print("-" * 80)
        for setting in sorted(unused):
            print(f"  - {setting}")
    
    # All used settings
    print("\n" + "-" * 80)
    print("ALL USED SETTINGS:")
    print("-" * 80)
    for setting in sorted(used.keys()):
        status = "❌ MISSING" if setting in missing else "✅"
        print(f"  {status} {setting} ({len(used[setting])} references)")
    
    print("\n" + "=" * 80)


def generate_patch_suggestions(missing: Set[str]) -> Dict[str, str]:
    """Generate suggested defaults for missing settings"""
    suggestions = {}
    
    # Common patterns and their suggested defaults
    patterns = {
        r'.*_API_KEY$': 'Optional[str] = None',
        r'.*_SECRET$': 'Optional[str] = None',
        r'.*_ID$': 'Optional[str] = None',
        r'.*_URL$': 'str = "http://localhost:8000"',
        r'.*_PORT$': 'int = 8000',
        r'.*_TIMEOUT$': 'int = 30',
        r'.*_INTERVAL.*': 'int = 3600',
        r'.*_ENABLED$': 'bool = False',
        r'.*_DEBUG$': 'bool = False',
        r'CLIENT_ID$': 'Optional[str] = None',
        r'TENANT_ID$': 'Optional[str] = None',
        r'CLIENT_SECRET$': 'Optional[str] = None',
    }
    
    for setting in missing:
        # Try to match patterns
        for pattern, default in patterns.items():
            if re.match(pattern, setting):
                suggestions[setting] = f"{setting}: {default}"
                break
        else:
            # Generic default
            suggestions[setting] = f"{setting}: str = ''"
    
    return suggestions


def main():
    """Run the settings audit"""
    print("Scanning codebase for settings usage...")
    
    # Extract declared settings
    declared = extract_settings_from_config()
    
    # Find used settings
    used = find_settings_usage()
    
    # Analyze discrepancies
    missing, unused = analyze_discrepancies(declared, used)
    
    # Print report
    print_report(declared, used, missing, unused)
    
    # Generate patch suggestions
    if missing:
        print("\nSUGGESTED ADDITIONS TO config.py:")
        print("-" * 80)
        suggestions = generate_patch_suggestions(missing)
        for setting, suggestion in sorted(suggestions.items()):
            print(f"    {suggestion}  # TODO: Set appropriate default")
        print()
    
    return {
        'declared': declared,
        'used': used,
        'missing': missing,
        'unused': unused
    }


if __name__ == "__main__":
    main() 