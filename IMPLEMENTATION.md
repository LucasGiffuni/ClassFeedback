# ClassFeedback — SPEC-01

API en Python 3.9+ con FastAPI, SQLAlchemy 2 y migraciones Alembic. SQLite es la base de desarrollo. Las entidades están en `app/models.py`; la migración inicial crea las seis entidades de dominio y la tabla de sesiones.

## Instalación y ejecución

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
export DATABASE_URL='sqlite:///./classfeedback.db'
export SESSION_TTL_SECONDS=86400
alembic upgrade head
export SEED_PASSWORD='una-clave-local-de-al-menos-12-caracteres'
python -m app.seed
uvicorn app.main:app --reload
```

El seed crea `alumno@example.com`, `docente@example.com`, una materia, una inscripción, una asignación docente y una clase. Ambos usuarios usan `SEED_PASSWORD`. Solo se ejecuta sobre una base sin usuarios, dentro de una transacción. La aplicación lee variables del entorno; `.env.example` documenta las disponibles y no se carga automáticamente.

## Autenticación y endpoints

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"docente@example.com","password":"una-clave-local-de-al-menos-12-caracteres"}'

# Copiar access_token de la respuesta:
export TOKEN='token-devuelto-por-login'
curl http://127.0.0.1:8000/auth/me -H "Authorization: Bearer $TOKEN"
curl http://127.0.0.1:8000/docente/materias -H "Authorization: Bearer $TOKEN"
curl http://127.0.0.1:8000/docente/materias/1 -H "Authorization: Bearer $TOKEN"
curl -X POST http://127.0.0.1:8000/auth/logout -H "Authorization: Bearer $TOKEN"
```

| Método | Ruta | Acceso |
| --- | --- | --- |
| POST | `/auth/login` | Pública; email y password, devuelve token Bearer y duración en segundos |
| POST | `/auth/logout` | Sesión válida; revoca el token actual, devuelve 204 |
| GET | `/auth/me` | Sesión válida; usuario actual sin credenciales |
| GET | `/materias` | Solo materias del usuario según su rol |
| GET | `/materias/{materia_id}` | Solo materia propia |
| GET | `/docente/materias` | Solo DOCENTE; materias que dicta |
| GET | `/docente/materias/{materia_id}` | Solo DOCENTE y materia que dicta |
| GET | `/materias/{materia_id}/clases` | Solo materia propia; clases por fecha descendente. El alumno ve `feedback`: `pendiente` o `enviado`; el docente no |
| POST | `/docente/materias/{materia_id}/clases` | Solo DOCENTE y materia que dicta; body `{fecha, tema?}`; devuelve 201, o 422 si la fecha es futura |

`POST /auth/login` es la única excepción al requisito de sesión: permite obtenerla. El middleware devuelve **401** antes del routing o la validación si falta el token, es inválido, expiró o fue revocado, incluso para rutas desconocidas. Las rutas de documentación están deshabilitadas. Un ALUMNO recibe **403** en las rutas de docente. Una materia ajena o inexistente devuelve **404** con el mismo mensaje.

### Feedback del alumno (SPEC-03)

| Método | Ruta | Acceso |
| --- | --- | --- |
| POST | `/clases/{clase_id}/feedback` | Solo ALUMNO inscripto en la materia; body `{gusto?, no_gusto?, calificacion}`; devuelve 201 |
| GET | `/clases/{clase_id}/feedback` | Solo ALUMNO inscripto; devuelve únicamente su feedback |
| PUT | `/feedback/{feedback_id}` | Solo el alumno propietario; permitido hasta 48 horas desde `creado_en` |

Los textos son opcionales y tienen un máximo de 500 caracteres. `calificacion` es obligatoria y debe estar entre 1 y 5; los errores de validación devuelven 422. Un segundo POST para la misma clase y alumno devuelve 409. Las clases futuras no admiten feedback (422). Un feedback ajeno se responde como 404 y, una vez vencidas las 48 horas, la edición responde 403 con un mensaje explícito.

### Extras del docente (SPEC-05)

| Método | Ruta | Acceso |
| --- | --- | --- |
| GET | `/docente/comparacion?semestre=` | Solo DOCENTE; sus materias lado a lado con `cantidad_respuestas`, `promedio_general` y `tendencia`. `semestre` es opcional |
| GET | `/docente/materias/{materia_id}/resumen.csv` | Solo DOCENTE y materia que dicta; columnas `clase, fecha, promedio, cantidad` |
| GET | `/docente/materias/{materia_id}/comentarios.csv` | Solo DOCENTE y materia que dicta; columnas `clase, fecha, comentario` |
| GET | `/docente/materias/{materia_id}/palabras?clase_id=` | Solo DOCENTE y materia que dicta; top 20 `{palabra, cantidad}` de la materia o de una de sus clases (otra clase: 404) |

