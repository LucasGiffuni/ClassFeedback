import secrets
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.auth import (
    AuthenticationMiddleware, Principal, current_user, require_alumno,
    require_docente, require_feedback_clase, require_materia,
)
from app.config import Settings
from app.database import build_engine, get_db
from app.extras import reportes
from app.models import Clase, DocenteMateria, Feedback, Inscripcion, Materia, Rol, Sesion, Usuario, utcnow
from app.schemas import (
    ClaseInput, ClaseOutput, FeedbackInput, FeedbackOutput,
    LoginInput, MateriaOutput, TokenOutput, UsuarioOutput,
    ComentarioAnonimoOutput, ResultadoClaseOutput,
    PuntoTendenciaOutput,
)
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

    @app.get("/materias/{materia_id}/clases", response_model=list[ClaseOutput],
             response_model_exclude_none=True)
    def clases(
        materia: Materia = Depends(require_materia),
        user: Principal = Depends(current_user),
        db: Session = Depends(get_db),
    ):
        query = select(Clase).where(Clase.materia_id == materia.id)
        query = query.order_by(Clase.fecha.desc(), Clase.id.desc())
        if user.rol == Rol.DOCENTE:
            return db.scalars(query).all()
        sent = set(db.scalars(
            select(Feedback.clase_id).where(Feedback.alumno_id == user.id)
        ))
        return [
            ClaseOutput.model_validate(c).model_copy(
                update={"feedback": "enviado" if c.id in sent else "pendiente"})
            for c in db.scalars(query)
        ]

    docente = APIRouter(prefix="/docente", dependencies=[Depends(require_docente)])

    @docente.get("/materias", response_model=list[MateriaOutput])
    def docente_materias(user: Principal = Depends(current_user), db: Session = Depends(get_db)):
        return own_materias(user, db)

    @docente.get("/materias/{materia_id}", response_model=MateriaOutput)
    def docente_materia(materia: Materia = Depends(require_materia)):
        return materia

    @docente.post("/materias/{materia_id}/clases", response_model=ClaseOutput,
                  response_model_exclude_none=True, status_code=201)
    def crear_clase(
        body: ClaseInput,
        materia: Materia = Depends(require_materia),
        db: Session = Depends(get_db),
    ):
        # La clase debe haber ocurrido para admitir feedback.
        if body.fecha > utcnow().date():
            raise HTTPException(status_code=422, detail="La fecha de la clase no puede ser futura")
        clase = Clase(materia_id=materia.id, fecha=body.fecha, tema=body.tema)
        db.add(clase)
        db.commit()
        return clase

    
    @docente.get(
        "/materias/{materia_id}/clases/{clase_id}/resultados",
        response_model=ResultadoClaseOutput,
        response_model_exclude_none=True,
    )
    def resultados_clase(
        clase_id: int,
        materia: Materia = Depends(require_materia),
        db: Session = Depends(get_db),
    ):
        # Comprobar que la clase pertenece a la materia solicitada.
        clase = db.scalar(
            select(Clase).where(
                Clase.id == clase_id,
                Clase.materia_id == materia.id,
            )
        )
        if clase is None:
            raise HTTPException(
                status_code=404,
                detail="Clase no encontrada",
            )

        # Obtener solamente los datos necesarios para el agregado.
        filas = db.execute(
            select(
                Feedback.gusto,
                Feedback.no_gusto,
                Feedback.calificacion,
            ).where(Feedback.clase_id == clase.id)
        ).all()

        cantidad = len(filas)

        # La distribución siempre se muestra, de 1 a 5.
        distribucion = {
            nota: sum(1 for fila in filas if fila.calificacion == nota)
            for nota in range(1, 6)
        }

        # No exponer promedio ni comentarios con menos de 3 respuestas.
        if cantidad < 3:
            return ResultadoClaseOutput(
                clase_id=clase.id,
                fecha=clase.fecha,
                cantidad_respuestas=cantidad,
                distribucion=distribucion,
                promedio=None,
                comentarios=None,
            )

        # Preparar comentarios sin autor ni marcas de tiempo.
        comentarios = [
            ComentarioAnonimoOutput(
                gusto=fila.gusto,
                no_gusto=fila.no_gusto,
            )
            for fila in filas
            if fila.gusto or fila.no_gusto
        ]

        # Orden alfabético para evitar revelar el orden cronológico.
        comentarios.sort(
            key=lambda c: (
                (c.gusto or "").casefold(),
                (c.no_gusto or "").casefold(),
            )
        )

        promedio = round(
            sum(fila.calificacion for fila in filas) / cantidad,
            2,
        )

        return ResultadoClaseOutput(
            clase_id=clase.id,
            fecha=clase.fecha,
            cantidad_respuestas=cantidad,
            promedio=promedio,
            distribucion=distribucion,
            comentarios=comentarios,
        )

    
    @docente.get(
        "/materias/{materia_id}/tendencia",
        response_model=list[PuntoTendenciaOutput],
        response_model_exclude_none=True,
    )
    def tendencia_materia(
        materia: Materia = Depends(require_materia),
        db: Session = Depends(get_db),
    ):
        # Consultar todas las clases de la materia y agregar sus feedbacks.
        filas = db.execute(
            select(
                Clase.id,
                Clase.fecha,
                func.count(Feedback.id).label("cantidad"),
                func.avg(Feedback.calificacion).label("promedio"),
            )
            .outerjoin(Feedback, Feedback.clase_id == Clase.id)
            .where(Clase.materia_id == materia.id)
            .group_by(Clase.id, Clase.fecha)
            .order_by(Clase.fecha.asc(), Clase.id.asc())
        ).all()

        resultado = []

        for fila in filas:
            cantidad = fila.cantidad

            # Aplicar el mismo umbral de anonimato que en los resultados.
            promedio = (
                round(float(fila.promedio), 2)
                if cantidad >= 3
                else None
            )

            resultado.append(
                PuntoTendenciaOutput(
                    clase_id=fila.id,
                    fecha=fila.fecha,
                    cantidad_respuestas=cantidad,
                    promedio=promedio,
                )
            )

        return resultado

    @app.post("/clases/{clase_id}/feedback", response_model=FeedbackOutput, status_code=201)
    def crear_feedback(
        body: FeedbackInput,
        clase: Clase = Depends(require_feedback_clase),
        user: Principal = Depends(require_alumno),
        db: Session = Depends(get_db),
    ):
        if clase.fecha > utcnow().date():
            raise HTTPException(status_code=422, detail="La clase todavía no ocurrió")
        if db.scalar(select(Feedback).where(
            Feedback.clase_id == clase.id, Feedback.alumno_id == user.id
        )) is not None:
            raise HTTPException(status_code=409, detail="Ya existe feedback para esta clase")
        feedback = Feedback(clase_id=clase.id, alumno_id=user.id, **body.model_dump())
        db.add(feedback)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Ya existe feedback para esta clase")
        db.refresh(feedback)
        return feedback

    @app.get("/clases/{clase_id}/feedback", response_model=FeedbackOutput)
    def ver_feedback(
        clase: Clase = Depends(require_feedback_clase),
        user: Principal = Depends(require_alumno),
        db: Session = Depends(get_db),
    ):
        feedback = db.scalar(select(Feedback).where(
            Feedback.clase_id == clase.id, Feedback.alumno_id == user.id
        ))
        if feedback is None:
            raise HTTPException(status_code=404, detail="Feedback no encontrado")
        return feedback

    @app.put("/feedback/{feedback_id}", response_model=FeedbackOutput)
    def editar_feedback(
        body: FeedbackInput,
        feedback_id: int,
        user: Principal = Depends(require_alumno),
        db: Session = Depends(get_db),
    ):
        feedback = db.get(Feedback, feedback_id)
        if feedback is None or feedback.alumno_id != user.id:
            raise HTTPException(status_code=404, detail="Feedback no encontrado")
        creado_en = feedback.creado_en
        if creado_en.tzinfo is None:
            creado_en = creado_en.replace(tzinfo=timezone.utc)
        if utcnow() - creado_en > timedelta(hours=48):
            raise HTTPException(
                status_code=403,
                detail="El plazo para editar el feedback (48 horas) ya expiró",
            )
        for field, value in body.model_dump().items():
            setattr(feedback, field, value)
        db.commit()
        db.refresh(feedback)
        return feedback

    app.include_router(docente)
    app.include_router(reportes.router)
    return app


app = create_app()
