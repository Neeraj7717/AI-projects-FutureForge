#!/usr/bin/env python3
"""
Installation script for AI Mock Interviewer dependencies.
This script helps install all required packages, especially handling pyaudio installation on Windows.
"""

import subprocess
import sys
import os

def install_package(package):
    """Install a package using pip."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}")
        return False

def main():
    print("=" * 60)
    print("🔧 AI Mock Interviewer - Package Installation")
    print("=" * 60)
    
    # List of packages to install
    packages = [
        "google-generativeai",
        "pyttsx3"
    ]
    
    # Special handling for speech recognition packages
    speech_packages = [
        "SpeechRecognition",
        "pyaudio"
    ]
    
    print("\nInstalling core packages...")
    success_count = 0
    
    # Install core packages
    for package in packages:
        if install_package(package):
            success_count += 1
    
    print("\nInstalling speech recognition packages...")
    print("Note: pyaudio might require special handling on Windows.")
    
    # Install speech recognition packages
    for package in speech_packages:
        if package == "pyaudio":
            # Try different methods for pyaudio
            print("Installing pyaudio...")
            
            # Method 1: Try direct installation
            if install_package("pyaudio"):
                success_count += 1
            else:
                # Method 2: Try pipwin on Windows
                try:
                    print("Trying pipwin method for pyaudio...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "pipwin"])
                    subprocess.check_call([sys.executable, "-m", "pipwin", "install", "pyaudio"])
                    print("✅ Successfully installed pyaudio via pipwin")
                    success_count += 1
                except subprocess.CalledProcessError:
                    print("❌ pipwin method failed for pyaudio")
                    print("Please try manual installation:")
                    print("1. Download pyaudio wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio")
                    print("2. Install with: pip install [downloaded_file].whl")
        else:
            if install_package(package):
                success_count += 1
    
    print("\n" + "=" * 60)
    print("INSTALLATION SUMMARY")
    print("=" * 60)
    
    total_packages = len(packages) + len(speech_packages)
    print(f"Successfully installed: {success_count}/{total_packages} packages")
    
    if success_count == total_packages:
        print("\n🎉 All packages installed successfully!")
        print("You can now run: python ai_mock_interviewer.py")
    else:
        print("\n⚠️  Some packages failed to install.")
        print("Please try the following:")
        print("1. Update pip: python -m pip install --upgrade pip")
        print("2. For pyaudio on Windows, download from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio")
        print("3. For other issues, check the error messages above")

if __name__ == "__main__":
    main() 