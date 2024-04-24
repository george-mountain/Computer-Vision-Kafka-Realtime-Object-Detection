from typing import List
from pydantic import BaseModel


class Models:
    class DetectionRequest(BaseModel):
        topic: str
        links: List[str]
        live: bool
        saving_timer: int

    class ConsumeDataRequest(BaseModel):
        topic: str
        limit: int

    class StartWritingToDatabaseRequest(BaseModel):
        topic: str
