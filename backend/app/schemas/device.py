from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=64)
    device_name: str = Field(min_length=1, max_length=120)
    fcm_token: str | None = Field(default=None, max_length=255)


class DeviceRegisterResponse(BaseModel):
    detail: str = "Dispositivo registrado."
    device_name: str


class DeviceListItem(BaseModel):
    id: int
    name: str
    is_current: bool
    last_seen_at: datetime | None = None
    created_at: datetime


class PendingTransferResponse(BaseModel):
    """Solicitud pendiente que cualquier dispositivo autorizado puede revisar."""

    transfer_id: str
    requested_device_name: str
    requested_at: datetime
    expires_in: int
    approval_token: str
    submitted_code_hash: str | None = None
    submissions_left: int = 0


class TransferApproveRequest(BaseModel):
    approval_token: str = Field(min_length=20, max_length=255)


class TransferRejectRequest(BaseModel):
    reason: Literal["not_me", "mismatch", "expired"]


class SimpleDetailResponse(BaseModel):
    detail: str
