from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import ALGORITHM, SECRET_KEY

bearer_scheme = HTTPBearer(auto_error=False)


def _extract_role_key(payload: dict) -> str:
    role_value = payload.get("rol") or payload.get("rol_nombre") or ""
    normalized = str(role_value).strip().lower()

    mapping = {
        "administrador": "admin",
        "bodeguero": "bodeguero",
        "vendedor": "ventas",
        "admin": "admin",
        "ventas": "ventas",
    }
    return mapping.get(normalized, normalized)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload["rol"] = _extract_role_key(payload)
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_roles(*allowed_roles: str):
    normalized_roles = {role.strip().lower() for role in allowed_roles}

    def _checker(current_user: dict = Depends(get_current_user)):
        role = (current_user.get("rol") or "").strip().lower()

        if role not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para realizar esta acción",
            )

        return current_user

    return _checker
