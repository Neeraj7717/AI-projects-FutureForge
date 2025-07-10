#!/usr/bin/env python3
"""
AI Mock Interviewer - Web Application
Provides a web UI for the voice-based AI interview system
"""

import os
import time
import json
import threading
import logging
import webbrowser
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import speech_recognition as sr
import pyttsx3
from config_loader import get_config
from ai_factory import get_ai_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ai-interviewer-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global interview state
interview_state = {
    'is_active': False,
    'current_question': '',
    'interview_history': [],
    'question_count': 0,
    'start_time': None,
    'is_listening': False,
    'auto_mode': True
}

class WebInterviewer:
    """Web-based AI Mock Interviewer"""
    
    def __init__(self):
        self.config = get_config()
        self.ai_provider = get_ai_provider()
        
        # Conversation context
        self.conversation_context = """
        You are a professional, friendly AI interviewer conducting a mock interview. 
        Your role is to:
        1. Ask relevant, follow-up questions based on the candidate's responses
        2. Use natural, conversational language (avoid robotic phrasing)
        3. Include conversational fillers like "That's interesting," "Could you elaborate?"
        4. Maintain a professional yet friendly tone
        5. Generate questions that flow naturally from the conversation
        6. Keep responses concise and engaging
        
        Current interview format: Web-based interaction with dynamic questioning.
        """
    
    def create_tts_engine(self):
        """Create a new TTS engine instance"""
        try:
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            if voices:
                for voice in voices:
                    if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        break
                else:
                    engine.setProperty('voice', voices[0].id)
            
            engine.setProperty('rate', self.config.get_tts_rate())
            engine.setProperty('volume', self.config.get_tts_volume())
            return engine
            
        except Exception as e:
            logger.warning(f"Could not configure TTS optimally: {e}")
            return None
    
    def speak(self, text: str):
        """Convert text to speech using a fresh TTS engine"""
        try:
            logger.info(f"Speaking: {text}")
            engine = self.create_tts_engine()
            if engine:
                engine.say(text)
                engine.runAndWait()
                engine.stop()
        except Exception as e:
            logger.error(f"TTS error: {e}")
    
    def listen(self) -> str:
        """Listen for user voice input and convert to text"""
        try:
            # Create fresh recognizer and microphone instances
            recognizer = sr.Recognizer()
            microphone = sr.Microphone()
            
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                logger.info("Listening for response...")
                
                audio = recognizer.listen(
                    source, 
                    timeout=self.config.get_speech_timeout(),
                    phrase_time_limit=self.config.get_phrase_time_limit()
                )
                
                text = recognizer.recognize_google(audio)
                logger.info(f"Recognized: {text}")
                
                # Wait after user stops speaking
                wait_time = self.config.get_wait_after_speech()
                logger.info(f"Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                
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
        """Generate a context-aware interview question"""
        try:
            if user_response:
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
                prompt = f"""
                {self.conversation_context}
                
                This is the start of the interview. Generate an engaging opening question that:
                1. Welcomes the candidate warmly
                2. Asks them to tell you about themselves
                3. Uses natural, conversational language
                4. Sets a friendly, professional tone
                
                Return ONLY the question, no additional text.
                """
            
            question = self.ai_provider(prompt)
            
            if not question:
                raise Exception("Empty response from API")
            
            # Clean up the response
            if question.startswith('"') and question.endswith('"'):
                question = question[1:-1]
            
            question = question.replace('**', '').replace('*', '')
            
            if not question.endswith('?'):
                question += '?'
            
            return question
            
        except Exception as e:
            logger.error(f"Error generating question: {e}")
            fallback_questions = [
                "Could you tell me a bit about yourself and your background?",
                "What interests you most about this role?",
                "Can you walk me through a challenging project you've worked on?",
                "What are your greatest strengths as a professional?",
                "Where do you see yourself in the next few years?",
                "What motivates you in your work?"
            ]
            return fallback_questions[interview_state['question_count'] % len(fallback_questions)]
    
    def format_interview_history(self) -> str:
        """Format the interview history for context"""
        if not interview_state['interview_history']:
            return "No previous questions asked yet."
        
        history = []
        for i, (question, response) in enumerate(interview_state['interview_history'], 1):
            history.append(f"Q{i}: {question}")
            history.append(f"A{i}: {response}")
        
        return "\n".join(history)

# Initialize the interviewer
interviewer = WebInterviewer()

def auto_interview_loop():
    """Automatic interview loop that runs in background"""
    while interview_state['is_active']:
        try:
            # Check if interview was ended manually
            if not interview_state['is_active']:
                break
                
            # Generate and ask question
            if interview_state['question_count'] == 0:
                question = interviewer.generate_question()
            else:
                # Get the last response from history
                if interview_state['interview_history']:
                    last_response = interview_state['interview_history'][-1][1]
                    question = interviewer.generate_question(last_response)
                else:
                    question = interviewer.generate_question()
            
            interview_state['current_question'] = question
            
            # Check again if interview was ended
            if not interview_state['is_active']:
                break
            
            # Speak the question
            interviewer.speak(question)
            
            # Emit question to frontend
            socketio.emit('new_question', {
                'question': question,
                'question_count': interview_state['question_count']
            })
            
            # Listen for response
            interview_state['is_listening'] = True
            socketio.emit('listening_started')
            
            user_response = interviewer.listen()
            
            interview_state['is_listening'] = False
            socketio.emit('listening_stopped')
            
            # Check if interview was ended during listening
            if not interview_state['is_active']:
                break
            
            if user_response:
                # Store the Q&A pair
                interview_state['interview_history'].append((question, user_response))
                interview_state['question_count'] += 1
                
                # Emit response to frontend
                socketio.emit('response_received', {
                    'user_response': user_response,
                    'question_count': interview_state['question_count']
                })
                
                # Check if we should continue (max 10 questions or time limit)
                if interview_state['question_count'] >= 10:
                    break
                    
                # Small pause before next question
                time.sleep(1)
            else:
                # If no response, try again
                socketio.emit('no_response_detected')
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"Error in auto interview loop: {e}")
            break
    
    # End interview only if not already ended manually
    if interview_state['is_active']:
        interview_state['is_active'] = False
        end_interview_auto()

