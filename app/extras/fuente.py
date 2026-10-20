"""Única fuente de datos agregados de SPEC-05.

El resto del paquete solo consume `umbral()` y `agregados_materia()`. Cuando
SPEC-04 esté disponible, solo cambia el cuerpo de este módulo para delegar en
su agregación; el contrato (`ClaseAgregada`) se mantiene.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Clase, Feedback


# TEMPORAL (SPEC-04): reemplazar por la constante de umbral de SPEC-04.
UMBRAL = 3


@dataclass(frozen=True)
class ClaseAgregada:
    clase_id: int
    fecha: date
    tema: Optional[str]
    # Siempre presente, aun por debajo del umbral.
    cantidad: int
    # None si cantidad < umbral. Sin redondear: se redondea al responder.
    promedio: Optional[float]
    # Vacío si cantidad < umbral. Solo texto, sin ningún dato del autor; el
    # orden no forma parte del contrato.
    comentarios: tuple[str, ...]


def umbral() -> int:
    return UMBRAL


def agregados_materia(db: Session, materia_id: int) -> list[ClaseAgregada]:
    """Clases de la materia ordenadas por fecha ascendente, con el umbral aplicado."""
    # TEMPORAL (SPEC-04): consulta propia hasta que exista la agregación de SPEC-04.
    filas = db.execute(
        select(
            Clase.id, Clase.fecha, Clase.tema,
            func.count(Feedback.id).label("cantidad"),
            func.avg(Feedback.calificacion).label("promedio"),
        )
        .outerjoin(Feedback, Feedback.clase_id == Clase.id)
        .where(Clase.materia_id == materia_id)
        .group_by(Clase.id, Clase.fecha, Clase.tema)
        .order_by(Clase.fecha, Clase.id)
    ).all()

    visibles = {fila.id for fila in filas if fila.cantidad >= UMBRAL}
    textos = defaultdict(list)
    if visibles:
        # Solo se seleccionan los textos: nunca alumno_id ni timestamps.
        for clase_id, gusto, no_gusto in db.execute(
            select(Feedback.clase_id, Feedback.gusto, Feedback.no_gusto)
            .where(Feedback.clase_id.in_(visibles))
        ):
            for texto in (gusto, no_gusto):
                if texto and texto.strip():
                    textos[clase_id].append(texto.strip())

    return [
        ClaseAgregada(
            clase_id=fila.id,
            fecha=fila.fecha,
            tema=fila.tema,
            cantidad=fila.cantidad,
            promedio=float(fila.promedio) if fila.id in visibles else None,
            # Orden alfabético para no revelar el orden de creación.
            comentarios=tuple(sorted(textos[fila.id])) if fila.id in visibles else (),
        )
        for fila in filas
    ]
