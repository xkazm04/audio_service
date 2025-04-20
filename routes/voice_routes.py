from pydantic import BaseModel
from sqlalchemy.orm import Session
from uuid import UUID
from models.models import Voice
from database import get_db
import os
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Form, HTTPException, File, UploadFile
from typing import List
from elevenlabs import ElevenLabs
from functions.eleven_api import get_voice_settings, update_voice_settings, delete_voice_eleven
from functions.voice import create_voice_to_pg
import logging
from schemas.voice import VoiceResponse, VoiceSettingsModel

load_dotenv()

ELEVEN_URL = "https://api.elevenlabs.io/v1/voices/add"
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
HUME_API_KEY = os.getenv("HUME_API_KEY")

client = ElevenLabs(
    api_key=ELEVEN_API_KEY,
)

router = APIRouter()

@router.post("/", response_model=VoiceResponse)
async def create_voice(
    project_id: UUID = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    label: str = Form(None),
    samples: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    # TBD what if project does not exist - error handling
    client = ElevenLabs(api_key=ELEVEN_API_KEY)

    # Read all the sample files
    files_payload = []
    for sample in samples:
        contents = await sample.read()
        files_payload.append((sample.filename, contents))

    # Call the ElevenLabs client to create a new voice
    try:
        resp = client.voices.add(
            name=name,
            files=files_payload
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calling ElevenLabs: {str(e)}")

    # Access the voice_id directly as an attribute
    try:
        voice_id = resp.voice_id
    except AttributeError:
        raise HTTPException(
            status_code=500, detail="ElevenLabs response did not contain a voice_id")

    # Create a new Voice record in the database
    new_voice = create_voice_to_pg(
        project_id=project_id,
        name=name,
        voice_id=voice_id,
        description=description,
        label=label,
        db=db,
    )
    return new_voice

@router.post("/test", response_model=VoiceResponse)
def test_create_voice(
    project_id: UUID = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    label: str = Form(None),
    db: Session = Depends(get_db),
):
    voice = create_voice_to_pg(
        project_id=project_id,
        name=name,
        description=description,
        label=label,
        db=db,
    )
    return voice

@router.get("/project/{project_id}", response_model=list[VoiceResponse])
def get_voices(project_id: UUID, db: Session = Depends(get_db)):
    # TBD error handling
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



