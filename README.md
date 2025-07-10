# AI Mock Interviewer 🤖

A dynamic, voice-based AI mock interviewer that uses the Gemini API to conduct natural, conversational interviews. The system generates context-aware follow-up questions based on your responses, creating a human-like interview experience.

## Features

- **Voice Interaction**: Speak naturally with the interviewer using your microphone
- **Dynamic Questioning**: AI-generated follow-up questions based on your responses
- **Human-like Communication**: Natural, conversational language with professional tone
- **Real-time Speech Recognition**: Converts your voice to text for analysis
- **Text-to-Speech Output**: Hear the interviewer's questions and responses
- **Error Handling**: Graceful handling of speech recognition failures and API errors

## Prerequisites

- Python 3.8 or higher
- Working microphone
- Internet connection (for Gemini API and speech recognition)
- Speakers or headphones

## Installation

1. **Clone or download this project**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your Gemini API key** (optional):
   ```bash
   # Option 1: Set environment variable
   export GEMINI_API_KEY="your_api_key_here"
   
   # Option 2: The code includes a fallback API key
   ```

## Usage

1. **Run the interviewer**:
   ```bash
   python ai_mock_interviewer.py
   ```

2. **Follow the prompts**:
   - Press Enter to begin the interview
   - Speak clearly when responding to questions
   - The interview will automatically end after 5-7 questions

3. **Exit anytime**: Press `Ctrl+C` to end the interview early

## How It Works

1. **Initialization**: The system sets up speech recognition, text-to-speech, and connects to the Gemini API
2. **Welcome**: A friendly greeting starts the interview
3. **Dynamic Questioning**: 
   - The AI generates an initial question
   - Your voice response is captured and transcribed
   - The AI analyzes your response and generates relevant follow-up questions
   - This continues for 5-7 questions total
4. **Natural Flow**: Conversational fillers and natural language make the interaction feel human
5. **Conclusion**: A professional closing message ends the interview

## Technical Details

### Dependencies

- **google-generativeai**: Powers the AI question generation and response analysis
- **speech_recognition**: Captures and transcribes voice input
- **pyttsx3**: Converts text to speech for interviewer responses
- **pyaudio**: Audio processing for microphone input

### API Usage

The system uses Google's Gemini API for:
- Generating context-aware interview questions
- Analyzing user responses for better follow-up questions
- Maintaining conversational flow and natural language

### Speech Processing

- **Input**: Microphone captures your voice
- **Recognition**: Google Speech Recognition converts speech to text
- **Analysis**: Gemini API processes your response
- **Output**: Text-to-speech converts AI responses back to voice

## Troubleshooting

### Common Issues

1. **"No module named 'pyaudio'"**:
   ```bash
   # On Windows:
   pip install pipwin
   pipwin install pyaudio
   
   # On macOS:
   brew install portaudio
   pip install pyaudio
   
   # On Linux:
   sudo apt-get install python3-pyaudio
   pip install pyaudio
   ```

2. **Microphone not detected**:
   - Check your microphone permissions
   - Ensure microphone is set as default input device
   - Test microphone in other applications

3. **Speech recognition fails**:
   - Speak clearly and at normal volume
   - Reduce background noise
   - Check internet connection (required for Google Speech Recognition)

4. **API errors**:
   - Verify internet connection
   - Check if the provided API key is valid
   - The system includes fallback questions if API fails

### Performance Tips

- Use a quiet environment for better speech recognition
- Speak at normal pace and volume
- Keep responses concise but detailed
- Ensure stable internet connection

## Customization

### Modifying Interview Length

Edit the `max_questions` variable in the `AIMockInterviewer` class:
```python
self.max_questions = 10  # Change to desired number
```

### Adjusting Speech Settings

Modify TTS settings in the `setup_tts` method:
```python
self.tts_engine.setProperty('rate', 180)  # Words per minute
self.tts_engine.setProperty('volume', 0.9)  # Volume level
```

### Changing Interview Style

Update the `conversation_context` variable to modify the AI's behavior and tone.

## Security Notes

- The provided API key is for demonstration purposes
- For production use, use your own Gemini API key
- Voice data is processed by Google's services (see their privacy policy)
- No voice data is stored locally

## License

This project is provided as-is for educational and demonstration purposes.

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify all dependencies are installed correctly
3. Ensure your microphone and speakers are working
4. Check your internet connection

---

**Enjoy your AI-powered interview experience!** 🎤✨ 