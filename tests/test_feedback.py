from datetime import date, timedelta

from app.models import Clase, Feedback, utcnow


def test_alumno_crea_y_consulta_su_feedback(client, login):
    headers = login()
    response = client.post(
        "/clases/1/feedback",
        json={"gusto": "La explicación fue clara", "calificacion": 5},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["alumno_id"] == 1
    assert client.get("/clases/1/feedback", headers=headers).json()["calificacion"] == 5
    assert client.post(
        "/clases/1/feedback", json={"calificacion": 4}, headers=headers
    ).status_code == 409


def test_feedback_valida_calificacion_y_textos(client, login):
    headers = login()
    for value in (0, 6):
        assert client.post(
            "/clases/1/feedback", json={"calificacion": value}, headers=headers
        ).status_code == 422
    assert client.post(
        "/clases/1/feedback",
        json={"calificacion": 4, "gusto": "x" * 501},
        headers=headers,
    ).status_code == 422


def test_alumno_no_inscripto_no_puede_dejar_feedback(client, login):
    assert client.post(
        "/clases/2/feedback", json={"calificacion": 4}, headers=login()
    ).status_code == 403
    assert client.post(
        "/clases/1/feedback", json={"calificacion": 4}, headers=login("docente@example.com")
    ).status_code == 403


def test_clase_futura_no_admite_feedback(app, client, login):
    with app.state.session_factory() as db:
        db.add(Clase(id=10, materia_id=1, fecha=date.today() + timedelta(days=1)))
        db.commit()
    assert client.post(
        "/clases/10/feedback", json={"calificacion": 4}, headers=login()
    ).status_code == 422


def test_edicion_feedback_hasta_48_horas(client, app, login):
    headers = login()
    created = client.post(
        "/clases/1/feedback", json={"calificacion": 3}, headers=headers
    )
    feedback_id = created.json()["id"]
    with app.state.session_factory() as db:
        feedback = db.get(Feedback, feedback_id)
        feedback.creado_en = utcnow() - timedelta(hours=47)
        db.commit()
    assert client.put(
        f"/feedback/{feedback_id}", json={"calificacion": 5}, headers=headers
    ).status_code == 200
    with app.state.session_factory() as db:
        db.get(Feedback, feedback_id).creado_en = utcnow() - timedelta(hours=49)
        db.commit()
    response = client.put(
        f"/feedback/{feedback_id}", json={"calificacion": 1}, headers=headers
    )
    assert response.status_code == 403
    assert "48 horas" in response.json()["detail"]