Se aplica el umbral de anonimato k = 3: una clase con menos feedbacks muestra la cantidad, pero no promedio, comentarios ni palabras. Como en SPEC-04, los promedios debajo del umbral se omiten de la respuesta; la `tendencia` usa el mismo formato que `/docente/materias/{materia_id}/tendencia`. El `promedio_general` se pondera por respuestas y solo usa clases que pasan el umbral, para que no se pueda deducir el promedio de una clase oculta por diferencia. Ninguna respuesta incluye IDs, emails ni timestamps de alumnos.

En `resumen.csv`, `clase` es el tema o `Clase del {fecha}` y `promedio` queda vacío debajo del umbral. `comentarios.csv` lista los textos de `gusto` y `no_gusto` sin autor, en orden alfabético por clase, descartando textos en blanco. Los CSV se descargan como adjunto en UTF-8 con BOM (para Excel) y `Cache-Control: no-store`; las celdas que empiezan con `=`, `+`, `-` o `@` llevan un `'` delante para que la planilla no las ejecute como fórmula.

Las palabras se cuentan en minúsculas sobre `gusto` y `no_gusto`, con al menos 2 letras y sin números, ignorando las stopwords de `app/extras/stopwords_es.py` sin distinguir tildes ("qué" = "que"). Los empates se ordenan alfabéticamente.

```bash
curl http://127.0.0.1:8000/docente/comparacion -H "Authorization: Bearer $TOKEN"
curl -OJ http://127.0.0.1:8000/docente/materias/1/resumen.csv -H "Authorization: Bearer $TOKEN"
curl -OJ http://127.0.0.1:8000/docente/materias/1/comentarios.csv -H "Authorization: Bearer $TOKEN"
curl "http://127.0.0.1:8000/docente/materias/1/palabras?clase_id=1" -H "Authorization: Bearer $TOKEN"
```

El código está en `app/extras/`. Todos los datos agregados salen de `fuente.py` (`ClaseAgregada`, `umbral()`, `agregados_materia()`), que aplica el umbral antes de devolver nada. La agregación de SPEC-04 está dentro de sus rutas y no es reutilizable, por lo que `fuente.py` hace su propio cálculo; un test verifica que tendencia, promedios y comentarios coincidan con los de SPEC-04, así que un cambio en uno de los dos que no se replique en el otro hace fallar las pruebas. SPEC-05 no modifica el esquema ni agrega migraciones.

Las contraseñas se almacenan con PBKDF2-HMAC-SHA256, salt aleatorio y 600.000 iteraciones. Las sesiones usan tokens aleatorios de 256 bits y solo se guarda su hash SHA-256. El usuario y su rol se consultan en cada request; la pertenencia se consulta en cada acceso a una materia. No existe un endpoint público de registro o modificación de roles.

## Guards reutilizables y esquema

- `app/auth.py`: `require_role`, `require_alumno`, `require_docente`, `require_materia`, `require_clase` y `authorize_materia` para los próximos endpoints. Las rutas específicas de rol deben declarar el guard de rol además del guard de pertenencia.
- `require_clase` resuelve la materia desde la clase persistida y comprueba pertenencia, sin confiar en una materia enviada por el cliente.
- `Usuario.rol` tiene constraint `ALUMNO | DOCENTE`; email único. `password_hash` es un campo interno adicional para autenticación.
- Las asociaciones tienen claves primarias compuestas para impedir asignaciones duplicadas; todas las referencias tienen foreign keys, habilitadas también en SQLite.
- `Feedback` tiene constraint único `(clase_id, alumno_id)`, calificación 1–5, textos opcionales de hasta 500 caracteres y timestamps UTC gestionados por el ORM. Los nombres de código sin tildes son `gusto`, `no_gusto` y `calificacion`.
- `semestre` es una etiqueta, por ejemplo `2026-2`; `fecha` es una fecha sin hora; `tema` es opcional.
- Para futuras migraciones: `alembic revision --autogenerate -m "descripcion"`, revisar el resultado y ejecutar `alembic upgrade head`.

## Verificación

```bash
python -m pytest -q
```

Las pruebas crean una base temporal con la migración real. Cubren los tres criterios de aceptación, inscripción de alumnos, guards de clase, cambios de rol y pertenencia durante una sesión, credenciales inválidas, expiración, logout, almacenamiento del hash del token, unicidad y constraints de feedback. También verifican que la migración coincide con los modelos y que se puede revertir y reaplicar.

Las pruebas de SPEC-05 están en `tests/test_extras.py` y `tests/test_extras_fuente.py` (contrato de `fuente.py`), con datos de `tests/datos_extras.py`. Cubren sus tres criterios de aceptación, el umbral, el anonimato de las respuestas JSON y CSV, el escape de fórmulas, el acceso por rol y materia, la integración con el feedback de SPEC-03 y la consistencia con SPEC-04.
