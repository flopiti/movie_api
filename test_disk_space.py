#!/usr/bin/env python3
import os

def test_disk_space(path):
    """Test disk space calculation for a specific path."""
    try:
        if not os.path.exists(path):
            print(f"Path {path} does not exist")
            return
        
        # Test os.statvfs
        stat = os.statvfs(path)
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = total - free
        
        # Convert to GB
        total_gb = total / (1024**3)
        used_gb = used / (1024**3)
        free_gb = free / (1024**3)
        usage_percentage = (used / total) * 100 if total > 0 else 0
        
        print(f"Path: {path}")
        print(f"Total: {total_gb:.2f} GB")
        print(f"Used: {used_gb:.2f} GB")
        print(f"Free: {free_gb:.2f} GB")
        print(f"Usage: {usage_percentage:.1f}%")
        
        # Also test shutil for comparison
        import shutil
        total_shutil, used_shutil, free_shutil = shutil.disk_usage(path)
        print(f"\nShutil comparison:")
        print(f"Total: {total_shutil / (1024**3):.2f} GB")
        print(f"Used: {used_shutil / (1024**3):.2f} GB")
        print(f"Free: {free_shutil / (1024**3):.2f} GB")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_disk_space("/mnt/external")
