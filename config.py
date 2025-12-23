from dotenv import load_dotenv
import os

load_dotenv()  # Loading environment variables from the .env file

class Config:
    # API keys
    NAGA_AC_API_KEY = os.getenv("NAGA_AC_API_KEY")
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    FISH_API_KEY = os.getenv("FISH_API_KEY")
    POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")
    GOOGLE_TTS_API_KEY=os.getenv('GOOGLE_TTS_API_KEY')
    FISH_AUDIO_API_KEY=os.getenv("FISH_AUDIO_API_KEY")
    AZURE_CONNECTION_STRING=os.getenv("AZURE_CONNECTION_STRING")
    AZURE_CONTAINER_NAME=os.getenv("AZURE_CONTAINER_NAME")
    

    # Video parameters
    VIDEO_WIDTH = 1080
    VIDEO_HEIGHT = 1920