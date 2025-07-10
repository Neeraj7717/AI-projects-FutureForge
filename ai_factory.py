#!/usr/bin/env python3
"""
Simple AI Factory for AI Mock Interviewer
Creates AI providers based on application.properties configuration
"""

import logging
from config_loader import get_config

logger = logging.getLogger(__name__)

class AIFactory:
    """Simple factory for creating AI providers"""
    
    @staticmethod
    def create_ai_provider():
        """Create AI provider based on configuration"""
        config = get_config()
        provider = config.get_ai_provider()
        model = config.get_ai_model()
        api_key = config.get_api_key()
        
        logger.info(f"Creating AI provider: {provider} with model: {model}")
        
        if provider == "openai":
            return AIFactory._create_openai_provider(api_key, model)
        elif provider == "gemini":
            return AIFactory._create_gemini_provider(api_key, model)
        elif provider == "anthropic":
            return AIFactory._create_anthropic_provider(api_key, model)
        else:
            raise ValueError(f"Unknown AI provider: {provider}")
    
    @staticmethod
    def _create_openai_provider(api_key: str, model: str):
        """Create OpenAI provider"""
        try:
            import openai
            openai.api_key = api_key
            
            def generate_response(prompt: str) -> str:
                try:
                    response = openai.ChatCompletion.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "You are a professional, friendly AI interviewer conducting a mock interview. Use natural, conversational language and generate relevant follow-up questions based on the candidate's responses."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=500,
                        temperature=0.7
                    )
                    return response.choices[0].message.content.strip()
                except Exception as e:
                    logger.error(f"OpenAI API error: {e}")
                    raise
            
            return generate_response
            
        except ImportError:
            raise ImportError("OpenAI library not installed. Run: pip install openai")
    
    @staticmethod
    def _create_gemini_provider(api_key: str, model: str):
        """Create Gemini provider"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            ai_model = genai.GenerativeModel(model)
            
            def generate_response(prompt: str) -> str:
                try:
                    response = ai_model.generate_content(prompt)
                    return response.text.strip()
                except Exception as e:
                    logger.error(f"Gemini API error: {e}")
                    raise
            
            return generate_response
            
        except ImportError:
            raise ImportError("Google Generative AI library not installed. Run: pip install google-generativeai")
    
    @staticmethod
    def _create_anthropic_provider(api_key: str, model: str):
        """Create Anthropic provider"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            
            def generate_response(prompt: str) -> str:
                try:
                    response = client.messages.create(
                        model=model,
                        max_tokens=500,
                        messages=[
                            {"role": "user", "content": prompt}
                        ]
                    )
                    return response.content[0].text.strip()
                except Exception as e:
                    logger.error(f"Anthropic API error: {e}")
                    raise
            
            return generate_response
            
        except ImportError:
            raise ImportError("Anthropic library not installed. Run: pip install anthropic")

def get_ai_provider():
    """Get AI provider function"""
    return AIFactory.create_ai_provider()

def test_ai_provider():
    """Test the current AI provider"""
    try:
        provider = get_ai_provider()
        response = provider("Test connection")
        if response:
            print("✅ AI provider is working")
            return True
        else:
            print("❌ AI provider returned empty response")
            return False
    except Exception as e:
        print(f"❌ AI provider test failed: {e}")
        return False

if __name__ == "__main__":
    # Test the AI provider
    print("Testing AI Provider...")
    test_ai_provider() 