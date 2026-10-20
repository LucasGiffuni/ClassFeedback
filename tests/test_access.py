from datetime import timedelta

import pytest
from fastapi import Depends
from sqlalchemy import select

from app.auth import require_alumno, require_clase
from app.models import Clase, Inscripcion, Rol, Sesion, Usuario, utcnow
from app.security import hash_token


@pytest.mark.parametrize("method,path", [
    ("GET", "/auth/me"), ("POST", "/auth/logout"), ("GET", "/materias"),
    ("GET", "/materias/1"), ("GET", "/docente/materias"),
    ("GET", "/docente/materias/1"), ("GET", "/materias/no-es-un-id"),
    ("GET", "/ruta-inexistente"), ("GET", "/docs"), ("GET", "/openapi.json"),
    ("GET", "/docente/comparacion"), ("GET", "/docente/materias/1/resumen.csv"),
    ("GET", "/docente/materias/1/comentarios.csv"), ("GET", "/docente/materias/1/palabras"),
])
def test_no_session_is_always_401(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_alumno_cannot_access_docente_routes(client, login):
    headers = login()
    for path in ("/docente/materias", "/docente/materias/1", "/docente/materias/2"):
        assert client.get(path, headers=headers).status_code == 403


def test_docente_membership(client, login):
    headers = login("docente@example.com")
    assert client.get("/docente/materias/1", headers=headers).status_code == 200
    for prefix in ("/materias", "/docente/materias"):
        assert client.get(f"{prefix}/2", headers=headers).status_code == 404
        assert client.get(f"{prefix}/999", headers=headers).status_code == 404
        assert [m["id"] for m in client.get(prefix, headers=headers).json()] == [1]


def test_alumno_membership_is_rechecked(app, client, login):
    headers = login()
    assert client.get("/materias/1", headers=headers).status_code == 200
    assert client.get("/materias/2", headers=headers).status_code == 404
    with app.state.session_factory() as db:
        db.delete(db.get(Inscripcion, (1, 1)))
        db.commit()
    assert client.get("/materias/1", headers=headers).status_code == 404


def test_role_is_read_on_every_request(app, client, login):
    headers = login("docente@example.com")
    assert client.get("/docente/materias", headers=headers).status_code == 200
    with app.state.session_factory() as db:
        db.get(Usuario, 2).rol = Rol.ALUMNO
        db.commit()
    assert client.get("/docente/materias", headers=headers).status_code == 403


def test_login_me_logout_and_token_storage(app, client, login):
    headers = login()
    response = client.get("/auth/me", headers=headers)
    assert response.json() == {"id": 1, "nombre": "Alumno", "email": "alumno@example.com", "rol": "ALUMNO"}
    token = headers["Authorization"].split()[1]
    with app.state.session_factory() as db:
        stored = db.scalar(select(Sesion))
        assert stored.token_hash == hash_token(token)
        assert stored.token_hash != token
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_expired_session(app, client, login):
    headers = login()
    with app.state.session_factory() as db:
        db.scalar(select(Sesion)).expira_en = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401


@pytest.mark.parametrize("authorization", ["Bearer inventado", "Basic abc", "Bearer", ""])
def test_invalid_token(client, authorization):
    assert client.get("/auth/me", headers={"Authorization": authorization}).status_code == 401


@pytest.mark.parametrize("email,password", [
    ("alumno@example.com", "incorrecta"), ("nadie@example.com", "clave-de-prueba"),
])
def test_invalid_credentials(client, email, password):
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "Credenciales inválidas"}


def test_reusable_class_and_role_guards(app, client, login):
    @app.get("/test/alumno/clases/{clase_id}", dependencies=[Depends(require_alumno)])
    def clase(clase: Clase = Depends(require_clase)):
        return {"id": clase.id}

    alumno = login()
    assert client.get("/test/alumno/clases/1", headers=alumno).status_code == 200
    assert client.get("/test/alumno/clases/2", headers=alumno).status_code == 404
    assert client.get("/test/alumno/clases/999", headers=alumno).status_code == 404
    docente = login("docente@example.com")
    assert client.get("/test/alumno/clases/1", headers=docente).status_code == 403
