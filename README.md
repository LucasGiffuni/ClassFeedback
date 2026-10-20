SPEC-01: Base: modelo de datos, auth y roles

Objetivo: cimientos para que el resto de las specs no toque esquema ni permisos.

Entidades:

Usuario (id, nombre, email, rol: ALUMNO | DOCENTE)
Materia (id, nombre, semestre)
DocenteMateria (docente_id, materia_id)
Inscripcion (alumno_id, materia_id)
Clase (id, materia_id, fecha, tema opcional)
Feedback (id, clase_id, alumno_id, gustó, no_gustó, calificación, creado_en, editado_en)

Requisitos:

Autenticación y rol en cada request.
Constraint único (clase_id, alumno_id) en Feedback.
Middleware/guard por rol y por pertenencia a la materia.

Criterios de aceptación:

Un usuario sin sesión recibe 401 en cualquier endpoint.
Un alumno que llama a un endpoint de docente recibe 403.
Un docente consultando una materia que no dicta recibe 403 (o 404, para no revelar que existe).
SPEC-02: Materias y clases por fecha

Objetivo: que alumnos y docentes naveguen materias y sus clases.

Requisitos:

Alumno: lista de sus materias y, por materia, clases ordenadas por fecha desc.
Docente: lo mismo, solo de sus materias.
Cada clase muestra si el alumno ya dejó feedback (pendiente | enviado).
Alta de materias y clases: seed o CRUD mínimo (ver supuesto 5).
No se puede crear una clase con fecha futura para feedback (la clase debe haber ocurrido).

Criterios de aceptación:

Alumno inscripto en 2 materias ve exactamente esas 2.
La lista de clases muestra el estado de feedback correcto por alumno.
Una clase con fecha futura no admite feedback (error 422).
SPEC-03: Feedback del alumno (crear y editar)

Objetivo: el flujo de escritura, con las reglas de negocio.

Campos: gustó (texto, máx. 500 caracteres), no_gustó (texto, máx. 500), calificación (entero 1–5, obligatoria). Los textos son opcionales.

Reglas:

Un solo feedback por clase y alumno (409 si ya existe; se edita, no se recrea).
Solo alumnos inscriptos en la materia.
Edición permitida hasta 48 h después de la creación del feedback [SUPUESTO]; pasado el plazo, 403 con mensaje claro.
El alumno solo ve y edita el suyo.

Criterios de aceptación:

Crear feedback válido → 201; segundo intento sobre la misma clase → 409.
Editar a las 47 h → 200; a las 49 h → 403.
Calificación 0 o 6 → 422.
Alumno no inscripto → 403.
SPEC-04: Vista agregada del docente (anonimato)

Objetivo: el docente ve resultados sin poder identificar a nadie.

Requisitos:

Por clase: promedio, cantidad de respuestas, distribución 1–5 y lista de comentarios.
Tendencia: serie de promedios por clase ordenada por fecha a lo largo del semestre.
Anonimato por diseño: las respuestas del docente nunca incluyen alumno_id, ni email, ni creado_en exacto (se muestra solo la fecha de la clase). Los comentarios se devuelven en orden aleatorio o alfabético, no cronológico.
Umbral mínimo: si una clase tiene menos de 3 feedbacks, se muestra la cantidad pero no promedio ni comentarios [SUPUESTO].
Aislamiento: solo materias propias.

Criterios de aceptación:

El JSON de respuesta no contiene ningún campo que identifique al alumno (test automatizado que inspecciona las claves).
Clase con 2 feedbacks → sin promedio ni comentarios; con 3 → visibles.
Docente A pidiendo materia de docente B → 403/404.
SPEC-05: Extras (comparación, exportación, palabras frecuentes)

Objetivo: valor agregado sobre la vista de SPEC-04, sin romper su anonimato.

Requisitos:

Comparación entre materias: promedio general y tendencia de las materias del docente, lado a lado. Solo materias propias; aplica el mismo umbral de 3.
Exportar a planilla: CSV (y opcionalmente XLSX) con las columnas clase, fecha, promedio, cantidad. Los comentarios van sin ningún dato del autor.
Palabras más repetidas: top 20 de palabras por materia o clase, ignorando stopwords en español, mínimo 2 caracteres, con conteo. Se calcula sobre clases que pasan el umbral.

Criterios de aceptación:

El CSV exportado no contiene IDs ni emails de alumnos.
Las stopwords (“el”, “de”, “que”…) no aparecen en el top 20.
La comparación no incluye materias de otros docentes.
Supuestos a validar
Escala 1–5.
Plazo de edición 48 h desde la creación.
Umbral de anonimato k = 3 feedbacks.
Una calificación es obligatoria; los textos son opcionales.
Materias, clases e inscripciones se cargan por seed o CRUD básico (no hay integración con un sistema académico real).