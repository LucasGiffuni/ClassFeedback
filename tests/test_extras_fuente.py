"""Contrato de app.extras.fuente, la fuente de datos agregados de SPEC-05."""
from dataclasses import fields
from datetime import date

import pytest

from app.extras.fuente import ClaseAgregada, agregados_materia, umbral
from app.models import Clase
from datos_extras import agregar_feedbacks


def agregados(app, materia_id=1):
    with app.state.session_factory() as db:
        return agregados_materia(db, materia_id)


def test_umbral_es_3():
    assert umbral() == 3


def test_debajo_del_umbral_solo_cantidad(app):
    agregar_feedbacks(app, 1, [(5, "Muy clara"), (4, "Buenos ejemplos")])
    [clase] = agregados(app)
    assert (clase.cantidad, clase.promedio, clase.comentarios) == (2, None, ())


def test_desde_el_umbral_promedio_y_comentarios(app):
    agregar_feedbacks(app, 1, [(5, "Muy clara"), (4, "Buenos ejemplos", "Rápido"), 3])
    [clase] = agregados(app)
    assert clase.cantidad == 3
    assert clase.promedio == pytest.approx(4.0)
    assert set(clase.comentarios) == {"Muy clara", "Buenos ejemplos", "Rápido"}


def test_textos_vacios_se_descartan(app):
    agregar_feedbacks(app, 1, [(5, "", "   "), (4, None, None), (3, "  Útil  ", "")])
    [clase] = agregados(app)
    assert clase.comentarios == ("Útil",)


def test_contrato_sin_datos_de_autor():
    nombres = {f.name for f in fields(ClaseAgregada)}
    assert not nombres & {"alumno_id", "email", "creado_en", "editado_en", "feedback_id"}


def test_orden_por_fecha_e_incluye_clases_sin_feedback(app):
    with app.state.session_factory() as db:
        db.add_all([
            Clase(id=3, materia_id=1, fecha=date(2026, 3, 1)),
            Clase(id=4, materia_id=1, fecha=date(2025, 12, 1)),
        ])
        db.commit()
    clases = agregados(app)
    assert [c.clase_id for c in clases] == [4, 1, 3]
    assert all(c.cantidad == 0 and c.promedio is None for c in clases)


def test_solo_clases_de_la_materia(app):
    agregar_feedbacks(app, 2, [5, 5, 5])
    assert [c.clase_id for c in agregados(app, 1)] == [1]
    assert [c.clase_id for c in agregados(app, 2)] == [2]
