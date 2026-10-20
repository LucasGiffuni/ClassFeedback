"""Datos de prueba para SPEC-05: alumnos con IDs y emails distintivos."""
from app.models import Clase, Feedback, Inscripcion, Rol, Usuario
from app.security import hash_password


PRIMER_ALUMNO = 1001
# Un solo hash: PBKDF2 con 600.000 iteraciones es lento para recalcular por alumno.
PASSWORD_HASH = hash_password("clave-de-prueba")


def email_alumno(alumno_id: int) -> str:
    return f"alumno{alumno_id}@example.com"


def crear_alumnos(db, ids, materia_id: int) -> None:
    for alumno_id in ids:
        if db.get(Usuario, alumno_id) is None:
            db.add(Usuario(id=alumno_id, nombre=f"Alumno {alumno_id}", email=email_alumno(alumno_id),
                           rol=Rol.ALUMNO, password_hash=PASSWORD_HASH))
    db.flush()
    for alumno_id in ids:
        if db.get(Inscripcion, (alumno_id, materia_id)) is None:
            db.add(Inscripcion(alumno_id=alumno_id, materia_id=materia_id))
    db.flush()


def agregar_feedbacks(app, clase_id: int, feedbacks, primer_alumno: int = PRIMER_ALUMNO) -> list[int]:
    """Inserta un feedback por alumno. Cada item es una calificación o una tupla
    (calificacion, gusto, no_gusto). Devuelve los IDs de alumno usados."""
    with app.state.session_factory() as db:
        materia_id = db.get(Clase, clase_id).materia_id
        ids = list(range(primer_alumno, primer_alumno + len(feedbacks)))
        crear_alumnos(db, ids, materia_id)
        for alumno_id, item in zip(ids, feedbacks):
            item = item if isinstance(item, tuple) else (item,)
            calificacion, gusto, no_gusto = item + (None,) * (3 - len(item))
            db.add(Feedback(clase_id=clase_id, alumno_id=alumno_id, calificacion=calificacion,
                            gusto=gusto, no_gusto=no_gusto))
        db.commit()
    return ids
