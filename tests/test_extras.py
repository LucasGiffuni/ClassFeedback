import csv
import io
from datetime import date

import pytest

from app.extras.stopwords_es import STOPWORDS
from app.models import Clase, DocenteMateria, Materia
from datos_extras import agregar_feedbacks, crear_alumnos, email_alumno


DOCENTE = "docente@example.com"
CAMPOS_PROHIBIDOS = {"alumno_id", "email", "creado_en", "editado_en", "feedback_id", "nombre_alumno"}


def leer_csv(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"\xef\xbb\xbf")
    texto = response.content.decode("utf-8-sig")
    return texto, list(csv.reader(io.StringIO(texto)))


def claves(valor):
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            yield clave
            yield from claves(hijo)
    elif isinstance(valor, list):
        for hijo in valor:
            yield from claves(hijo)


def agregar_clase(app, clase_id, fecha, materia_id=1, tema=None):
    with app.state.session_factory() as db:
        db.add(Clase(id=clase_id, materia_id=materia_id, fecha=fecha, tema=tema))
        db.commit()


# --- Exportación CSV ---------------------------------------------------------

def test_csv_resumen_sin_ids_ni_emails_de_alumnos(app, client, login):
    ids = agregar_feedbacks(app, 1, [(5, "Muy clara"), (4, None, "Rápido"), 3])
    agregar_clase(app, 3, date(2026, 2, 1), tema="Recursión")
    ids += agregar_feedbacks(app, 3, [1, 2], primer_alumno=2001)
    docente = login(DOCENTE)

    texto, filas = leer_csv(client.get("/docente/materias/1/resumen.csv", headers=docente))
    assert filas == [
        ["clase", "fecha", "promedio", "cantidad"],
        ["Clase del 2026-01-01", "2026-01-01", "4.0", "3"],
        ["Recursión", "2026-02-01", "", "2"],
    ]
    comentarios, _ = leer_csv(client.get("/docente/materias/1/comentarios.csv", headers=docente))
    for contenido in (texto, comentarios):
        for alumno_id in ids:
            assert str(alumno_id) not in contenido
            assert email_alumno(alumno_id) not in contenido
        assert "@" not in contenido
        assert "alumno" not in contenido.lower()


def test_csv_comentarios_solo_sobre_el_umbral_y_alfabeticos(app, client, login):
    agregar_feedbacks(app, 1, [(5, "Zeta final"), (4, "Ejemplos claros", "Algo rápido"), 3])
    agregar_clase(app, 3, date(2026, 2, 1))
    agregar_feedbacks(app, 3, [(1, "Comentario oculto"), (2, "Otro oculto")], primer_alumno=2001)

    _, filas = leer_csv(client.get("/docente/materias/1/comentarios.csv", headers=login(DOCENTE)))
    assert filas == [
        ["clase", "fecha", "comentario"],
        ["Clase del 2026-01-01", "2026-01-01", "Algo rápido"],
        ["Clase del 2026-01-01", "2026-01-01", "Ejemplos claros"],
        ["Clase del 2026-01-01", "2026-01-01", "Zeta final"],
    ]


def test_csv_escapa_formulas(app, client, login):
    agregar_feedbacks(app, 1, [(5, '=HYPERLINK("http://x")'), (4, "+1"), (3, "@SUMA", "-2")])
    _, filas = leer_csv(client.get("/docente/materias/1/comentarios.csv", headers=login(DOCENTE)))
    assert sorted(f[2] for f in filas[1:]) == ["'+1", "'-2", "'=HYPERLINK(\"http://x\")", "'@SUMA"]


# --- Palabras frecuentes -----------------------------------------------------

