"""Datos locales de ejemplo: python -m app.seed (requiere migraciones)."""
import os
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import build_engine
from app.models import Clase, DocenteMateria, Inscripcion, Materia, Rol, Usuario
from app.security import hash_password


def main() -> None:
    password = os.environ.get("SEED_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit("Definí SEED_PASSWORD con al menos 12 caracteres")
    engine = build_engine(Settings.from_env().database_url)
    with Session(engine) as db:
        if db.scalar(select(Usuario.id).limit(1)) is not None:
            raise SystemExit("El seed requiere una base sin usuarios")
        docente = Usuario(nombre="Docente demo", email="docente@example.com", rol=Rol.DOCENTE,
                          password_hash=hash_password(password))
        alumno = Usuario(nombre="Alumno demo", email="alumno@example.com", rol=Rol.ALUMNO,
                         password_hash=hash_password(password))
        materia = Materia(nombre="Programación", semestre="2026-2")
        db.add_all([docente, alumno, materia])
        db.flush()
        db.add_all([
            DocenteMateria(docente_id=docente.id, materia_id=materia.id),
            Inscripcion(alumno_id=alumno.id, materia_id=materia.id),
            Clase(materia_id=materia.id, fecha=date.today(), tema="Introducción"),
        ])
        db.commit()
    engine.dispose()
    print("Seed creado: docente@example.com y alumno@example.com")


if __name__ == "__main__":
    main()
