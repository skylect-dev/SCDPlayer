"""
Test script for KH2 SCD Hook connection.
Run this with KH2FM running to verify we can connect and read the hook addresses.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.kh2_hook import get_hook
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(message)s'
)

def main():
    print("=" * 60)
    print("KH2 SCD Hook Connection Test")
    print("=" * 60)
    print()
    print("Make sure Kingdom Hearts II Final Mix is running...")
    print()
    
    hook = get_hook()
    
    # Attempt connection
    print("Attempting to connect to KH2FM process...")
    if hook.connect():
        print("✓ Connected successfully!")
        print()
        
        # Get current paths
        field_path, battle_path = hook.get_current_paths()
        
        print(f"Process ID: {hook.process_id}")
        print(f"Base Address: 0x{hook.base_address:X}")
        print()
        
        print("Current Hook Values:")
        print("-" * 60)
        print(f"FIELD_PATH:  {field_path or '(empty)'}")
        print(f"BATTLE_PATH: {battle_path or '(empty)'}")
        print("-" * 60)
        print()
        print("✓ Connection test successful!")
        print("  All addresses are readable.")
        print("  The hook mod appears to be loaded correctly.")
        
        hook.disconnect()
        
    else:
        print("✗ Connection failed!")
        print()
        print("Possible causes:")
        print("  - KH2FM is not running")
        print("  - SCDHook mod is not installed/loaded")
        print("  - Running without administrator privileges")
        print("  - Process name mismatch")
        print()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
