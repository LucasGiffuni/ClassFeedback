
from datetime import date

from app.models import (
    Clase,
    Feedback,
    Inscripcion,
    Rol,
    Usuario,
)
from app.security import hash_password



def preparar_feedbacks(app, cantidad):
    with app.state.session_factory() as db:
        password_hash = hash_password("clave-de-prueba")

        alumnos = [
            Usuario(
                id=i,
                nombre=f"Alumno {i}",
                email=f"alumno{i}@example.com",
                rol=Rol.ALUMNO,
                password_hash=password_hash,
            )
            for i in range(4, 4 + cantidad)
        ]

        db.add_all(alumnos)

        db.flush()

        inscripciones = [
            Inscripcion(alumno_id=i, materia_id=1)
            for i in range(4, 4 + cantidad)
        ]

        db.add_all(inscripciones)
        db.flush()

        notas = [3, 4, 5, 2, 4, 5]

        feedbacks = [
            Feedback(
                clase_id=1,
                alumno_id=4 + i,
                calificacion=notas[i % len(notas)],
                gusto=f"Comentario positivo {i}",
                no_gusto=f"Comentario de mejora {i}",
            )
            for i in range(cantidad)
        ]

        db.add_all(feedbacks)
        db.commit()


def test_resultados_con_dos_feedbacks_ocultan_promedio_y_comentarios(
    app, client, login
):
    preparar_feedbacks(app, 2)

    response = client.get(
        "/docente/materias/1/clases/1/resultados",
        headers=login("docente@example.com"),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["cantidad_respuestas"] == 2
    assert "promedio" not in data
    assert "comentarios" not in data


def test_resultados_con_tres_feedbacks_muestran_agregados(
    app, client, login
):
    preparar_feedbacks(app, 3)

    response = client.get(
        "/docente/materias/1/clases/1/resultados",
        headers=login("docente@example.com"),
    )

    assert response.status_code == 200
    data = response.json()

    assert data["cantidad_respuestas"] == 3
    assert data["promedio"] == 4.0
    assert len(data["comentarios"]) == 3
    assert set(data["distribucion"].keys()) == {
        "1", "2", "3", "4", "5"
    }

    # Ningún campo de respuesta debe identificar a un alumno.
    assert "alumno_id" not in data
    assert "email" not in data
    assert "creado_en" not in data
    for comentario in data["comentarios"]:
        assert set(comentario.keys()) == {"gusto", "no_gusto"}


def test_docente_no_puede_consultar_materia_ajena(client, login):
    headers = login("docente@example.com")

    response = client.get(
        "/docente/materias/2/clases/2/resultados",
        headers=headers,
    )
    assert response.status_code == 404

    response = client.get(
        "/docente/materias/2/tendencia",
        headers=headers,
    )
    assert response.status_code == 404



def test_tendencia_ordenada_por_fecha(app, client, login):
    preparar_feedbacks(app, 3)

    with app.state.session_factory() as db:
        # Crear una segunda clase de la misma materia, con fecha posterior.
        db.add(
            Clase(
                id=3,
                materia_id=1,
                fecha=date(2026, 1, 2),
                tema="Segunda clase",
            )
        )
        db.flush()

        # Los mismos alumnos dejan feedback en la segunda clase.
        for alumno_id, nota in zip((4, 5, 6), (4, 4, 5)):
            db.add(
                Feedback(
                    clase_id=3,
                    alumno_id=alumno_id,
                    calificacion=nota,
                    gusto="Comentario de prueba",
                )
            )

        db.commit()

    response = client.get(
        "/docente/materias/1/tendencia",
        headers=login("docente@example.com"),
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert [p["clase_id"] for p in data] == [1, 3]
    assert [p["fecha"] for p in data] == [
        "2026-01-01",
        "2026-01-02",
    ]
    assert data[0]["promedio"] == 4.0
    assert data[1]["promedio"] == 4.33

def test_alumno_no_puede_acceder_a_resultados(client, login):
    response = client.get(
        "/docente/materias/1/clases/1/resultados",
        headers=login("alumno@example.com"),
    )
    assert response.status_code == 403
