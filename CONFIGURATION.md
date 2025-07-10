# AI Mock Interviewer Configuration Guide

## Quick Setup

The AI Mock Interviewer uses a simple `application.properties` file for configuration, just like Spring Boot applications.

## Configuration File: `application.properties`

Edit the `application.properties` file to change settings:

```properties
# AI Provider Configuration
ai.provider=openai
ai.model=gpt-4

# API Keys
openai.api.key=your-openai-api-key-here
gemini.api.key=your-gemini-api-key-here
anthropic.api.key=your-anthropic-api-key-here

# Interview Settings
interview.duration.minutes=30
speech.timeout.seconds=15
speech.phrase.time.limit.seconds=60
speech.wait.after.seconds=3
```

## Supported AI Providers

### 1. OpenAI
```properties
ai.provider=openai
ai.model=gpt-4
openai.api.key=sk-your-api-key-here
```
**Available Models:**
- `gpt-4`
- `gpt-4-turbo`
- `gpt-3.5-turbo`

### 2. Google Gemini
```properties
ai.provider=gemini
ai.model=gemini-2.0-flash
gemini.api.key=your-gemini-api-key-here
```
**Available Models:**
- `gemini-2.0-flash`
- `gemini-1.5-pro`
- `gemini-1.5-flash`
- `gemini-1.0-pro`

### 3. Anthropic Claude
```properties
ai.provider=anthropic
ai.model=claude-3-sonnet
anthropic.api.key=your-anthropic-api-key-here
```
**Available Models:**
- `claude-3-opus`
- `claude-3-sonnet`
- `claude-3-haiku`

## Configuration Options

### Interview Settings
- `interview.duration.minutes` - Interview duration in minutes (default: 30)
- `interview.max.questions` - Maximum questions (fallback)

### Speech Recognition
- `speech.timeout.seconds` - Time to wait for speech to start (default: 15)
- `speech.phrase.time.limit.seconds` - Maximum speech duration (default: 60)
- `speech.wait.after.seconds` - Wait time after speech (default: 3)

### Text-to-Speech
- `tts.rate` - Speech rate in words per minute (default: 180)
- `tts.volume` - Volume level 0.0 to 1.0 (default: 0.9)

## Quick Examples

### Switch to Gemini
```properties
ai.provider=gemini
ai.model=gemini-2.0-flash
gemini.api.key=AIzaSyCllftuYclAv1coi8RqrUJYoIzyTGd34FE
```

### Switch to OpenAI GPT-4
```properties
ai.provider=openai
ai.model=gpt-4
openai.api.key=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
```

### Change Interview Duration
```properties
interview.duration.minutes=45
```

### Adjust Speech Settings
```properties
speech.timeout.seconds=20
speech.phrase.time.limit.seconds=90
speech.wait.after.seconds=5
```

## Testing Configuration

### Check Current Settings
```bash
python config_loader.py
```

### Test AI Provider
```bash
python ai_factory.py
```

### Run Interview
```bash
python ai_mock_interviewer.py
```

## Troubleshooting

1. **API Key Issues**: Make sure your API key is correct and has sufficient credits
2. **Model Not Found**: Check the available models list above
3. **Import Errors**: Install required packages:
   ```bash
   pip install openai google-generativeai anthropic
   ```

## Security Note

- Keep your API keys secure
- Don't commit `application.properties` to version control
- Consider using environment variables for production 