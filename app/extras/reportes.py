import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, current_user, require_docente, require_materia
from app.database import get_db
from app.extras.fuente import ClaseAgregada, agregados_materia
from app.extras.palabras import palabras_frecuentes
from app.models import DocenteMateria, Materia
from app.schemas import PuntoTendenciaOutput


# Nunca reutilizar FeedbackOutput, que expone alumno_id y timestamps. La
# tendencia usa el mismo modelo que SPEC-04.
class ComparacionOutput(BaseModel):
    materia_id: int
    nombre: str
    semestre: str
    cantidad_respuestas: int
    promedio_general: Optional[float] = None
    tendencia: list[PuntoTendenciaOutput]


class PalabraOutput(BaseModel):
    palabra: str
    cantidad: int


def redondear(valor: Optional[float]) -> Optional[float]:
    return None if valor is None else round(valor, 2)


def promedio_general(clases: list[ClaseAgregada]) -> Optional[float]:
    # Ponderado por respuestas y solo sobre clases que pasan el umbral: incluir
    # las demás permitiría deducir su promedio por diferencia.
    visibles = [c for c in clases if c.promedio is not None]
    respuestas = sum(c.cantidad for c in visibles)
    if respuestas == 0:
        return None
    return sum(c.promedio * c.cantidad for c in visibles) / respuestas


def etiqueta(clase: ClaseAgregada) -> str:
    return clase.tema or f"Clase del {clase.fecha.isoformat()}"


def celda(valor) -> str:
    texto = "" if valor is None else str(valor)
    # Evita que una planilla interprete un comentario como fórmula.
    return "'" + texto if texto.startswith(("=", "+", "-", "@", "\t", "\r")) else texto


def respuesta_csv(nombre: str, encabezado: list[str], filas: list[list]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(encabezado)
    writer.writerows([celda(valor) for valor in fila] for fila in filas)
    # BOM para que Excel detecte UTF-8 y muestre bien las tildes.
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
            "Cache-Control": "no-store",
        },
    )


router = APIRouter(prefix="/docente", dependencies=[Depends(require_docente)])


# Como en SPEC-04, los promedios debajo del umbral se omiten en lugar de ser null.
@router.get("/comparacion", response_model=list[ComparacionOutput], response_model_exclude_none=True)
def comparacion(
    semestre: Optional[str] = Query(default=None, max_length=30),
    user: Principal = Depends(current_user),
    db: Session = Depends(get_db),
):
    # Solo materias que el docente dicta, según DocenteMateria.
    query = (
        select(Materia).join(DocenteMateria, DocenteMateria.materia_id == Materia.id)
        .where(DocenteMateria.docente_id == user.id).order_by(Materia.id)
    )
    if semestre is not None:
        query = query.where(Materia.semestre == semestre)
    resultado = []
    for materia in db.scalars(query):
        clases = agregados_materia(db, materia.id)
        resultado.append(ComparacionOutput(
            materia_id=materia.id,
            nombre=materia.nombre,
            semestre=materia.semestre,
            cantidad_respuestas=sum(c.cantidad for c in clases),
            promedio_general=redondear(promedio_general(clases)),
            tendencia=[
                PuntoTendenciaOutput(clase_id=c.clase_id, fecha=c.fecha,
                                     cantidad_respuestas=c.cantidad, promedio=redondear(c.promedio))
                for c in clases
            ],
        ))
    return resultado


@router.get("/materias/{materia_id}/resumen.csv")
def exportar_resumen(materia: Materia = Depends(require_materia), db: Session = Depends(get_db)):
    filas = [
        [etiqueta(c), c.fecha.isoformat(), redondear(c.promedio), c.cantidad]
        for c in agregados_materia(db, materia.id)
    ]
    return respuesta_csv(f"materia-{materia.id}-resumen.csv",
                         ["clase", "fecha", "promedio", "cantidad"], filas)


@router.get("/materias/{materia_id}/comentarios.csv")
def exportar_comentarios(materia: Materia = Depends(require_materia), db: Session = Depends(get_db)):
    filas = [
        [etiqueta(c), c.fecha.isoformat(), comentario]
        for c in agregados_materia(db, materia.id)
        for comentario in sorted(c.comentarios)
    ]
    return respuesta_csv(f"materia-{materia.id}-comentarios.csv",
                         ["clase", "fecha", "comentario"], filas)


@router.get("/materias/{materia_id}/palabras", response_model=list[PalabraOutput])
def palabras(
    clase_id: Optional[int] = None,
    materia: Materia = Depends(require_materia),
    db: Session = Depends(get_db),
):
    clases = agregados_materia(db, materia.id)
    if clase_id is not None:
        clases = [c for c in clases if c.clase_id == clase_id]
        if not clases:
            raise HTTPException(status_code=404, detail="Clase no encontrada")
    # Los comentarios ya vienen filtrados por umbral desde la fuente.
    textos = (texto for c in clases for texto in c.comentarios)
    return [PalabraOutput(palabra=p, cantidad=n) for p, n in palabras_frecuentes(textos)]
