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
