import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models import Feedback


def test_unique_feedback_is_enforced_by_database(app):
    with app.state.session_factory() as db:
        db.add(Feedback(clase_id=1, alumno_id=1, calificacion=5))
        db.commit()
        db.add(Feedback(clase_id=1, alumno_id=1, calificacion=4))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        # El mismo alumno puede responder otra clase.
        db.add(Feedback(clase_id=2, alumno_id=1, calificacion=3))
        db.commit()


@pytest.mark.parametrize("values", [
    {"calificacion": 0}, {"calificacion": 6},
    {"calificacion": 3, "gusto": "a" * 501},
    {"calificacion": 3, "no_gusto": "a" * 501},
    {"calificacion": 3, "clase_id": 999},
    {"calificacion": 3, "alumno_id": 999},
])
def test_feedback_constraints(app, values):
    with app.state.session_factory() as db:
        db.add(Feedback(**({"clase_id": 1, "alumno_id": 1} | values)))
        with pytest.raises(IntegrityError):
            db.commit()


def test_migration_matches_models(app):
    command.check(Config("alembic.ini"))


def test_migration_can_be_reversed_and_reapplied(app):
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    assert set(inspect(app.state.engine).get_table_names()) == {"alembic_version"}
    command.upgrade(config, "head")
    assert "feedbacks" in inspect(app.state.engine).get_table_names()
