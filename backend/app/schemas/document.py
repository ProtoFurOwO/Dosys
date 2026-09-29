from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    original_name: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
