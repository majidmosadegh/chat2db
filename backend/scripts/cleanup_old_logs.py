"""
Cleanup Old Loguru Logs Script
Finds and removes old loguru log files from default Windows locations (like C: drive)
"""

import os
import shutil
from pathlib import Path
from loguru import logger


def find_loguru_log_directories():
    """Find all possible loguru log directories on Windows"""
    possible_locations = []
    
    # Get user's AppData Local directory (most common location)
    appdata_local = os.environ.get('LOCALAPPDATA', '')
    if appdata_local:
        loguru_appdata = Path(appdata_local) / "Loguru"
        if loguru_appdata.exists():
            possible_locations.append(loguru_appdata)
    
    # Get Temp directory
    temp_dir = os.environ.get('TEMP', '')
    if temp_dir:
        loguru_temp = Path(temp_dir) / "Loguru"
        if loguru_temp.exists():
            possible_locations.append(loguru_temp)
    
    # Get user's home directory
    user_home = Path.home()
    loguru_home = user_home / "AppData" / "Local" / "Loguru"
    if loguru_home.exists():
        possible_locations.append(loguru_home)
    
    # Check C:\Users\<username>\AppData\Local\Loguru
    if user_home:
        c_users_loguru = user_home / "AppData" / "Local" / "Loguru"
        if c_users_loguru.exists() and c_users_loguru not in possible_locations:
            possible_locations.append(c_users_loguru)
    
    # Also check common Windows log locations
    windows_log_locations = [
        Path("C:/Loguru"),
        Path("C:/Windows/Loguru"),
        Path("C:/ProgramData/Loguru"),
    ]
    
    for loc in windows_log_locations:
        if loc.exists():
            possible_locations.append(loc)
    
    return possible_locations


def cleanup_loguru_logs(dry_run=False):
    """
    Find and cleanup old loguru log files
    
    Args:
        dry_run: If True, only print what would be deleted without actually deleting
    """
    print("=" * 80)
    print("Loguru Log Cleanup Script")
    print("=" * 80)
    print()
    
    log_dirs = find_loguru_log_directories()
    
    if not log_dirs:
        print("✅ No old loguru log directories found in default Windows locations.")
        print("   All logs should now be in: backend/logs/")
        return
    
    total_size = 0
    total_files = 0
    
    for log_dir in log_dirs:
        print(f"\n📁 Found log directory: {log_dir}")
        
        if not log_dir.exists():
            print(f"   ⚠️  Directory doesn't exist, skipping...")
            continue
        
        # Count files and size for this directory
        files_in_dir = []
        dir_size = 0
        for root, dirs, files in os.walk(log_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.is_file():
                    try:
                        file_size = file_path.stat().st_size
                        files_in_dir.append(file_path)
                        dir_size += file_size
                        total_files += 1
                        total_size += file_size
                    except Exception as e:
                        print(f"   ⚠️  Could not read {file_path}: {e}")
        
        if not files_in_dir:
            print(f"   ℹ️  Directory is empty")
            continue
        
        print(f"   📊 Found {len(files_in_dir)} file(s)")
        
        # Show size for this directory
        dir_size_mb = dir_size / (1024 * 1024)
        print(f"   💾 Directory size: {dir_size_mb:.2f} MB")
        
        if dry_run:
            print(f"   🔍 DRY RUN: Would delete:")
            for file_path in files_in_dir[:10]:  # Show first 10
                print(f"      - {file_path}")
            if len(files_in_dir) > 10:
                print(f"      ... and {len(files_in_dir) - 10} more files")
        else:
            print(f"   🗑️  Deleting files...")
            deleted_count = 0
            for file_path in files_in_dir:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"      ⚠️  Failed to delete {file_path}: {e}")
            
            print(f"   ✅ Deleted {deleted_count}/{len(files_in_dir)} files")
            
            # Try to remove directory if empty
            try:
                if not any(log_dir.iterdir()):
                    log_dir.rmdir()
                    print(f"   ✅ Removed empty directory")
            except Exception as e:
                print(f"   ⚠️  Could not remove directory: {e}")
    
    if log_dirs:
        print("\n" + "=" * 80)
        if dry_run:
            total_mb = total_size / (1024 * 1024)
            print(f"DRY RUN SUMMARY: Would delete {total_files} file(s) ({total_mb:.2f} MB)")
            print("\n⚠️  This was a dry run. To actually delete files, run:")
            print("   python backend/scripts/cleanup_old_logs.py --delete")
        else:
            total_mb = total_size / (1024 * 1024)
            print(f"✅ CLEANUP COMPLETE: Deleted {total_files} file(s) ({total_mb:.2f} MB)")
            print("\n✅ Old logs have been removed. New logs will be saved to: backend/logs/")
        print("=" * 80)


if __name__ == "__main__":
    import sys
    
    # Check if --delete flag is provided
    dry_run = "--delete" not in sys.argv
    
    if dry_run:
        print("⚠️  DRY RUN MODE - No files will be deleted")
        print("   Add --delete flag to actually delete files\n")
    else:
        response = input("⚠️  Are you sure you want to delete old loguru log files? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Cancelled.")
            sys.exit(0)
    
    cleanup_loguru_logs(dry_run=dry_run)

