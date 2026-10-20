from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import Rol


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UsuarioOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: str
    rol: Rol


class MateriaOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    semestre: str


class ClaseInput(BaseModel):
    fecha: date
    tema: Optional[str] = Field(default=None, max_length=500)


class ClaseOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    materia_id: int
    fecha: date
    tema: Optional[str]
    # Solo para alumnos: estado de SU feedback. Se omite para docentes.
    feedback: Optional[str] = None


class FeedbackInput(BaseModel):
    gusto: Optional[str] = Field(default=None, max_length=500)
    no_gusto: Optional[str] = Field(default=None, max_length=500)
    calificacion: int = Field(ge=1, le=5)


class FeedbackOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clase_id: int
    alumno_id: int
    gusto: Optional[str]
    no_gusto: Optional[str]
    calificacion: int
    creado_en: datetime
    editado_en: datetime


class ComentarioAnonimoOutput(BaseModel):
    gusto: Optional[str] = None
    no_gusto: Optional[str] = None


class ResultadoClaseOutput(BaseModel):
    clase_id: int
    fecha: date
    cantidad_respuestas: int
    promedio: Optional[float] = None
    distribucion: dict[int, int]
    comentarios: Optional[list[ComentarioAnonimoOutput]] = None


class PuntoTendenciaOutput(BaseModel):
    clase_id: int
    fecha: date
    cantidad_respuestas: int
    promedio: Optional[float] = None
