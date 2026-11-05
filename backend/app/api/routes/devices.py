from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import DeviceTransferStatus, UserRole
from app.models.user import User
from app.schemas.device import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    PendingTransferResponse,
    SimpleDetailResponse,
    TransferApproveRequest,
    TransferRejectRequest,
)
from app.services import devices
from app.services.audit import write_audit_event

router = APIRouter(prefix="/devices", tags=["Dispositivos"])

_patient_only = require_roles(UserRole.PATIENT)


@router.put("/me", response_model=DeviceRegisterResponse)
async def register_my_device(
    payload: DeviceRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_patient_only),
) -> DeviceRegisterResponse:
    """Registra o actualiza el dispositivo activo y su token FCM."""
    active = await devices.active_device(db, current_user.id)
    if active is not None and not devices.matches_device(active, payload.device_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este dispositivo no es el activo de tu cuenta.",
        )

    device = await devices.register_or_touch(
        db,
        current_user,
        device_id=payload.device_id,
        name=payload.device_name,
        fcm_token=payload.fcm_token,
        activate=True,
    )
    await write_audit_event(
        db,
        user=current_user,
        action="device_registered",
        entity_type="device",
        entity_id=device.id,
        request=request,
        detail=f"nombre={device.name}",
    )
    await db.commit()
    return DeviceRegisterResponse(device_name=device.name)


@router.get(
    "/transfers/pending",
    response_model=PendingTransferResponse | None,
    responses={204: {"description": "No hay solicitudes pendientes"}},
)
async def pending_transfer(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_patient_only),
) -> PendingTransferResponse | Response:
    """Solicitud que espera la aprobación de este dispositivo (A)."""
    transfer = await devices.pending_transfer(db, current_user.id)
    if transfer is None:
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    approval_token = devices.derive_approval_token(
        transfer.id, transfer.user_id, transfer.new_device_hash
    )
    payload = PendingTransferResponse(
        transfer_id=transfer.id,
        requested_device_name=transfer.new_device_name,
        requested_at=transfer.created_at,
        expires_in=devices.seconds_left(transfer),
        approval_token=approval_token,
        submitted_code=transfer.submitted_code,
        submissions_left=max(
            0,
            settings.device_transfer_max_code_submissions - transfer.code_submissions,
        ),
    )
    await db.commit()
    return payload


@router.post("/transfers/{transfer_id}/approve", response_model=SimpleDetailResponse)
async def approve_transfer(
    transfer_id: str,
    payload: TransferApproveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_patient_only),
) -> SimpleDetailResponse:
    """Aprueba la solicitud y deja sin acceso a este dispositivo de inmediato."""
    active = await devices.active_device(db, current_user.id)
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este dispositivo ya no es el activo.",
        )
    try:
        transfer = await devices.approve_transfer(
            db,
            current_user,
            active,
            transfer_id=transfer_id,
            approval_token=payload.approval_token,
        )
    except devices.DeviceTransferError as error:
        await db.commit()
        raise HTTPException(status_code=error.status_code, detail=error.message) from None

    await write_audit_event(
        db,
        user=current_user,
        action="device_transfer_approved",
        entity_type="device_transfer",
        entity_id=transfer.id,
        request=request,
        detail=f"dispositivo={transfer.new_device_name}",
    )
    await db.commit()
    return SimpleDetailResponse(
        detail="Sesión transferida. Este dispositivo ya no tiene acceso."
    )


@router.post("/transfers/{transfer_id}/reject", response_model=SimpleDetailResponse)
async def reject_transfer(
    transfer_id: str,
    payload: TransferRejectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_patient_only),
) -> SimpleDetailResponse:
    """Rechaza o reporta la propuesta (código incorrecto, ``not_me`` o expiró)."""
    active = await devices.active_device(db, current_user.id)
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este dispositivo ya no es el activo.",
        )
    existing = await devices.get_transfer(db, transfer_id)
    if existing is None or existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No encontramos esa solicitud."
        )
    try:
        transfer = await devices.reject_transfer(db, transfer_id, payload.reason)
    except devices.DeviceTransferError as error:
        await db.commit()
        raise HTTPException(status_code=error.status_code, detail=error.message) from None

    # Un código incorrecto solo es ``failed`` cuando ya no quedan intentos; si
    # aún puede reintentarse, se registra como rechazo de esa propuesta.
    if payload.reason == "not_me":
        action = "device_transfer_rejected"
        detail = "motivo=no_fui_yo"
    elif payload.reason == "expired":
        action = "device_transfer_expired"
        detail = "motivo=expirado_en_dispositivo_activo"
    elif transfer.status == DeviceTransferStatus.FAILED:
        action = "device_transfer_failed"
        detail = "motivo=intentos_agotados"
    else:
        action = "device_transfer_rejected"
        detail = "motivo=codigo_incorrecto"
    await write_audit_event(
        db,
        user=current_user,
        action=action,
        entity_type="device_transfer",
        entity_id=transfer.id,
        request=request,
        detail=f"{detail} propuestas={transfer.code_submissions}",
    )
    await db.commit()

    if payload.reason == "not_me":
        return SimpleDetailResponse(
            detail="Solicitud rechazada. Cambia tu contraseña si no reconoces el intento."
        )
    if payload.reason == "expired":
        return SimpleDetailResponse(detail="La solicitud expiró.")
    if transfer.status.value == "failed":
        return SimpleDetailResponse(detail="Se agotaron los intentos de esta solicitud.")
    return SimpleDetailResponse(detail="Código incorrecto. Espera otra propuesta.")
