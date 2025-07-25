#!/usr/bin/env python3
"""
Test script to verify the auto-updater ZIP extraction fix.
This simulates the nested folder structure issue and tests the fix.
"""

import os
import tempfile
import zipfile
import shutil
import subprocess
import sys
from pathlib import Path

def create_test_zip_nested():
    """Create a test ZIP with nested SCDPlayer folder structure (like GitHub Actions creates)"""
    temp_dir = tempfile.mkdtemp(prefix="scd_test_")
    
    # Create the nested structure: SCDPlayer/files...
    nested_dir = os.path.join(temp_dir, "SCDPlayer")
    os.makedirs(nested_dir)
    
    # Create some test files
    test_files = {
        "SCDPlayer.exe": "fake executable content",
        "README.md": "# SCDPlayer Test\nThis is a test file",
        "_internal/test.dll": "fake dll content",
        "_internal/data/config.json": '{"test": true}'
    }
    
    for file_path, content in test_files.items():
        full_path = os.path.join(nested_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
    
    # Create ZIP file
    zip_path = os.path.join(temp_dir, "SCDPlayer-Windows.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(nested_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Add to ZIP with relative path from temp_dir
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)
    
    return zip_path, temp_dir

def test_batch_extraction():
    """Test the batch script extraction logic"""
    print("=== Testing Auto-Updater ZIP Extraction Fix ===\n")
    
    # Create test ZIP with nested structure
    print("1. Creating test ZIP with nested SCDPlayer folder...")
    zip_path, temp_dir = create_test_zip_nested()
    print(f"   Created: {zip_path}")
    
    # Create a fake "current directory" to extract to
    current_dir = os.path.join(temp_dir, "current_install")
    os.makedirs(current_dir)
    
    # Create some existing files to verify they get overwritten
    with open(os.path.join(current_dir, "SCDPlayer.exe"), 'w') as f:
        f.write("old version content")
    with open(os.path.join(current_dir, "README.md"), 'w') as f:
        f.write("old readme")
    
    print("2. Testing batch script extraction logic...")
    
    # Create the batch script with our fix
    script_content = f'''@echo off
echo Testing SCDPlayer updater extraction...

REM Create temp directory for extraction
set TEMP_DIR=%TEMP%\\scd_update_extract_test
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

REM Extract to temp directory first
echo Extracting update archive...
powershell -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '%TEMP_DIR%' -Force"
if errorlevel 1 (
    echo ERROR: Failed to extract update archive
    exit /b 1
)

REM Check if extraction created a nested SCDPlayer folder
if exist "%TEMP_DIR%\\SCDPlayer" (
    echo Found nested folder structure, copying contents...
    REM Copy from nested folder to current directory, overwriting existing files
    xcopy /s /e /y /h /r "%TEMP_DIR%\\SCDPlayer\\*" "{current_dir}\\"
    if errorlevel 1 (
        echo ERROR: Failed to copy files from nested structure
        exit /b 1
    )
) else (
    echo Found direct structure, copying contents...
    REM Copy directly from temp to current directory, overwriting existing files
    xcopy /s /e /y /h /r "%TEMP_DIR%\\*" "{current_dir}\\"
    if errorlevel 1 (
        echo ERROR: Failed to copy files from direct structure
        exit /b 1
    )
)

echo Extraction test completed successfully!

REM Clean up temp directory
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
'''
    
    script_path = os.path.join(temp_dir, 'test_extraction.bat')
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Run the batch script
    print("3. Running extraction test...")
    try:
        result = subprocess.run([script_path], capture_output=True, text=True, timeout=30)
        print(f"   Exit code: {result.returncode}")
        print(f"   Output: {result.stdout}")
        if result.stderr:
            print(f"   Errors: {result.stderr}")
        
        if result.returncode != 0:
            print("❌ Batch script extraction FAILED!")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Batch script timed out!")
        return False
    except Exception as e:
        print(f"❌ Error running batch script: {e}")
        return False
    
    # Verify files were extracted correctly
    print("4. Verifying extraction results...")
    
    expected_files = [
        "SCDPlayer.exe",
        "README.md",
        "_internal/test.dll",
        "_internal/data/config.json"
    ]
    
    all_good = True
    for file_path in expected_files:
        full_path = os.path.join(current_dir, file_path)
        if os.path.exists(full_path):
            print(f"   ✅ Found: {file_path}")
            # Check content to ensure it's the new version
            with open(full_path, 'r') as f:
                content = f.read()
                if file_path == "SCDPlayer.exe" and "fake executable content" in content:
                    print(f"      ✅ Content updated correctly")
                elif file_path == "README.md" and "This is a test file" in content:
                    print(f"      ✅ Content updated correctly")
        else:
            print(f"   ❌ Missing: {file_path}")
            all_good = False
    
    # Check that no nested SCDPlayer folder was created
    nested_path = os.path.join(current_dir, "SCDPlayer")
    if os.path.exists(nested_path):
        print(f"   ❌ Found unwanted nested folder: {nested_path}")
        all_good = False
    else:
        print(f"   ✅ No nested SCDPlayer folder created")
    
    # Cleanup
    shutil.rmtree(temp_dir)
    
    if all_good:
        print("\n🎉 Auto-updater fix test PASSED! The extraction logic works correctly.")
        return True
    else:
        print("\n❌ Auto-updater fix test FAILED! Issues found with extraction logic.")
        return False

def test_direct_zip_structure():
    """Test with direct ZIP structure (no nested folder) for edge case"""
    print("\n=== Testing Direct ZIP Structure (Edge Case) ===\n")
    
    temp_dir = tempfile.mkdtemp(prefix="scd_test_direct_")
    
    # Create files directly in temp directory (no nested SCDPlayer folder)
    test_files = {
        "SCDPlayer.exe": "direct fake executable content",
        "README.md": "# Direct SCDPlayer Test\nThis is a direct test file",
    }
    
    for file_path, content in test_files.items():
        full_path = os.path.join(temp_dir, file_path)
        with open(full_path, 'w') as f:
            f.write(content)
    
    # Create ZIP file with direct structure
    zip_path = os.path.join(temp_dir, "SCDPlayer-Direct.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path, content in test_files.items():
            zipf.writestr(file_path, content)
    
    # Create extraction target
    current_dir = os.path.join(temp_dir, "current_direct")
    os.makedirs(current_dir)
    
    # Test extraction
    script_content = f'''@echo off
echo Testing direct structure extraction...

set TEMP_DIR=%TEMP%\\scd_update_extract_direct
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

powershell -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '%TEMP_DIR%' -Force"

if exist "%TEMP_DIR%\\SCDPlayer" (
    echo Found nested folder structure, copying contents...
    xcopy /s /e /y /h /r "%TEMP_DIR%\\SCDPlayer\\*" "{current_dir}\\"
) else (
    echo Found direct structure, copying contents...
    xcopy /s /e /y /h /r "%TEMP_DIR%\\*" "{current_dir}\\"
)

if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
echo Direct extraction test completed!
'''
    
    script_path = os.path.join(temp_dir, 'test_direct.bat')
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    try:
        result = subprocess.run([script_path], capture_output=True, text=True, timeout=15)
        print(f"Direct test output: {result.stdout}")
        
        # Verify files
        success = True
        for file_path in test_files.keys():
            full_path = os.path.join(current_dir, file_path)
            if os.path.exists(full_path):
                print(f"   ✅ Direct extraction found: {file_path}")
            else:
                print(f"   ❌ Direct extraction missing: {file_path}")
                success = False
        
        shutil.rmtree(temp_dir)
        return success
        
    except Exception as e:
        print(f"❌ Direct extraction test failed: {e}")
        shutil.rmtree(temp_dir)
        return False

if __name__ == "__main__":
    print("SCDPlayer Auto-Updater Fix Test")
    print("=" * 50)
    
    # Test nested structure (main case)
    nested_success = test_batch_extraction()
    
    # Test direct structure (edge case)  
    direct_success = test_direct_zip_structure()
    
    print("\n" + "=" * 50)
    if nested_success and direct_success:
        print("🎉 ALL TESTS PASSED! The auto-updater fix is working correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. The auto-updater fix needs more work.")
        sys.exit(1)
