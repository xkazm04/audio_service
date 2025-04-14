from fastapi import APIRouter
from routes.speech_routes import router as speech_router
from routes.voice_routes import router as voice_router
api_router = APIRouter()


api_router.include_router(speech_router, prefix="/speech", tags=["Speech"])
api_router.include_router(voice_router, prefix="/voices", tags=["Voices"])