from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.core.security import hash_password, verify_password
from app.database.database import get_db
from app.models import models

router = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])


class UsuarioCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    correo: EmailStr
    contrasena: str = Field(..., min_length=8, max_length=72)
    rol: str = Field(..., pattern="^(admin|bodeguero|ventas)$")


class UsuarioUpdate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    correo: EmailStr
    rol: str = Field(..., pattern="^(admin|bodeguero|ventas)$")


class CambioContrasena(BaseModel):
    actual: str = Field(..., min_length=1, max_length=100)
    nueva: str = Field(..., min_length=8, max_length=72)


class RestablecerContrasena(BaseModel):
    nueva: str = Field(..., min_length=8, max_length=72)


def serialize(user, db):
    role = db.query(models.Rol).filter(models.Rol.id_rol == user.id_rol).first()
    key = {"administrador": "admin", "vendedor": "ventas"}.get((role.nombre_rol if role else "").lower(), (role.nombre_rol if role else "").lower())
    return {"id_usuario": user.id_usuario, "nombre": user.nombre, "correo": user.correo, "rol": key, "rol_nombre": role.nombre_rol if role else "Desconocido"}


def role_id(db, key):
    role_name = {"admin": "Administrador", "bodeguero": "Bodeguero", "ventas": "Vendedor"}[key]
    role = db.query(models.Rol).filter(func.lower(models.Rol.nombre_rol) == role_name.lower()).first()
    if not role:
        raise HTTPException(500, "Falta configurar los roles base en la base de datos.")
    return role.id_rol


def ensure_bcrypt_password_size(password: str):
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(400, "La contraseña no puede superar 72 bytes UTF-8.")


@router.put("/me/contrasena")
def cambiar_contrasena(payload: CambioContrasena, db: Session = Depends(get_db), current=Depends(get_current_user)):
    ensure_bcrypt_password_size(payload.nueva)
    user = db.query(models.Usuario).filter(models.Usuario.id_usuario == int(current["sub"])).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado.")
    if not verify_password(payload.actual, user.contrasena):
        raise HTTPException(400, "La contraseña actual no es correcta.")
    if verify_password(payload.nueva, user.contrasena):
        raise HTTPException(400, "La nueva contraseña debe ser diferente a la actual.")
    user.contrasena = hash_password(payload.nueva)
    db.commit()
    return {"message": "Tu contraseña fue actualizada correctamente."}


@router.get("/", dependencies=[Depends(require_roles("admin"))])
def list_users(db: Session = Depends(get_db)):
    return [serialize(user, db) for user in db.query(models.Usuario).order_by(models.Usuario.nombre).all()]


@router.post("/", status_code=201, dependencies=[Depends(require_roles("admin"))])
def create_user(payload: UsuarioCreate, db: Session = Depends(get_db)):
    ensure_bcrypt_password_size(payload.contrasena)
    email = str(payload.correo).lower()
    if db.query(models.Usuario).filter(func.lower(models.Usuario.correo) == email).first():
        raise HTTPException(409, "Ya existe un usuario con ese correo.")
    user = models.Usuario(nombre=payload.nombre.strip(), correo=email, contrasena=hash_password(payload.contrasena), id_rol=role_id(db, payload.rol))
    db.add(user); db.commit(); db.refresh(user)
    return serialize(user, db)


@router.put("/{user_id}", dependencies=[Depends(require_roles("admin"))])
def update_user(user_id: int, payload: UsuarioUpdate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    user = db.query(models.Usuario).filter(models.Usuario.id_usuario == user_id).first()
    if not user: raise HTTPException(404, "Usuario no encontrado.")
    email = str(payload.correo).lower()
    duplicate = db.query(models.Usuario).filter(func.lower(models.Usuario.correo) == email, models.Usuario.id_usuario != user_id).first()
    if duplicate: raise HTTPException(409, "Ya existe un usuario con ese correo.")
    if str(current.get("sub")) == str(user_id) and payload.rol != "admin": raise HTTPException(400, "No puedes quitarte el rol de administrador a ti mismo.")
    user.nombre = payload.nombre.strip(); user.correo = email; user.id_rol = role_id(db, payload.rol)
    db.commit(); db.refresh(user)
    return serialize(user, db)


@router.put("/{user_id}/contrasena", dependencies=[Depends(require_roles("admin"))])
def restablecer_contrasena(user_id: int, payload: RestablecerContrasena, db: Session = Depends(get_db)):
    ensure_bcrypt_password_size(payload.nueva)
    user = db.query(models.Usuario).filter(models.Usuario.id_usuario == user_id).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado.")
    user.contrasena = hash_password(payload.nueva)
    db.commit()
    return {"message": "La contraseña del usuario fue restablecida."}


@router.delete("/{user_id}", status_code=204, dependencies=[Depends(require_roles("admin"))])
def delete_user(user_id: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    if str(current.get("sub")) == str(user_id): raise HTTPException(400, "No puedes eliminar tu propio usuario.")
    user = db.query(models.Usuario).filter(models.Usuario.id_usuario == user_id).first()
    if not user: raise HTTPException(404, "Usuario no encontrado.")
    db.delete(user); db.commit()
