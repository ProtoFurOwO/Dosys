from fastapi import APIRouter

from app.api.routes import auth, doctor, patients


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(doctor.router)
