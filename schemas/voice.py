from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from uuid import UUID

class TranscriptionWord(BaseModel):
    text: str
    type: str
    start: float
    end: float
    speaker_id: str
    characters: Optional[List[Dict[str, Any]]]


class TranscriptionResponse(BaseModel):
    language_code: str
    language_probability: float
    text: str
    words: List[TranscriptionWord]
    segments: Optional[List[Dict[str, Any]]] 
    engine: Optional[str] 
    model: Optional[str]
    confidence: Optional[float] 


class VoiceSettingsModel(BaseModel):
    stability: Optional[float]
    similarity_boost: Optional[float]
    style: Optional[float]
    use_speaker_boost: Optional[bool]
    

class VoiceBase(BaseModel):
    name: str
    description: str 
    voice_id: str
    label: str 


class VoiceCreate(VoiceBase):
    pass


class VoiceResponse(VoiceBase):
    id: UUID
    project_id: UUID

    class Config:
        orm_mode = True