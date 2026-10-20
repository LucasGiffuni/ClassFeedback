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