def test_top_palabras_ignora_stopwords(app, client, login):
    agregar_feedbacks(app, 1, [
        (5, "El docente explicó que la recursión es clara", "De la teoría, nada"),
        (4, "Qué buena la recursión de hoy y los ejemplos", "Que el ritmo fue rápido"),
        (3, "Me gustó que hubo ejemplos de recursión", "A veces rápido"),
    ])
    body = client.get("/docente/materias/1/palabras", headers=login(DOCENTE)).json()
    palabras = [p["palabra"] for p in body]
    assert body[:3] == [
        {"palabra": "recursión", "cantidad": 3},
        {"palabra": "ejemplos", "cantidad": 2},
        {"palabra": "rápido", "cantidad": 2},
    ]
    for stopword in ("el", "de", "que", "qué", "la", "los", "me", "es", "fue", "hubo", "nada"):
        assert stopword not in palabras
    assert not [p for p in palabras if p in STOPWORDS or len(p) < 2]


def test_top_palabras_maximo_20_y_minimo_2_caracteres(app, client, login):
    # 25 palabras distintas de 5 letras (sin dígitos, que el tokenizador descarta).
    vocabulario = ["".join(chr(97 + (i + j) % 26) for j in range(5)) for i in range(25)]
    agregar_feedbacks(app, 1, [(5, " ".join(vocabulario) + " x y z"), 4, 3])
    body = client.get("/docente/materias/1/palabras", headers=login(DOCENTE)).json()
    assert len(body) == 20
    assert all(len(p["palabra"]) >= 2 for p in body)


def test_palabras_por_clase_y_umbral(app, client, login):
    agregar_feedbacks(app, 1, [(5, "Pizarrón"), (4, "Pizarrón"), (3, "Diapositivas")])
    agregar_clase(app, 3, date(2026, 2, 1))
    agregar_feedbacks(app, 3, [(1, "Secreto"), (2, "Secreto")], primer_alumno=2001)
    docente = login(DOCENTE)

    general = client.get("/docente/materias/1/palabras", headers=docente).json()
    assert general == [{"palabra": "pizarrón", "cantidad": 2}, {"palabra": "diapositivas", "cantidad": 1}]
    assert client.get("/docente/materias/1/palabras?clase_id=1", headers=docente).json() == general
    # Clase debajo del umbral: sin palabras.
    assert client.get("/docente/materias/1/palabras?clase_id=3", headers=docente).json() == []
    # Clase de otra materia o inexistente.
    assert client.get("/docente/materias/1/palabras?clase_id=2", headers=docente).status_code == 404
    assert client.get("/docente/materias/1/palabras?clase_id=999", headers=docente).status_code == 404


# --- Comparación entre materias ----------------------------------------------

@pytest.fixture
def segunda_materia(app):
    with app.state.session_factory() as db:
        db.add(Materia(id=3, nombre="Bases de datos", semestre="2026-1"))
        db.flush()
        db.add_all([
            DocenteMateria(docente_id=2, materia_id=3),
            Clase(id=5, materia_id=3, fecha=date(2026, 4, 1)),
        ])
        db.commit()


def test_comparacion_solo_materias_propias(app, client, login, segunda_materia):
    agregar_feedbacks(app, 2, [5, 5, 5])  # Materia 2: de la docente B.
    body = client.get("/docente/comparacion", headers=login(DOCENTE)).json()
    assert [m["materia_id"] for m in body] == [1, 3]
    otra = client.get("/docente/comparacion", headers=login("otro@example.com")).json()
    assert [m["materia_id"] for m in otra] == [2]


def test_comparacion_filtra_por_semestre(client, login, segunda_materia):
    docente = login(DOCENTE)
    body = client.get("/docente/comparacion?semestre=2026-1", headers=docente).json()
    assert [m["materia_id"] for m in body] == [3]
    assert client.get("/docente/comparacion?semestre=2030-1", headers=docente).json() == []


