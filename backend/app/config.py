import os
from dataclasses import dataclass


@dataclass
class Settings:
    # On macOS/Windows Docker Desktop this resolves to the host automatically.
    # On Linux the docker-compose file adds an extra_hosts entry so it works there too.
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
    OCR_MODEL: str = os.getenv("OCR_MODEL", "glm-ocr")
    OCR_DPI: int = int(os.getenv("OCR_DPI", "220"))
    OCR_NUM_CTX: int = int(os.getenv("OCR_NUM_CTX", "8192"))
    OCR_NUM_PREDICT: int = int(os.getenv("OCR_NUM_PREDICT", "4096"))
    OCR_TIMEOUT: int = int(os.getenv("OCR_TIMEOUT", "300"))


settings = Settings()
