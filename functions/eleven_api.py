import os
import requests
import logging
from dotenv import load_dotenv
from typing import Generator, Dict, Any
from fastapi import HTTPException
from elevenlabs import ElevenLabs

# Load environment variables
load_dotenv()

# Logging Configuration
logging.basicConfig(level=logging.INFO)

# Constants
ELEVEN_API_BASE_URL = "https://api.elevenlabs.io/v1"
ELEVEN_TTS_URL = f"{ELEVEN_API_BASE_URL}/text-to-speech"
ELEVEN_STT_URL = f"{ELEVEN_API_BASE_URL}/speech-to-text"
ELEVEN_URL = f"{ELEVEN_API_BASE_URL}/voices/add"
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")

if not ELEVEN_API_KEY:
    raise ValueError("Eleven API key is missing. Please set it in the .env file.")

def generate_speech(text: str, voice_id: str, output_format: str, model_id: str) -> Generator:
    url = f"{ELEVEN_TTS_URL}/{voice_id}?output_format={output_format}"
    
    headers = {
        "Content-Type": "application/json",
        "xi-api-key": ELEVEN_API_KEY  # API Key is kept **secret** in the backend
    }
    
    payload = {
        "text": text,
        "model_id": model_id
    }

    try:
        response = requests.post(url, headers=headers, json=payload, stream=True)
        response.raise_for_status()  # Ensure request was successful

        # Use an iterator to stream the content properly
        return response.iter_content(chunk_size=1024)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling ElevenLabs API: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate speech.")
    

def transcribe_audio(audio_content: bytes, filename: str, model_id: str = "scribe_v1") -> Dict[str, Any]:
    """
    Transcribe audio to text using ElevenLabs Speech-to-Text API
    
    Args:
        audio_content: Binary content of the audio file
        filename: Name of the audio file
        model_id: Model ID to use for transcription (default: scribe_v1)
        
    Returns:
        Dictionary with transcription result
    """
    headers = {
        "xi-api-key": ELEVEN_API_KEY
    }
    
    files = {
        "file": (filename, audio_content, "audio/mpeg")
    }
    
    data = {
        "model_id": model_id
    }
    
    try:
        response = requests.post(
            ELEVEN_STT_URL,
            headers=headers,
            files=files,
            data=data
        )
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling ElevenLabs Speech-to-Text API: {e}")
        error_detail = str(e)
        
        # Try to extract more detailed error information if available
        if hasattr(e, 'response') and e.response:
            try:
                error_json = e.response.json()
                if 'detail' in error_json:
                    error_detail = error_json['detail']
            except:
                pass
                
        raise HTTPException(status_code=500, detail=f"Failed to transcribe audio: {error_detail}")

def get_voice_settings(voice_id: str) -> Dict[str, Any]:
    url = f"{ELEVEN_API_BASE_URL}/voices/{voice_id}/settings"
    
    headers = {
        "xi-api-key": ELEVEN_API_KEY
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling ElevenLabs API: {e}")
        raise HTTPException(status_code=500, detail="Failed to get voice settings.")

def update_voice_settings(voice_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{ELEVEN_API_BASE_URL}/voices/{voice_id}/settings/edit"
    
    headers = {
        "Content-Type": "application/json",
        "xi-api-key": ELEVEN_API_KEY
    }
    
    try:
        response = requests.post(url, headers=headers, json=settings)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling ElevenLabs API: {e}")
        raise HTTPException(status_code=500, detail="Failed to update voice settings.")

def delete_voice_eleven(voice_id: str) -> Dict[str, Any]:
    url = f"{ELEVEN_API_BASE_URL}/voices/{voice_id}"
    
    headers = {
        "xi-api-key": ELEVEN_API_KEY
    }
    
    try:
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling ElevenLabs API: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete voice.")

def stream_speech(text: str, voice_id: str = "LPJ71OSKKaosXFK91Zee", model_id: str = "eleven_multilingual_v2", output_format: str = "mp3_44100_128"):
    try:
        client = ElevenLabs(api_key=ELEVEN_API_KEY)
        audio_stream = client.text_to_speech.convert_as_stream(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format=output_format
        )
        return audio_stream
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error streaming audio: {str(e)}")