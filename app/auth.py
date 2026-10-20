from dataclasses import dataclass
from datetime import timezone
from typing import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.database import get_db
from app.models import Clase, DocenteMateria, Inscripcion, Materia, Rol, Sesion, Usuario, utcnow
from app.security import hash_token


@dataclass(frozen=True)
class Principal:
    id: int
    nombre: str
    email: str
    rol: Rol


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Excepción indispensable para iniciar una sesión; el resto es privado,
        # incluidas rutas desconocidas y errores de validación de parámetros.
        if request.method == "POST" and request.url.path == "/auth/login":
            return await call_next(request)

        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token or len(token) > 512:
            return self.unauthorized()

        with request.app.state.session_factory() as db:
            session = db.get(Sesion, hash_token(token))
            if session is None or session.expira_en.replace(tzinfo=timezone.utc) <= utcnow():
                return self.unauthorized()
            # El rol se obtiene de la base en CADA request, no de claims del cliente.
            user = db.get(Usuario, session.usuario_id)
            if user is None:
                return self.unauthorized()
            request.state.principal = Principal(user.id, user.nombre, user.email, user.rol)
            request.state.token_hash = session.token_hash
        return await call_next(request)

    @staticmethod
    def unauthorized() -> JSONResponse:
        return JSONResponse(
            {"detail": "Se requiere una sesión válida"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )


def current_user(request: Request) -> Principal:
    return request.state.principal


def require_role(*roles: Rol) -> Callable:
    def guard(user: Principal = Depends(current_user)) -> Principal:
        if user.rol not in roles:
            raise HTTPException(status_code=403, detail="Rol no autorizado")
        return user
    return guard


require_docente = require_role(Rol.DOCENTE)
require_alumno = require_role(Rol.ALUMNO)


def authorize_materia(db: Session, user: Principal, materia_id: int) -> Materia:
    association = DocenteMateria if user.rol == Rol.DOCENTE else Inscripcion
    user_column = association.docente_id if user.rol == Rol.DOCENTE else association.alumno_id
    materia = db.scalar(
        select(Materia)
        .join(association, association.materia_id == Materia.id)
        .where(Materia.id == materia_id, user_column == user.id)
    )
    if materia is None:
        # Misma respuesta para inexistencia y falta de pertenencia.
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return materia


def require_materia(
    materia_id: int,
    user: Principal = Depends(current_user),
    db: Session = Depends(get_db),
) -> Materia:
    return authorize_materia(db, user, materia_id)


def require_clase(
    clase_id: int,
    user: Principal = Depends(current_user),
    db: Session = Depends(get_db),
) -> Clase:
    clase = db.get(Clase, clase_id)
    if clase is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    authorize_materia(db, user, clase.materia_id)
    return clase
