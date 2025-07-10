#!/usr/bin/env python3
"""
Test script to verify AI Mock Interviewer setup.
Run this before using the main application to ensure everything is working.
"""

import sys
import os

def test_imports():
    """Test if all required modules can be imported."""
    print("Testing imports...")
    
    try:
        import google.generativeai as genai
        print("✅ google-generativeai imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import google-generativeai: {e}")
        return False
    
    try:
        import speech_recognition as sr
        print("✅ speech_recognition imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import speech_recognition: {e}")
        return False
    
    try:
        import pyttsx3
        print("✅ pyttsx3 imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import pyttsx3: {e}")
        return False
    
    try:
        import pyaudio
        print("✅ pyaudio imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import pyaudio: {e}")
        return False
    
    return True

def test_microphone():
    """Test if microphone is accessible."""
    print("\nTesting microphone access...")
    
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()
        
        with microphone as source:
            print("✅ Microphone detected and accessible")
            return True
    except Exception as e:
        print(f"❌ Microphone test failed: {e}")
        return False

def test_tts():
    """Test text-to-speech functionality."""
    print("\nTesting text-to-speech...")
    
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        print(f"✅ TTS initialized successfully. Found {len(voices)} voice(s)")
        return True
    except Exception as e:
        print(f"❌ TTS test failed: {e}")
        return False

def test_gemini_api():
    """Test Gemini API connection."""
    print("\nTesting Gemini API connection...")
    
    try:
        import google.generativeai as genai
        
        # Use the same API key as the main application
        api_key = os.getenv('GEMINI_API_KEY', 'AIzaSyCllftuYclAv1coi8RqrUJYoIzyTGd34FE')
        genai.configure(api_key=api_key)
        
        # Try different model names that are available
        model_names = [
            'gemini-2.0-flash',
            'gemini-1.5-pro',
            'gemini-1.0-pro', 
            'gemini-pro',
            'gemini-1.5-flash',
            'gemini-1.0-pro-001'
        ]
        
        model = None
        for model_name in model_names:
            try:
                print(f"  Trying model: {model_name}")
                model = genai.GenerativeModel(model_name)
                # Test the model
                response = model.generate_content("Hello, this is a test.")
                if response.text:
                    print(f"  ✅ Successfully connected using {model_name}")
                    break
            except Exception as e:
                print(f"  ❌ Failed with {model_name}: {e}")
                continue
        
        if model and response.text:
            print("✅ Gemini API connection successful")
            return True
        else:
            print("❌ Could not connect to any Gemini model")
            return False
            
    except Exception as e:
        print(f"❌ Gemini API test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("AI Mock Interviewer - Setup Test")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("Microphone Test", test_microphone),
        ("TTS Test", test_tts),
        ("Gemini API Test", test_gemini_api)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)} tests")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Your system is ready for the AI Mock Interviewer.")
        print("Run 'python ai_mock_interviewer.py' to start your interview.")
    else:
        print("\n⚠️  Some tests failed. Please check the issues above before running the main application.")
        print("\nCommon solutions:")
        print("1. Install missing dependencies: pip install -r requirements.txt")
        print("2. For pyaudio issues on Windows: pip install pipwin && pipwin install pyaudio")
        print("3. Check microphone permissions and settings")
        print("4. Verify internet connection for API tests")

if __name__ == "__main__":
    main() 