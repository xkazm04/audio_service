from uuid import UUID
from models.models import Voice
from database import get_db
from fastapi import  Form, Depends
from sqlalchemy.orm import Session

def create_voice_to_pg(
    project_id: UUID = Form(...),
    name: str = Form(...),
    voice_id: str = Form(...),
    description: str = Form(None),
    label: str = Form(None),
    db: Session = Depends(get_db),
):
    new_voice = Voice(
        name=name,
        description=description,
        voice_id=voice_id,
        label=label,
        project_id=project_id,
    )
    db.add(new_voice)
    db.commit()
    db.refresh(new_voice)