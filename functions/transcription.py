import os
import requests
import logging
import tempfile
from dotenv import load_dotenv
from typing import Dict, Any, List, Union
from fastapi import HTTPException
import whisper
import torch

load_dotenv()

logging.basicConfig(level=logging.INFO)

# Constants
ELEVEN_API_BASE_URL = "https://api.elevenlabs.io/v1"
ELEVEN_STT_URL = f"{ELEVEN_API_BASE_URL}/speech-to-text"
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logging.info(f"Using device: {DEVICE} for Whisper model")

# Load Whisper model once at module level for efficiency
DEFAULT_WHISPER_MODEL = "turbo"
whisper_model = None

def get_whisper_model(model_name: str = DEFAULT_WHISPER_MODEL):
    global whisper_model
    if whisper_model is None:
        logging.info(f"Loading Whisper model: {model_name} on {DEVICE}")
        try:
            whisper_model = whisper.load_model(model_name, device=DEVICE)
            logging.info(f"Model device: {next(whisper_model.parameters()).device}")
        except Exception as e:
            logging.error(f"Failed to load model on {DEVICE}: {e}")
            raise
    return whisper_model

def transcribe_with_whisper(
    audio_contents: Union[bytes, List[bytes]], 
    filenames: Union[str, List[str]], 
    model_name: str = DEFAULT_WHISPER_MODEL
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Transcribe audio using the Whisper model
    
    Args:
        audio_contents: Binary content of one or more audio files
        filenames: Names of the audio files
        model_name: Whisper model to use
        
    Returns:
        Dictionary or list of dictionaries with transcription results
    """
    # Convert single inputs to lists for consistent handling
    if not isinstance(audio_contents, list):
        audio_contents = [audio_contents]
        filenames = [filenames]
    
    model = get_whisper_model(model_name)
    results = []
    
    for content, filename in zip(audio_contents, filenames):
        try:
            # Save the audio content to a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{filename.split('.')[-1]}") as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            # Transcribe using Whisper
            logging.info(f"Transcribing {filename} with Whisper on {DEVICE}")
            result = model.transcribe(temp_path)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            # Extract the detected language
            language_code = result.get("language", "en")
            
            # Format the result to match the expected schema
            transcription_result = {
                "text": result["text"],
                "language_code": language_code,
                "language_probability": 1.0,  # Whisper doesn't provide a language probability
                "words": [],  # Will be populated with segment data below
                "segments": result["segments"],
                "confidence": result.get("confidence", 1.0),
                "engine": "whisper",
                "model": model_name
            }
            
            # Convert segments to words for compatibility with the expected schema
            for segment in result["segments"]:
                transcription_result["words"].append({
                    "text": segment["text"],
                    "type": "word",
                    "start": segment["start"],
                    "end": segment["end"],
                    "speaker_id": "0"  # Default speaker ID
                })
            
            results.append(transcription_result)
            
        except Exception as e:
            logging.error(f"Error transcribing with Whisper: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to transcribe audio with Whisper: {str(e)}")
    
    # Return a single result if only one file was processed
    return results[0] if len(results) == 1 else results

# Eleven Labs API variant
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

def transcribe_with_fallback(
    audio_contents: Union[bytes, List[bytes]], 
    filenames: Union[str, List[str]], 
    whisper_model: str = DEFAULT_WHISPER_MODEL,
    eleven_model: str = "scribe_v1"
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Transcribe audio using Whisper first, and fall back to ElevenLabs if Whisper fails.
    
    Args:
        audio_contents: Binary content of one or more audio files
        filenames: Names of the audio files
        whisper_model: Whisper model to use
        eleven_model: ElevenLabs model to use
        
    Returns:
        Dictionary or list of dictionaries with transcription results
    """
    # Convert single inputs to lists for consistent handling
    if not isinstance(audio_contents, list):
        audio_contents = [audio_contents]
        filenames = [filenames]
        single_input = True
    else:
        single_input = False
    
    results = []
    
    for content, filename in zip(audio_contents, filenames):
        try:
            # Try Whisper first
            result = transcribe_with_whisper(content, filename, whisper_model)
            if isinstance(result, list):
                result = result[0]  # Get first result since we're processing one file at a time here
            
        except Exception as whisper_error:
            logging.warning(f"Whisper transcription failed, falling back to ElevenLabs: {whisper_error}")
            try:
                # Fall back to ElevenLabs
                result = transcribe_audio(content, filename, eleven_model)
                result["engine"] = "elevenlabs"  # Add engine information
                result["model"] = eleven_model
            except Exception as eleven_error:
                # Both methods failed
                logging.error(f"Both transcription methods failed: {eleven_error}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Transcription failed with both engines. Whisper: {str(whisper_error)}. ElevenLabs: {str(eleven_error)}"
                )
        
        results.append(result)
    
    # Return a single result if only one file was processed
    return results[0] if single_input else results