import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.auth import (
    AuthenticationMiddleware, Principal, current_user, require_docente, require_materia,
)
from app.config import Settings
from app.database import build_engine, get_db
from app.models import DocenteMateria, Inscripcion, Materia, Rol, Sesion, Usuario, utcnow
from app.schemas import LoginInput, MateriaOutput, TokenOutput, UsuarioOutput
from app.security import hash_password, hash_token, verify_password


def create_app(settings: Settings = None) -> FastAPI:
    settings = settings or Settings.from_env()
    # No se exponen rutas de documentación públicas por defecto.
    app = FastAPI(title="ClassFeedback", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.engine = build_engine(settings.database_url)
    app.state.session_factory = sessionmaker(app.state.engine, expire_on_commit=False)
    app.add_middleware(AuthenticationMiddleware)
    dummy_hash = hash_password(secrets.token_urlsafe(32))

    @app.post("/auth/login", response_model=TokenOutput)
    def login(body: LoginInput, response: Response, db: Session = Depends(get_db)):
        user = db.scalar(select(Usuario).where(Usuario.email == body.email.strip().lower()))
        valid = verify_password(body.password, user.password_hash if user else dummy_hash)
        if not valid or user is None:
            raise HTTPException(
                status_code=401, detail="Credenciales inválidas",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = secrets.token_urlsafe(32)
        db.add(Sesion(
            token_hash=hash_token(token), usuario_id=user.id,
            expira_en=utcnow() + timedelta(seconds=settings.session_ttl_seconds),
        ))
        db.commit()
        response.headers["Cache-Control"] = "no-store"
        return TokenOutput(access_token=token, expires_in=settings.session_ttl_seconds)

    @app.post("/auth/logout", status_code=204)
    def logout(request: Request, db: Session = Depends(get_db)):
        session = db.get(Sesion, request.state.token_hash)
        if session is not None:
            db.delete(session)
            db.commit()
        return Response(status_code=204)

    @app.get("/auth/me", response_model=UsuarioOutput)
    def me(user: Principal = Depends(current_user)):
        return user

    def own_materias(user: Principal, db: Session):
        association = DocenteMateria if user.rol == Rol.DOCENTE else Inscripcion
        user_column = association.docente_id if user.rol == Rol.DOCENTE else association.alumno_id
        return db.scalars(
            select(Materia).join(association, association.materia_id == Materia.id)
            .where(user_column == user.id).order_by(Materia.id)
        ).all()

    @app.get("/materias", response_model=list[MateriaOutput])
    def materias(user: Principal = Depends(current_user), db: Session = Depends(get_db)):
        return own_materias(user, db)

    @app.get("/materias/{materia_id}", response_model=MateriaOutput)
    def materia(materia: Materia = Depends(require_materia)):
        return materia

    docente = APIRouter(prefix="/docente", dependencies=[Depends(require_docente)])

    @docente.get("/materias", response_model=list[MateriaOutput])
    def docente_materias(user: Principal = Depends(current_user), db: Session = Depends(get_db)):
        return own_materias(user, db)

    @docente.get("/materias/{materia_id}", response_model=MateriaOutput)
    def docente_materia(materia: Materia = Depends(require_materia)):
        return materia

    app.include_router(docente)
    return app


app = create_app()
