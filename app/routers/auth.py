from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.database.database import get_db
from app.models import models
from app.schemas.schemas import LoginRequest, LoginResponse, UsuarioLogin

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def normalize_role_name(nombre_rol: str) -> str:
    mapping = {
        "administrador": "admin",
        "bodeguero": "bodeguero",
        "vendedor": "ventas",
    }
    return mapping.get((nombre_rol or "").strip().lower(), (nombre_rol or "").strip().lower())


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    correo = payload.correo.strip().lower()
    contrasena = payload.contrasena

    usuario = (
        db.query(models.Usuario)
        .filter(func.lower(models.Usuario.correo) == correo)
        .first()
    )

    if not usuario or not verify_password(contrasena, usuario.contrasena):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    rol = db.query(models.Rol).filter(models.Rol.id_rol == usuario.id_rol).first()
    rol_nombre = rol.nombre_rol if rol else "Desconocido"
    rol_key = normalize_role_name(rol_nombre)

    token = create_access_token(
        subject=str(usuario.id_usuario),
        extra_data={
            "correo": usuario.correo,
            "rol": rol_key,
            "rol_nombre": rol_nombre,
        },
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UsuarioLogin(
            id_usuario=usuario.id_usuario,
            nombre=usuario.nombre,
            correo=usuario.correo,
            rol=rol_key,
            rol_nombre=rol_nombre,
        ),
    }
