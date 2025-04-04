# will contain Voice management routes
from pydantic import BaseModel
from sqlalchemy.orm import Session
from uuid import UUID
from models.models import Voice, Project, Apilog, User
from services.pricing import charge_user_credits, PriceList
from StoryTeller.audio_service.routes.voice_routes import get_current_user
from database import get_db
import os
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from elevenlabs import ElevenLabs
from services.eleven_api import generate_speech, get_voice_settings, update_voice_settings, delete_voice_eleven, stream_speech
from services.media.transcription import DEFAULT_WHISPER_MODEL, transcribe_with_fallback
from fastapi.responses import StreamingResponse
import logging
from schemas.voice_schemas import VoiceResponse, VoiceSettingsModel

load_dotenv()

ELEVEN_URL = "https://api.elevenlabs.io/v1/voices/add"
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
HUME_API_KEY = os.getenv("HUME_API_KEY")

client = ElevenLabs(
    api_key=ELEVEN_API_KEY,
)

router = APIRouter()


@router.post("/projects/{project_id}", response_model=VoiceResponse)
async def create_voice(
    project_id: UUID,
    voice_name: str = Form(...),
    description: str = Form(None),
    label: str = Form(None),
    samples: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    client = ElevenLabs(api_key=ELEVEN_API_KEY)

    # Read all the sample files.
    files_payload = []
    for sample in samples:
        contents = await sample.read()
        files_payload.append((sample.filename, contents))

    # Call the ElevenLabs client to create a new voice.
    try:
        resp = client.voices.add(
            name=voice_name,
            files=files_payload
        )
    except Exception as e:
        api_log = Apilog(
            user_id=current_user.id,
            endpoint="VoiceCreate",
            result="error",
            cost=PriceList.VOICE_CREATE.value
        )
        db.add(api_log)
        db.commit()     
        raise HTTPException(
            status_code=500, detail=f"Error calling ElevenLabs: {str(e)}")

    # Access the voice_id directly as an attribute.
    try:
        voice_id = resp.voice_id
    except AttributeError:
        api_log = Apilog(
            user_id=current_user.id,
            endpoint="VoiceCreate",
            result="error",
            cost=PriceList.VOICE_CREATE.value
        )
        db.add(api_log)
        db.commit()       
        raise HTTPException(
            status_code=500, detail="ElevenLabs response did not contain a voice_id")

    # Create a new Voice record in the database.
    new_voice = Voice(
        name=voice_name,
        description=description,
        voice_id=voice_id,
        label=label,
        project_id=project_id
    )
    api_log = Apilog(
        user_id=current_user.id,
        endpoint="VoiceCreate",
        result="ok",
        cost=PriceList.VOICE_CREATE.value
    )
    db.add(api_log)
    db.add(new_voice)
    db.commit()
    db.refresh(new_voice)
    return new_voice


@router.get("/project/{project_id}", response_model=list[VoiceResponse])
def get_voices(project_id: UUID, db: Session = Depends(get_db)):
    # Check if project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    voices = db.query(Voice).filter(Voice.project_id == project_id).all()
    return voices if voices else []

# Rename voice
class RenameVoiceRequest(BaseModel):
    name: str
@router.put("/{voice_id}")
def rename_voice(voice_id: UUID, request: RenameVoiceRequest, db: Session = Depends(get_db)):
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")

    voice.name = request.name
    db.commit()
    return voice

@router.delete("/{voice_id}")
def delete_voice(voice_id: UUID, db: Session = Depends(get_db)):
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    db.delete(voice)
    db.commit()
    delete_voice_eleven(voice.voice_id)
    return {"detail": "Voice deleted successfully"}


# Eleven labs API
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
    voice_id: str | None = "LPJ71OSKKaosXFK91Zee"
    model_id: str | None = "eleven_multilingual_v2"
    output_format: str | None = "mp3_44100_128"

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


@router.get("/{voice_id}/settings")
def get_voice_settings_route(voice_id: str):
    """
    Get voice settings for a specific ElevenLabs voice ID
    """
    try:
        settings = get_voice_settings(voice_id)
        return settings
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error getting voice settings: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get voice settings: {str(e)}"
        )


@router.post("/{voice_id}/settings")
def update_voice_settings_route(voice_id: str, settings: VoiceSettingsModel):
    """
    Update voice settings for a specific ElevenLabs voice ID
    """
    try:
        updated_settings = update_voice_settings(voice_id, settings.dict(exclude_none=True))
        return updated_settings
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error updating voice settings: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update voice settings: {str(e)}"
        )


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


