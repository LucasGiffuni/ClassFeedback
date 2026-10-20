from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Clase, DocenteMateria, Inscripcion, Materia, Rol, Usuario
from app.security import hash_password


@pytest.fixture
def app(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    app = create_app(Settings(database_url=url))
    password_hash = hash_password("clave-de-prueba")
    with app.state.session_factory() as db:
        db.add_all([
            Usuario(id=1, nombre="Alumno", email="alumno@example.com", rol=Rol.ALUMNO, password_hash=password_hash),
            Usuario(id=2, nombre="Docente A", email="docente@example.com", rol=Rol.DOCENTE, password_hash=password_hash),
            Usuario(id=3, nombre="Docente B", email="otro@example.com", rol=Rol.DOCENTE, password_hash=password_hash),
            Materia(id=1, nombre="Programación", semestre="2026-2"),
            Materia(id=2, nombre="Álgebra", semestre="2026-2"),
        ])
        db.flush()
        db.add_all([
            DocenteMateria(docente_id=2, materia_id=1),
            DocenteMateria(docente_id=3, materia_id=2),
            Inscripcion(alumno_id=1, materia_id=1),
            Clase(id=1, materia_id=1, fecha=date(2026, 1, 1)),
            Clase(id=2, materia_id=2, fecha=date(2026, 1, 1)),
        ])
        db.commit()
    yield app
    app.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def login(client):
    def authenticate(email="alumno@example.com"):
        response = client.post("/auth/login", json={"email": email, "password": "clave-de-prueba"})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    return authenticate
