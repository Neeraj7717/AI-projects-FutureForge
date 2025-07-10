#!/usr/bin/env python3
"""
AI Mock Interviewer - Dynamic Voice-Based Interview System
Uses Gemini API for natural language processing and speech recognition for voice interaction.

Dependencies:
- google-generativeai: For AI-powered question generation and response analysis
- speech_recognition: For voice input capture
- pyttsx3: For text-to-speech output
- pyaudio: For microphone access (required by speech_recognition)

Installation:
pip install google-generativeai speech_recognition pyttsx3 pyaudio

Author: AI Assistant
Version: 1.0
"""

import os
import time
import json
import speech_recognition as sr
import pyttsx3
from typing import List, Dict, Optional
import logging
from config_loader import get_config
from ai_factory import get_ai_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AIMockInterviewer:
    """
    Dynamic AI Mock Interviewer that conducts voice-based interviews using Gemini API.
    Generates context-aware follow-up questions based on user responses.
    """
    
    def __init__(self):
        """Initialize the AI Mock Interviewer with necessary components."""
        # Load configuration
        self.config = get_config()
        
        # Initialize AI provider
        self.ai_provider = get_ai_provider()
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize text-to-speech engine
        self.tts_engine = pyttsx3.init()
        self.setup_tts()
        
        # Interview state
        self.interview_history = []
        self.question_count = 0
        self.interview_duration = self.config.get_interview_duration()
        self.start_time = None
        
        # Conversation context for Gemini
        self.conversation_context = """
        You are a professional, friendly AI interviewer conducting a mock interview. 
        Your role is to:
        1. Ask relevant, follow-up questions based on the candidate's responses
        2. Use natural, conversational language (avoid robotic phrasing)
        3. Include conversational fillers like "That's interesting," "Could you elaborate?"
        4. Maintain a professional yet friendly tone
        5. Generate questions that flow naturally from the conversation
        6. Keep responses concise and engaging
        
        Current interview format: Voice-based interaction with dynamic questioning.
        """
    
    def _initialize_gemini_model(self):
        """Initialize Gemini model with fallback options for different API versions."""
        model_names = [
            'gemini-2.0-flash',
            
            'gemini-1.5-flash'
            
        ]
        
        for model_name in model_names:
            try:
                logger.info(f"Trying to initialize model: {model_name}")
                model = genai.GenerativeModel(model_name)
                # Test the model with a simple query
                response = model.generate_content("Test")
                if response.text:
                    logger.info(f"Successfully initialized model: {model_name}")
                    return model
            except Exception as e:
                logger.warning(f"Failed to initialize {model_name}: {e}")
                continue
        
        # If all models fail, raise an error
        raise Exception("Could not initialize any Gemini model. Please check your API key and internet connection.")
    
    def get_remaining_time(self) -> int:
        """Calculate remaining time in seconds for the interview."""
        if self.start_time is None:
            return self.interview_duration
        elapsed = time.time() - self.start_time
        remaining = self.interview_duration - elapsed
        return max(0, int(remaining))
    
    def format_time(self, seconds: int) -> str:
        """Format seconds into minutes and seconds."""
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    
    def setup_tts(self):
        """Configure text-to-speech settings for natural voice output."""
        try:
            # Get available voices and set a natural-sounding one
            voices = self.tts_engine.getProperty('voices')
            if voices:
                # Prefer a female voice if available (often sounds more natural for interviews)
                for voice in voices:
                    if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                        self.tts_engine.setProperty('voice', voice.id)
                        break
                else:
                    # Fallback to first available voice
                    self.tts_engine.setProperty('voice', voices[0].id)
            
            # Set speech rate and volume from config
            self.tts_engine.setProperty('rate', self.config.get_tts_rate())  # Words per minute
            self.tts_engine.setProperty('volume', self.config.get_tts_volume())  # Volume level (0.0 to 1.0)
            
        except Exception as e:
            logger.warning(f"Could not configure TTS optimally: {e}")
    
    def speak(self, text: str):
        """
        Convert text to speech and play it.
        
        Args:
            text (str): Text to convert to speech
        """
        try:
            logger.info(f"Speaking: {text}")
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            logger.error(f"TTS error: {e}")
            print(f"Interviewer: {text}")  # Fallback to text output
    
    def listen(self) -> Optional[str]:
        """
        Listen for user voice input and convert to text.
        Waits for user to finish speaking with a 5-second pause.
        
        Returns:
            Optional[str]: Transcribed text or None if failed
        """
        try:
            with self.microphone as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                logger.info("Listening for response...")
                
                # Listen for audio input with longer timeout and phrase time limit
                audio = self.recognizer.listen(
                    source, 
                    timeout=self.config.get_speech_timeout(),  # From config
                    phrase_time_limit=self.config.get_phrase_time_limit(),  # From config
                    snowboy_configuration=None  # Disable hotword detection
                )
                
                # Convert speech to text
                text = self.recognizer.recognize_google(audio)
                logger.info(f"Recognized: {text}")
                
                # Wait after user stops speaking to ensure they're done
                wait_time = self.config.get_wait_after_speech()
                logger.info(f"Waiting {wait_time} seconds to ensure you're finished speaking...")
                time.sleep(wait_time)
                
                # Check if user started speaking again during the 5-second wait
                try:
                    # Quick check for additional speech
                    additional_audio = self.recognizer.listen(
                        source, 
                        timeout=2,  # Short timeout for additional speech
                        phrase_time_limit=30
                    )
                    additional_text = self.recognizer.recognize_google(additional_audio)
                    if additional_text:
                        text += " " + additional_text
                        logger.info(f"Additional speech detected: {additional_text}")
                        # Wait another 5 seconds after additional speech
                        logger.info("Waiting another 5 seconds...")
                        time.sleep(5)
                except (sr.WaitTimeoutError, sr.UnknownValueError):
                    # No additional speech detected, continue
                    pass
                
                return text
                
        except sr.WaitTimeoutError:
            logger.warning("No speech detected within timeout")
            return None
        except sr.UnknownValueError:
            logger.warning("Speech was unintelligible")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in speech recognition: {e}")
            return None
    
    def generate_question(self, user_response: str = None) -> str:
        """
        Generate a context-aware interview question using Gemini API.
        
        Args:
            user_response (str): The user's previous response for context
            
        Returns:
            str: Generated interview question
        """
        try:
            if user_response:
                # Generate follow-up question based on user's response
                prompt = f"""
                {self.conversation_context}
                
                Interview History:
                {self.format_interview_history()}
                
                Candidate's last response: "{user_response}"
                
                Generate a natural, follow-up question that:
                1. Builds on what the candidate just said
                2. Shows interest in their response
                3. Uses conversational language
                4. Helps explore their experience or skills further
                5. Maintains professional tone
                
                Return ONLY the question, no additional text.
                """
            else:
                # Generate initial question
                prompt = f"""
                {self.conversation_context}
                
                This is the start of the interview. Generate an engaging opening question that:
                1. Welcomes the candidate warmly
                2. Asks them to tell you about themselves
                3. Uses natural, conversational language
                4. Sets a friendly, professional tone
                
                Return ONLY the question, no additional text.
                """
            
            try:
                question = self.ai_provider(prompt)
                
                if not question:
                    raise Exception("Empty response from API")
                    
            except Exception as api_error:
                logger.error(f"API error in question generation: {api_error}")
                raise api_error
            
            # Clean up the response if needed
            if question.startswith('"') and question.endswith('"'):
                question = question[1:-1]
            
            # Remove any markdown formatting
            question = question.replace('**', '').replace('*', '')
            
            # Ensure it's a proper question
            if not question.endswith('?'):
                question += '?'
            
            return question
            
        except Exception as e:
            logger.error(f"Error generating question: {e}")
            # Fallback questions
            fallback_questions = [
                "Could you tell me a bit about yourself and your background?",
                "What interests you most about this role?",
                "Can you walk me through a challenging project you've worked on?",
                "What are your greatest strengths as a professional?",
                "Where do you see yourself in the next few years?",
                "What motivates you in your work?"
            ]
            return fallback_questions[self.question_count % len(fallback_questions)]
    
    def format_interview_history(self) -> str:
        """Format the interview history for context."""
        if not self.interview_history:
            return "No previous questions asked yet."
        
        history = []
        for i, (question, response) in enumerate(self.interview_history, 1):
            history.append(f"Q{i}: {question}")
            history.append(f"A{i}: {response}")
        
        return "\n".join(history)
    
    def analyze_response(self, response: str) -> Dict:
        """
        Analyze user response for context and sentiment.
        
        Args:
            response (str): User's response
            
        Returns:
            Dict: Analysis results
        """
        try:
            prompt = f"""
            Analyze this interview response and provide insights in JSON format:
            
            Response: "{response}"
            
            Return ONLY a valid JSON object with these exact keys:
            {{
                "key_topics": ["topic1", "topic2"],
                "sentiment": "positive|neutral|negative",
                "follow_up_areas": ["area1", "area2"],
                "response_length": "short|medium|long"
            }}
            
            Do not include any text before or after the JSON.
            """
            
            result = self.ai_provider(prompt)
            
            # Clean the response text
            text = result.strip()
            
            # Try to extract JSON from the response
            try:
                # First, try direct JSON parsing
                analysis = json.loads(text)
            except json.JSONDecodeError:
                # If that fails, try to find JSON within the text
                import re
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    try:
                        analysis = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        raise Exception("Could not parse JSON from response")
                else:
                    raise Exception("No JSON found in response")
            
            # Validate the analysis structure
            required_keys = ["key_topics", "sentiment", "follow_up_areas", "response_length"]
            for key in required_keys:
                if key not in analysis:
                    analysis[key] = "general" if key == "key_topics" else "neutral" if key == "sentiment" else "experience" if key == "follow_up_areas" else "medium"
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing response: {e}")
            # Return a more detailed fallback based on the response content
            response_lower = response.lower()
            
            # Simple keyword-based analysis
            key_topics = []
            if any(word in response_lower for word in ["java", "python", "javascript", "react", "sql"]):
                key_topics.append("programming")
            if any(word in response_lower for word in ["kafka", "microservices", "api", "database"]):
                key_topics.append("architecture")
            if any(word in response_lower for word in ["cloud", "gcp", "aws", "azure"]):
                key_topics.append("cloud")
            if not key_topics:
                key_topics = ["general"]
            
            sentiment = "positive" if any(word in response_lower for word in ["success", "achieved", "solved", "improved"]) else "neutral"
            
            follow_up_areas = ["experience"] if len(response) > 50 else ["background"]
            
            response_length = "long" if len(response) > 200 else "medium" if len(response) > 100 else "short"
            
            return {
                "key_topics": key_topics,
                "sentiment": sentiment,
                "follow_up_areas": follow_up_areas,
                "response_length": response_length
            }
    
    def conduct_interview(self):
        """Main method to conduct the complete interview."""
        try:
            # Set start time
            self.start_time = time.time()
            
            # Welcome message
            duration_minutes = self.interview_duration // 60
            welcome_message = f"Hello! I'm your AI interviewer today. I'm excited to learn more about you and your experience. We'll be having a {duration_minutes}-minute conversation to get to know you better. Let's have a great interview!"
            self.speak(welcome_message)
            print(f"\nInterviewer: {welcome_message}")
            
            # Initial question
            initial_question = self.generate_question()
            self.speak(initial_question)
            print(f"\nInterviewer: {initial_question}")
            
            # Main interview loop - continue until 30 minutes are up
            while self.get_remaining_time() > 0:
                # Listen for response
                user_response = self.listen()
                
                if user_response is None:
                    # Handle speech recognition failure
                    self.speak("I didn't catch that. Could you please repeat your response?")
                    print("\nInterviewer: I didn't catch that. Could you please repeat your response?")
                    continue
                
                print(f"\nYou: {user_response}")
                
                # Store the Q&A pair (store the current question and response)
                current_question = initial_question if self.question_count == 0 else self.interview_history[-1][0]
                self.interview_history.append((current_question, user_response))
                
                # Analyze response for better follow-up
                analysis = self.analyze_response(user_response)
                logger.info(f"Response analysis: {analysis}")
                
                # Increment question count
                self.question_count += 1
                remaining_time = self.get_remaining_time()
                logger.info(f"Question {self.question_count} completed. Remaining time: {self.format_time(remaining_time)}")
                
                # Check if we're running out of time (less than 2 minutes left)
                if remaining_time < 120:
                    logger.info("Less than 2 minutes remaining, preparing to wrap up")
                    break
                
                # Give a 5-minute warning
                if remaining_time < 300 and remaining_time > 240:  # Between 5 and 4 minutes
                    time_warning = f"We have about {self.format_time(remaining_time)} left in our interview. Let's make the most of our remaining time."
                    self.speak(time_warning)
                    print(f"\nInterviewer: {time_warning}")
                
                # Generate follow-up question
                follow_up = self.generate_question(user_response)
                
                # Add conversational elements
                conversational_fillers = [
                    "That's really interesting.",
                    "Thank you for sharing that.",
                    "I appreciate you taking the time to explain that.",
                    "That's a great point.",
                    "I see what you mean."
                ]
                
                import random
                filler = random.choice(conversational_fillers)
                full_response = f"{filler} {follow_up}"
                
                self.speak(full_response)
                print(f"\nInterviewer: {full_response}")
                
                # Small pause for natural flow
                time.sleep(1)
            
            # Calculate total interview time
            total_time = time.time() - self.start_time
            total_minutes = int(total_time // 60)
            total_seconds = int(total_time % 60)
            
            # Closing message
            closing_message = f"Thank you so much for taking the time to speak with me today. We've had a great {total_minutes}-minute conversation, and I've really enjoyed learning more about your background and experience. I appreciate you sharing your insights with me."
            self.speak(closing_message)
            print(f"\nInterviewer: {closing_message}")
            
            # Final thank you
            final_message = f"That concludes our {total_minutes}-minute interview. Best of luck with your application!"
            self.speak(final_message)
            print(f"\nInterviewer: {final_message}")
            
        except KeyboardInterrupt:
            logger.info("Interview interrupted by user")
            self.speak("I understand you need to end the interview early. Thank you for your time.")
            print("\nInterviewer: I understand you need to end the interview early. Thank you for your time.")
        
        except Exception as e:
            logger.error(f"Unexpected error during interview: {e}")
            self.speak("I apologize, but I'm experiencing some technical difficulties. Let's end the interview here. Thank you for your time.")
            print("\nInterviewer: I apologize, but I'm experiencing some technical difficulties. Let's end the interview here. Thank you for your time.")

def main():
    """Main function to run the AI Mock Interviewer."""
    print("=" * 60)
    print("🤖 AI Mock Interviewer - Voice-Based Interview System")
    print("=" * 60)
    
    # Show configuration
    config = get_config()
    config.print_config()
    
    print("\nThis system will conduct a dynamic interview using voice interaction.")
    print("The interview will continue until the time limit is reached.")
    print("Make sure your microphone is working and you're in a quiet environment.")
    print("\nPress Ctrl+C to exit the interview at any time.")
    print("=" * 60)
    
    try:
        # Initialize the interviewer
        interviewer = AIMockInterviewer()
        
        # Start the interview
        input("\nPress Enter to begin the interview...")
        interviewer.conduct_interview()
        
    except Exception as e:
        logger.error(f"Failed to initialize interviewer: {e}")
        print(f"Error: {e}")
        print("Please check your microphone and internet connection.")

if __name__ == "__main__":
    main() 