from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Table, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class Voice(Base):
    __tablename__ = "voices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    voice_id = Column(String, nullable=False)  # ElevenLabs reference
    label = Column(String, nullable=True)
    project_id = Column(UUID(as_uuid=True))