"""
Test script for .NET installer functionality
"""
import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from utils.dotnet_installer import DotNetRuntimeChecker, prompt_dotnet_install

def test_dotnet_check():
    """Test .NET detection"""
    print("Testing .NET 5.0 detection...")
    is_available, version = DotNetRuntimeChecker.check_dotnet_installed()
    
    if is_available:
        print(f"✓ .NET {version} detected")
    else:
        print("✗ .NET 5.0 not detected")
    
    return is_available

def test_bundled_installer():
    """Test bundled installer detection"""
    print("\nTesting bundled installer detection...")
    installer = DotNetRuntimeChecker.check_bundled_installer()
    
    if installer:
        print(f"✓ Bundled installer found: {installer}")
    else:
        print("✗ No bundled installer found")
    
    return installer

def test_installer_prompt():
    """Test the installer prompt dialog"""
    print("\nTesting installer prompt...")
    app = QApplication(sys.argv)
    
    # Show the installer prompt
    result = prompt_dotnet_install(None)
    
    print(f"Installer prompt result: {result}")
    return result

if __name__ == '__main__':
    print("=== .NET Installer Test ===\n")
    
    # Test 1: Check if .NET is detected
    dotnet_available = test_dotnet_check()
    
    # Test 2: Check for bundled installer
    bundled_installer = test_bundled_installer()
    
    # Test 3: Show the installer prompt (if .NET not available)
    if not dotnet_available:
        print("\n.NET not found - showing installer prompt...")
        test_installer_prompt()
    else:
        print("\n.NET is installed. To test the installer:")
        print("1. Temporarily rename the .NET 5.0 folder (requires admin):")
        print('   Rename-Item "C:\\Program Files\\dotnet\\shared\\Microsoft.NETCore.App\\5.0.17" "5.0.17.backup"')
        print("2. Run this test script again")
        print("3. Restore the folder after testing:")
        print('   Rename-Item "C:\\Program Files\\dotnet\\shared\\Microsoft.NETCore.App\\5.0.17.backup" "5.0.17"')
        
        # Still show what the prompt would look like
        user_choice = input("\nDo you want to see the installer prompt anyway? (y/n): ")
        if user_choice.lower() == 'y':
            test_installer_prompt()
    
    print("\n=== Test Complete ===")
