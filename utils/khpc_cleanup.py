"""Utility to clean up temporary files in khpc_tools directory"""
import os
import glob
from pathlib import Path
from utils.helpers import get_bundled_path


def cleanup_khpc_tools():
    """Clean up temporary files from khpc_tools directory"""
    try:
        khpc_tools_dir = get_bundled_path('khpc_tools')
        encoder_dir = Path(khpc_tools_dir) / 'SingleEncoder'
        output_dir = encoder_dir / 'output'
        
        cleanup_count = 0
        
        # Clean up encoder directory temp files (temp_template_*, input_*)
        if encoder_dir.exists():
            temp_patterns = [
                'temp_template_*.scd',
                'input_*.wav'
            ]
            
            for pattern in temp_patterns:
                for file_path in encoder_dir.glob(pattern):
                    try:
                        file_path.unlink()
                        cleanup_count += 1
                        print(f"Cleaned up: {file_path.name}")
                    except Exception as e:
                        print(f"Failed to clean up {file_path.name}: {e}")
        
        # Clean up output directory except test.scd
        # (Note: output directory should only contain generated SCD files)
        if output_dir.exists():
            for file_path in output_dir.iterdir():
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        cleanup_count += 1
                        print(f"Cleaned up: output/{file_path.name}")
                    except Exception as e:
                        print(f"Failed to clean up output/{file_path.name}: {e}")
        
        return cleanup_count
        
    except Exception as e:
        print(f"Error during khpc_tools cleanup: {e}")
        return 0


if __name__ == "__main__":
    cleanup_count = cleanup_khpc_tools()
    print(f"Cleanup complete. Removed {cleanup_count} temporary files.")
