from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import DeviceTransferStatus, UserRole
from app.models.user import User
from app.schemas.device import (
    DeviceListItem,
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


async def _current_device(request: Request, db: AsyncSession, user: User):
    device_hash = getattr(request.state, "device_hash", None)
    if not device_hash:
        return None
    return await devices.find_active_device_by_hash(db, user.id, str(device_hash))


@router.get("/me", response_model=list[DeviceListItem])
async def list_my_devices(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_patient_only),
) -> list[DeviceListItem]:
    """Dispositivos autorizados del paciente; marca el que hace la petición."""
    current = await _current_device(request, db, current_user)
    active = await devices.active_devices(db, current_user.id)
    return [
        DeviceListItem(
            id=device.id,
            name=device.name,
            is_current=current is not None and device.id == current.id,
            last_seen_at=device.last_seen_at,
            created_at=device.created_at,
        )
        for device in active
    ]


@router.delete("/me/{device_id}", response_model=SimpleDetailResponse)
async def revoke_my_device(
    device_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_patient_only),
) -> SimpleDetailResponse:
    """Revoca un dispositivo propio; sus tokens dejan de servir al instante."""
    device = await devices.find_device_by_id(db, device_id)
    if device is None or device.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo no encontrado.")
    if not device.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese dispositivo ya no estaba activo.")

    name = device.name
    await devices.release_device_by_id(db, device.id)
    await write_audit_event(
        db,
        user=current_user,
        action="device_released",
        entity_type="device",
        entity_id=device.id,
        request=request,
        detail=f"nombre={name} origen=app",
    )
    await db.commit()
    return SimpleDetailResponse(detail=f"Dispositivo «{name}» revocado.")


@router.put("/me", response_model=DeviceRegisterResponse)
async def register_my_device(
    payload: DeviceRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_patient_only),
) -> DeviceRegisterResponse:
    """Registra o actualiza este dispositivo autorizado y su token FCM."""
    current = await devices.find_active_device(db, current_user.id, payload.device_id)
    if current is None:
        active = await devices.active_devices(db, current_user.id)
        if active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este dispositivo no está autorizado. Inicia sesión para solicitar acceso.",
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
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_patient_only),
) -> PendingTransferResponse | Response:
    """Solicitud que espera la aprobación de este dispositivo (A)."""
    current = await _current_device(request, db, current_user)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este dispositivo ya no está autorizado.",
        )
    transfer = await devices.pending_transfer(db, current_user.id)
    if transfer is None:
        await db.commit()
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={"Cache-Control": "no-store"},
        )

    approval_token = devices.derive_approval_token(
        transfer.id, transfer.user_id, transfer.new_device_hash
    )
    payload = PendingTransferResponse(
        transfer_id=transfer.id,
        requested_device_name=transfer.new_device_name,
        requested_at=transfer.created_at,
        expires_in=devices.seconds_left(transfer),
        approval_token=approval_token,
        submitted_code_hash=transfer.submitted_code_hash,
        submissions_left=max(
            0,
            settings.device_transfer_max_code_submissions - transfer.code_submissions,
        ),
    )
    response.headers["Cache-Control"] = "no-store"
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
    """Aprueba el dispositivo nuevo; los ya autorizados siguen activos."""
    current = await _current_device(request, db, current_user)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este dispositivo ya no está autorizado.",
        )
    try:
        transfer = await devices.approve_transfer(
            db,
            current_user,
            current,
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
        detail="Dispositivo autorizado. Los demás dispositivos siguen activos."
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
    current = await _current_device(request, db, current_user)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este dispositivo ya no está autorizado.",
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
