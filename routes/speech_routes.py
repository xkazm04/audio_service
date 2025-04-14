from pydantic import BaseModel
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from functions.eleven_api import generate_speech, stream_speech
from functions.transcription import DEFAULT_WHISPER_MODEL, transcribe_with_fallback
from fastapi.responses import StreamingResponse
import logging

# Will contain text-to-speech and speech-to-text routes

router = APIRouter()

class TextToSpeechRequest(BaseModel):
    text: str
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    output_format: str = "mp3_44100_128"
    model_id: str = "eleven_multilingual_v2"


@router.post("/text-to-speech")
def text_to_speech(request: TextToSpeechRequest):
    try:
        audio_stream = generate_speech(
            text=request.text,
            voice_id=request.voice_id,
            output_format=request.output_format,
            model_id=request.model_id
        )
        return StreamingResponse(audio_stream, media_type="audio/mpeg")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")


class StreamSpeechRequest(BaseModel):
    text: str
    voice_id: str # default "LPJ71OSKKaosXFK91Zee"
    model_id: str # default "eleven_multilingual_v2"
    output_format: str # default "mp3_44100_128"

@router.post("/stream")
def stream_speech_route(request: StreamSpeechRequest):
    """
    Stream text-to-speech using ElevenLabs API
    """
    try:
        audio_stream = stream_speech(
            text=request.text,
            voice_id=request.voice_id,
            model_id=request.model_id,
            output_format=request.output_format
        )
        return StreamingResponse(audio_stream, media_type="audio/mpeg")
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Unexpected error in stream_speech: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
@router.post("/transcribe")  # Remove response_model to debug
async def transcribe_speech(
    file: UploadFile = File(...),
    model_id: str = Form("scribe_v1"),
    whisper_model: str = Form(DEFAULT_WHISPER_MODEL)
):
    """
    Transcribe an audio file to text using Whisper with ElevenLabs as fallback
    """
    try:
        # Read the file content
        file_content = await file.read()

        # Call the transcribe_with_fallback function
        transcription_result = transcribe_with_fallback(
            audio_contents=file_content,
            filenames=file.filename,
            whisper_model=whisper_model,
            eleven_model=model_id
        )

        # For debugging: Print the result structure
        logging.debug(f"Transcription result keys: {transcription_result.keys() if isinstance(transcription_result, dict) else 'Not a dict'}")
        
        return transcription_result
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error transcribing speech: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to transcribe audio: {str(e)}")

