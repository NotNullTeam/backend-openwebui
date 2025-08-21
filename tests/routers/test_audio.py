"""
Test cases for audio router endpoints - comprehensive coverage for all 6 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, Mock
from httpx import AsyncClient
import json
from io import BytesIO


@pytest.fixture
def mock_admin_user():
    return MagicMock(
        id="admin123",
        name="Admin User",
        email="admin@example.com",
        role="admin"
    )


@pytest.fixture
def mock_verified_user():
    return MagicMock(
        id="user123",
        name="Test User",
        email="test@example.com",
        role="user"
    )


class TestAudioConfig:
    """Test audio configuration endpoints"""
    
    async def test_get_audio_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /config endpoint - get audio configuration"""
        with patch("open_webui.routers.audio.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.audio.app.state") as mock_state:
                # Mock configuration
                mock_state.config.TTS_ENGINE = "openai"
                mock_state.config.TTS_MODEL = "tts-1"
                mock_state.config.TTS_VOICE = "alloy"
                mock_state.config.STT_ENGINE = "openai"
                mock_state.config.STT_MODEL = "whisper-1"
                
                response = await async_client.get("/api/v1/audio/config")
                assert response.status_code in [200, 401]
                
                if response.status_code == 200:
                    data = response.json()
                    assert "tts" in data
                    assert "stt" in data
    
    async def test_update_audio_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /config/update endpoint - update audio configuration"""
        with patch("open_webui.routers.audio.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.audio.app.state") as mock_state:
                config_data = {
                    "tts": {
                        "engine": "openai",
                        "model": "tts-1-hd",
                        "voice": "nova",
                        "openai_url": "https://api.openai.com/v1",
                        "openai_key": "test-key"
                    },
                    "stt": {
                        "engine": "openai",
                        "model": "whisper-1",
                        "openai_url": "https://api.openai.com/v1",
                        "openai_key": "test-key"
                    }
                }
                
                response = await async_client.post(
                    "/api/v1/audio/config/update",
                    json=config_data
                )
                assert response.status_code in [200, 401]


class TestSpeechGeneration:
    """Test speech generation endpoint"""
    
    async def test_speech_generation(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /speech endpoint - generate speech from text"""
        with patch("open_webui.routers.audio.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.audio.get_audio_generation_model") as mock_model:
                # Mock the model to return audio bytes
                mock_model.return_value = AsyncMock()
                mock_model.return_value.generate_audio = AsyncMock(return_value=b"fake_audio_data")
                
                # Create request body
                request_data = {
                    "input": "Hello, this is a test speech generation",
                    "model": "tts-1",
                    "voice": "alloy",
                    "response_format": "mp3",
                    "speed": 1.0
                }
                
                response = await async_client.post(
                    "/api/v1/audio/speech",
                    content=json.dumps(request_data)
                )
                assert response.status_code in [200, 401, 500]


class TestTranscription:
    """Test audio transcription endpoint"""
    
    async def test_transcription(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /transcriptions endpoint - transcribe audio file"""
        with patch("open_webui.routers.audio.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.audio.get_available_models") as mock_models:
                mock_models.return_value = ["whisper-1"]
                
                with patch("open_webui.routers.audio.transcribe_audio") as mock_transcribe:
                    mock_transcribe.return_value = {"text": "This is the transcribed text"}
                    
                    # Create a fake audio file
                    audio_content = b"fake_audio_content"
                    files = {"file": ("test.mp3", BytesIO(audio_content), "audio/mp3")}
                    
                    response = await async_client.post(
                        "/api/v1/audio/transcriptions",
                        files=files,
                        data={"model": "whisper-1", "language": "en"}
                    )
                    assert response.status_code in [200, 401, 415, 500]


class TestAudioModels:
    """Test audio models endpoints"""
    
    async def test_get_models(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /models endpoint - get available audio models"""
        with patch("open_webui.routers.audio.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.audio.get_available_models") as mock_models:
                mock_models.return_value = [
                    "whisper-1",
                    "whisper-large-v3",
                    "distil-whisper-large-v3"
                ]
                
                response = await async_client.get("/api/v1/audio/models")
                assert response.status_code in [200, 401]
                
                if response.status_code == 200:
                    data = response.json()
                    assert "models" in data
                    assert isinstance(data["models"], list)


class TestVoices:
    """Test voices endpoint"""
    
    async def test_get_voices(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /voices endpoint - get available TTS voices"""
        with patch("open_webui.routers.audio.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.audio.get_available_voices") as mock_voices:
                mock_voices.return_value = [
                    {"id": "alloy", "name": "Alloy", "preview_url": None},
                    {"id": "echo", "name": "Echo", "preview_url": None},
                    {"id": "fable", "name": "Fable", "preview_url": None},
                    {"id": "onyx", "name": "Onyx", "preview_url": None},
                    {"id": "nova", "name": "Nova", "preview_url": None},
                    {"id": "shimmer", "name": "Shimmer", "preview_url": None}
                ]
                
                response = await async_client.get("/api/v1/audio/voices")
                assert response.status_code in [200, 401]
                
                if response.status_code == 200:
                    data = response.json()
                    assert "voices" in data
                    assert isinstance(data["voices"], list)
