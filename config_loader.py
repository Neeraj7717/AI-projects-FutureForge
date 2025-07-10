#!/usr/bin/env python3
"""
Simple Configuration Loader for AI Mock Interviewer
Reads settings from application.properties file
"""

import os
from typing import Dict, Any

class ConfigLoader:
    """Simple configuration loader for application.properties"""
    
    def __init__(self, properties_file: str = "application.properties"):
        self.properties_file = properties_file
        self.config = {}
        self.load_properties()
    
    def load_properties(self):
        """Load properties from file"""
        if not os.path.exists(self.properties_file):
            print(f"Warning: {self.properties_file} not found. Using default values.")
            return
        
        try:
            with open(self.properties_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line.startswith('#') or not line or '=' not in line:
                        continue
                    
                    # Parse key=value
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    self.config[key] = value
                    
        except Exception as e:
            print(f"Error loading {self.properties_file}: {e}")
    
    def get(self, key: str, default: Any = None) -> str:
        """Get a configuration value"""
        return self.config.get(key, default)
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get a configuration value as integer"""
        try:
            return int(self.get(key, default))
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a configuration value as float"""
        try:
            return float(self.get(key, default))
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a configuration value as boolean"""
        value = self.get(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def get_ai_provider(self) -> str:
        """Get the configured AI provider"""
        return self.get('ai.provider', 'openai')
    
    def get_ai_model(self) -> str:
        """Get the configured AI model"""
        return self.get('ai.model', 'gpt-4')
    
    def get_api_key(self, provider: str = None) -> str:
        """Get API key for the specified provider or current provider"""
        if provider is None:
            provider = self.get_ai_provider()
        
        key_map = {
            'openai': 'openai.api.key',
            'gemini': 'gemini.api.key',
            'anthropic': 'anthropic.api.key'
        }
        
        config_key = key_map.get(provider, f'{provider}.api.key')
        return self.get(config_key, '')
    
    def get_interview_duration(self) -> int:
        """Get interview duration in seconds"""
        minutes = self.get_int('interview.duration.minutes', 30)
        return minutes * 60
    
    def get_speech_timeout(self) -> int:
        """Get speech timeout in seconds"""
        return self.get_int('speech.timeout.seconds', 15)
    
    def get_phrase_time_limit(self) -> int:
        """Get phrase time limit in seconds"""
        return self.get_int('speech.phrase.time.limit.seconds', 60)
    
    def get_wait_after_speech(self) -> int:
        """Get wait time after speech in seconds"""
        return self.get_int('speech.wait.after.seconds', 3)
    
    def get_tts_rate(self) -> int:
        """Get TTS speech rate"""
        return self.get_int('tts.rate', 180)
    
    def get_tts_volume(self) -> float:
        """Get TTS volume"""
        return self.get_float('tts.volume', 0.9)
    
    def print_config(self):
        """Print current configuration"""
        print("Current Configuration:")
        print("=" * 40)
        print(f"AI Provider: {self.get_ai_provider()}")
        print(f"AI Model: {self.get_ai_model()}")
        print(f"API Key Configured: {'Yes' if self.get_api_key() else 'No'}")
        print(f"Interview Duration: {self.get_interview_duration() // 60} minutes")
        print(f"Speech Timeout: {self.get_speech_timeout()} seconds")
        print(f"Phrase Time Limit: {self.get_phrase_time_limit()} seconds")
        print(f"Wait After Speech: {self.get_wait_after_speech()} seconds")

# Global configuration instance
config = ConfigLoader()

def get_config() -> ConfigLoader:
    """Get the global configuration instance"""
    return config

if __name__ == "__main__":
    # Print current configuration
    config.print_config()
    
    print("\nTo change settings, edit application.properties file:")
    print("- Change ai.provider to switch between openai, gemini, anthropic")
    print("- Change ai.model to use different models")
    print("- Update API keys in the respective .api.key properties") 