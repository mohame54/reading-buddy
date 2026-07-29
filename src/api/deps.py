from fastapi import Request

from src.services.stt_service import STTService


def get_stt_service(request: Request) -> STTService:
    return request.app.state.stt_service