def test_comparacion_promedio_ponderado_y_umbral(app, client, login, segunda_materia):
    agregar_clase(app, 3, date(2026, 2, 1))
    agregar_clase(app, 4, date(2026, 3, 1))
    agregar_feedbacks(app, 1, [5, 5, 5])
    agregar_feedbacks(app, 3, [1, 1, 1, 1], primer_alumno=2001)
    # Debajo del umbral: no debe mover el promedio general.
    agregar_feedbacks(app, 4, [1, 1], primer_alumno=3001)
    agregar_feedbacks(app, 5, [4, 4, 5], primer_alumno=4001)

    body = client.get("/docente/comparacion", headers=login(DOCENTE)).json()
    assert body[0] == {
        "materia_id": 1, "nombre": "Programación", "semestre": "2026-2",
        # (5·3 + 1·4) / 7, no el promedio de promedios (3.0).
        "promedio_general": 2.71,
        "cantidad": 9,
        "tendencia": [
            {"clase_id": 1, "fecha": "2026-01-01", "promedio": 5.0, "cantidad": 3},
            {"clase_id": 3, "fecha": "2026-02-01", "promedio": 1.0, "cantidad": 4},
            {"clase_id": 4, "fecha": "2026-03-01", "promedio": None, "cantidad": 2},
        ],
    }
    assert body[1]["promedio_general"] == 4.33


def test_comparacion_sin_clases_sobre_el_umbral(app, client, login):
    agregar_feedbacks(app, 1, [5, 4])
    [materia] = client.get("/docente/comparacion", headers=login(DOCENTE)).json()
    assert materia["promedio_general"] is None
    assert materia["cantidad"] == 2


# --- Anonimato y acceso -------------------------------------------------------

def test_respuestas_json_sin_campos_identificatorios(app, client, login):
    agregar_feedbacks(app, 1, [(5, "Muy clara", "Rápido"), (4, "Ejemplos"), 3])
    docente = login(DOCENTE)
    for path in ("/docente/comparacion", "/docente/materias/1/palabras",
                 "/docente/materias/1/palabras?clase_id=1"):
        body = client.get(path, headers=docente).json()
        assert body
        assert not set(claves(body)) & CAMPOS_PROHIBIDOS


RUTAS_SPEC05 = [
    "/docente/comparacion",
    "/docente/materias/1/resumen.csv",
    "/docente/materias/1/comentarios.csv",
    "/docente/materias/1/palabras",
]


def test_alumno_recibe_403(client, login):
    alumno = login()
    for path in RUTAS_SPEC05:
        assert client.get(path, headers=alumno).status_code == 403


def test_materia_ajena_o_inexistente_404(client, login):
    docente = login(DOCENTE)
    for path in RUTAS_SPEC05[1:]:
        for materia_id in (2, 999):
            ruta = path.replace("/materias/1/", f"/materias/{materia_id}/")
            assert client.get(ruta, headers=docente).status_code == 404


# --- Integración con SPEC-03 ---------------------------------------------------

def test_feedback_creado_y_editado_por_la_api(app, client, login):
    ids = [1001, 1002, 1003]
    with app.state.session_factory() as db:
        crear_alumnos(db, ids, materia_id=1)
        db.commit()
    alumnos = {alumno_id: login(email_alumno(alumno_id)) for alumno_id in ids}
    creados = {}
    for alumno_id, (calificacion, gusto) in zip(ids, [(5, "Pizarrón ordenado"), (4, "Ejemplos"), (3, "")]):
        response = client.post("/clases/1/feedback", headers=alumnos[alumno_id],
                               json={"calificacion": calificacion, "gusto": gusto})
        assert response.status_code == 201
        creados[alumno_id] = response.json()["id"]

    docente = login(DOCENTE)
    [materia] = client.get("/docente/comparacion", headers=docente).json()
    assert (materia["promedio_general"], materia["cantidad"]) == (4.0, 3)
    _, filas = leer_csv(client.get("/docente/materias/1/comentarios.csv", headers=docente))
    assert [f[2] for f in filas[1:]] == ["Ejemplos", "Pizarrón ordenado"]

    # La edición (SPEC-03) reemplaza el texto: el anterior deja de aparecer.
    assert client.put(f"/feedback/{creados[1001]}", headers=alumnos[1001],
                      json={"calificacion": 2, "gusto": "Proyector borroso"}).status_code == 200
    palabras = [p["palabra"] for p in
                client.get("/docente/materias/1/palabras", headers=docente).json()]
    assert "pizarrón" not in palabras and "proyector" in palabras
    [materia] = client.get("/docente/comparacion", headers=docente).json()
    assert materia["promedio_general"] == 3.0
