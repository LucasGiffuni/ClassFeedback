from datetime import date, timedelta

from app.models import Clase, Feedback, Inscripcion, Materia


def test_alumno_ve_solo_sus_materias(app, client, login):
    with app.state.session_factory() as db:
        db.add(Inscripcion(alumno_id=1, materia_id=2))
        db.add(Materia(id=3, nombre="Física", semestre="2026-2"))
        db.commit()
    ids = [m["id"] for m in client.get("/materias", headers=login()).json()]
    assert ids == [1, 2]


def test_clases_desc_con_estado_por_alumno(app, client, login):
    with app.state.session_factory() as db:
        db.add_all([
            Clase(id=3, materia_id=1, fecha=date(2026, 3, 1)),
            Clase(id=4, materia_id=1, fecha=date(2026, 2, 1)),
            Feedback(clase_id=3, alumno_id=1, calificacion=4),
        ])
        db.commit()
    body = client.get("/materias/1/clases", headers=login()).json()
    assert [(c["id"], c["feedback"]) for c in body] == [(3, "enviado"), (4, "pendiente"), (1, "pendiente")]
    # El docente ve las mismas clases, sin estado de feedback.
    docente = client.get("/materias/1/clases", headers=login("docente@example.com")).json()
    assert [c["id"] for c in docente] == [3, 4, 1]
    assert all("feedback" not in c for c in docente)


def test_clases_materia_ajena_404(client, login):
    assert client.get("/materias/2/clases", headers=login()).status_code == 404
    assert client.get("/materias/1/clases", headers=login("otro@example.com")).status_code == 404


def test_crear_clase(client, login):
    docente, path = login("docente@example.com"), "/docente/materias/1/clases"
    ok = client.post(path, json={"fecha": date.today().isoformat(), "tema": "Hoy"}, headers=docente)
    assert ok.status_code == 201 and ok.json()["tema"] == "Hoy"
    futura = (date.today() + timedelta(days=1)).isoformat()
    assert client.post(path, json={"fecha": futura}, headers=docente).status_code == 422
    assert client.post(path, json={"fecha": "2026-01-01"}, headers=login()).status_code == 403
    assert client.post("/docente/materias/2/clases", json={"fecha": "2026-01-01"}, headers=docente).status_code == 404