def end_interview_auto():
    """End interview automatically"""
    try:
        # Calculate total time
        if interview_state['start_time']:
            total_time = time.time() - interview_state['start_time']
            total_minutes = int(total_time // 60)
        else:
            total_minutes = 0
        
        # Closing message
        closing_message = f"Thank you so much for taking the time to speak with me today. We've had a great {total_minutes}-minute conversation, and I've really enjoyed learning more about your background and experience."
        interviewer.speak(closing_message)
        
        socketio.emit('interview_ended', {
            'message': closing_message,
            'total_time_minutes': total_minutes,
            'total_questions': interview_state['question_count']
        })
        
    except Exception as e:
        logger.error(f"Error ending interview: {e}")

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/start-voice-interview', methods=['POST'])
def start_voice_interview():
    """Start a new voice interview"""
    try:
        # Reset interview state
        interview_state['is_active'] = True
        interview_state['interview_history'] = []
        interview_state['question_count'] = 0
        interview_state['start_time'] = time.time()
        interview_state['is_listening'] = False
        
        # Start automatic interview loop in background
        interview_thread = threading.Thread(target=auto_interview_loop, daemon=True)
        interview_thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Interview started successfully - automatic mode enabled'
        })
        
    except Exception as e:
        logger.error(f"Error starting interview: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/interview-status', methods=['GET'])
def get_interview_status():
    """Get current interview status"""
    return jsonify({
        'is_active': interview_state['is_active'],
        'is_listening': interview_state['is_listening'],
        'current_question': interview_state['current_question'],
        'question_count': interview_state['question_count'],
        'interview_history': interview_state['interview_history']
    })

@app.route('/api/end-interview', methods=['POST'])
def end_interview():
    """End the current interview"""
    try:
        # Stop the interview immediately
        interview_state['is_active'] = False
        interview_state['is_listening'] = False
        
        # Calculate total time
        if interview_state['start_time']:
            total_time = time.time() - interview_state['start_time']
            total_minutes = int(total_time // 60)
        else:
            total_minutes = 0
        
        # Closing message
        closing_message = f"Thank you so much for taking the time to speak with me today. We've had a great {total_minutes}-minute conversation, and I've really enjoyed learning more about your background and experience."
        interviewer.speak(closing_message)
        
        # Emit WebSocket event to update frontend
        socketio.emit('interview_ended', {
            'message': closing_message,
            'total_time_minutes': total_minutes,
            'total_questions': interview_state['question_count']
        })
        
        return jsonify({
            'success': True,
            'message': closing_message,
            'total_time_minutes': total_minutes,
            'total_questions': interview_state['question_count']
        })
        
    except Exception as e:
        logger.error(f"Error ending interview: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def check_dependencies():
    """Check if all required dependencies are installed"""
    try:
        import google.generativeai
        import speech_recognition
        import pyttsx3
        import pyaudio
        return True
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return False

def open_browser():
    """Open the application in the default browser"""
    try:
        # Wait a moment for the server to start
        time.sleep(1.5)
        webbrowser.open('http://localhost:5000')
        print("🌐 Browser opened automatically!")
    except Exception as e:
        logger.warning(f"Could not open browser automatically: {e}")
        print("⚠️  Please manually open your browser and go to: http://localhost:5000")

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 AI Mock Interviewer - Web Application")
    print("=" * 60)
    
    print("Checking dependencies...")
    if check_dependencies():
        print("✅ All dependencies are installed!")
    else:
        print("❌ Some dependencies are missing. Please run: pip install -r requirements.txt")
        exit(1)
    
    print("Starting web application...")
    print("The application will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Show configuration
    config = get_config()
    config.print_config()
    
    # Start browser opening in a separate thread
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # Run the Flask app
    socketio.run(app, host='0.0.0.0', port=5000, debug=True) 