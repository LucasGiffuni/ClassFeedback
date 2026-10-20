import enum
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Rol(str, enum.Enum):
    ALUMNO = "ALUMNO"
    DOCENTE = "DOCENTE"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    rol: Mapped[Rol] = mapped_column(
        Enum(Rol, native_enum=False, create_constraint=True, name="rol_usuario")
    )
    password_hash: Mapped[str] = mapped_column(String(256))


class Materia(Base):
    __tablename__ = "materias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    semestre: Mapped[str] = mapped_column(String(30))


class DocenteMateria(Base):
    __tablename__ = "docente_materia"

    docente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), primary_key=True)
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"), primary_key=True)


class Inscripcion(Base):
    __tablename__ = "inscripciones"

    alumno_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), primary_key=True)
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"), primary_key=True)


class Clase(Base):
    __tablename__ = "clases"

    id: Mapped[int] = mapped_column(primary_key=True)
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    tema: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class Feedback(Base):
    __tablename__ = "feedbacks"
    __table_args__ = (
        UniqueConstraint("clase_id", "alumno_id", name="uq_feedback_clase_alumno"),
        CheckConstraint("calificacion BETWEEN 1 AND 5", name="ck_feedback_calificacion"),
        CheckConstraint("gusto IS NULL OR length(gusto) <= 500", name="ck_feedback_gusto"),
        CheckConstraint("no_gusto IS NULL OR length(no_gusto) <= 500", name="ck_feedback_no_gusto"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    clase_id: Mapped[int] = mapped_column(ForeignKey("clases.id"))
    alumno_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    gusto: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    no_gusto: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    calificacion: Mapped[int]
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    editado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Sesion(Base):
    __tablename__ = "sesiones"

    # Solo se persiste el SHA-256 del token aleatorio, nunca el token utilizable.
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
