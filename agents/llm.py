import instructor
from openai import OpenAI

from config import settings

OLLAMA_BASE_URL = 'http://localhost:11434/v1'
NVIDIA_BASE_URL = 'https://integrate.api.nvidia.com/v1'


def make_instructor_client() -> instructor.Instructor:
    if settings.nvidia_build_api_key:
        return instructor.from_openai(
            OpenAI(
                base_url=NVIDIA_BASE_URL,
                api_key=settings.nvidia_build_api_key,
            ),
            mode=instructor.Mode.TOOLS,
        )
    return instructor.from_openai(
        OpenAI(base_url=OLLAMA_BASE_URL, api_key='ollama'),
        mode=instructor.Mode.TOOLS,
    )