# Manual de la API REST de Huancayoga

## 1. Objetivo

Esta API agrega una interfaz REST al sistema existente sin reemplazar el panel web. Ambas interfaces usan las mismas tablas MySQL:

- El panel administrativo trabaja con formularios HTML y sesiones.
- La API trabaja con JSON, métodos HTTP y tokens Bearer.

La versión inicial cubre los CRUD completos de `productos` y `publicaciones`, que son los módulos con operaciones administrativas completas en el sistema original.

## 2. Arquitectura implementada

```text
Postman
   │ JSON + Bearer token
   ▼
/api/v1 (Blueprint de Flask)
   │ validación y autorización
   ▼
Flask-MySQLdb
   │ consultas parametrizadas
   ▼
MySQL: productos y publicaciones
```

Archivos principales:

- `api_v1.py`: autenticación, validaciones, respuestas y endpoints REST.
- `app.py`: configura Flask, MySQL y registra el Blueprint.
- `tests/test_api_v1.py`: pruebas automatizadas de validación y seguridad.
- `docs/postman/Huancayoga_API_REST.postman_collection.json`: colección importable en Postman.

No fue necesaria una migración porque se reutilizan las tablas y usuarios existentes.

## 3. Preparación

Desde la carpeta `github_repo`, activa el entorno virtual e instala las dependencias si todavía no están instaladas:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Configura `.env`. La API utiliza la misma base de datos y `SECRET_KEY` de Flask. Agrega o revisa:

```dotenv
SECRET_KEY=una-clave-larga-aleatoria-y-privada
DB_HOST=servidor_mysql
DB_PORT=3306
DB_USER=usuario_mysql
DB_PASSWORD=clave_mysql
DB_NAME=huancayoga
API_TOKEN_TTL_SECONDS=3600
```

`API_TOKEN_TTL_SECONDS=3600` hace que cada token sea válido durante una hora. En producción nunca debe usarse la clave temporal predeterminada de la aplicación.

Inicia el servidor:

```powershell
python app.py
```

La URL local predeterminada será `http://127.0.0.1:5000`.

## 4. Autenticación

La API reutiliza la tabla `usuarios`. Primero se solicita un token con las mismas credenciales del administrador:

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{
  "usuario": "admin",
  "password": "contraseña-del-administrador"
}
```

Respuesta exitosa (`200 OK`):

```json
{
  "success": true,
  "message": "Autenticación correcta",
  "data": {
    "access_token": "token-firmado",
    "token_type": "Bearer",
    "expires_in": 3600,
    "usuario": {
      "id": 1,
      "nombre": "Administrador",
      "rol": "admin"
    }
  }
}
```

Todas las demás operaciones requieren este encabezado:

```http
Authorization: Bearer token-firmado
```

El token está firmado con `SECRET_KEY`, tiene expiración y contiene el identificador, nombre de usuario y rol. No contiene la contraseña.

## 5. Endpoints de productos

| Método | Ruta | Acción | Código exitoso |
|---|---|---|---:|
| `GET` | `/api/v1/productos` | Listar | 200 |
| `GET` | `/api/v1/productos/{id}` | Consultar uno | 200 |
| `POST` | `/api/v1/productos` | Crear | 201 |
| `PUT` | `/api/v1/productos/{id}` | Reemplazar datos editables | 200 |
| `PATCH` | `/api/v1/productos/{id}` | Modificar algunos campos | 200 |
| `DELETE` | `/api/v1/productos/{id}` | Desactivar | 200 |

Ejemplo de creación:

```json
{
  "nombre": "Mat profesional",
  "descripcion": "Mat antideslizante de 6 mm",
  "precio": 89.90,
  "stock": 15,
  "imagen": null
}
```

Reglas principales:

- `nombre`: obligatorio, máximo 100 caracteres.
- `precio`: obligatorio, número igual o mayor que cero.
- `stock`: obligatorio, entero igual o mayor que cero.
- `imagen`: opcional, máximo 255 caracteres.
- `estado`: opcional; solamente `activo` o `inactivo`.

Ejemplo de actualización parcial:

```http
PATCH /api/v1/productos/12
```

```json
{
  "precio": 95.50,
  "stock": 8
}
```

## 6. Endpoints de publicaciones

| Método | Ruta | Acción | Código exitoso |
|---|---|---|---:|
| `GET` | `/api/v1/publicaciones` | Listar | 200 |
| `GET` | `/api/v1/publicaciones/{id}` | Consultar una | 200 |
| `POST` | `/api/v1/publicaciones` | Crear | 201 |
| `PUT` | `/api/v1/publicaciones/{id}` | Reemplazar datos editables | 200 |
| `PATCH` | `/api/v1/publicaciones/{id}` | Modificar algunos campos | 200 |
| `DELETE` | `/api/v1/publicaciones/{id}` | Desactivar | 200 |

Ejemplo de creación:

```json
{
  "titulo": "Taller de respiración",
  "contenido": "Nueva sesión disponible este fin de semana.",
  "tipo": "noticia",
  "imagen": null
}
```

Reglas principales:

- `titulo`: obligatorio, máximo 150 caracteres.
- `contenido`: obligatorio.
- `tipo`: `monologo`, `frase`, `noticia`, `foto` o `promocion`.
- `imagen`: opcional, máximo 255 caracteres.
- `estado`: `activo` o `inactivo`.

## 7. Paginación y filtros

Los listados aceptan parámetros de consulta:

```http
GET /api/v1/productos?page=1&per_page=20&estado=activo
```

- `page`: página, desde 1.
- `per_page`: elementos por página, entre 1 y 100.
- `estado`: `activo` o `inactivo`.

La respuesta incluye metadatos:

```json
{
  "success": true,
  "data": [],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 0,
    "pages": 0
  }
}
```

## 8. Eliminación lógica

`DELETE` no borra físicamente el registro. Ejecuta conceptualmente:

```sql
UPDATE productos SET estado = 'inactivo' WHERE id = ?;
```

Se aplica el mismo criterio a publicaciones. Esta decisión conserva la trazabilidad y evita romper relaciones históricas, por ejemplo pedidos asociados con productos.

Para reactivar un registro se utiliza `PATCH`:

```json
{
  "estado": "activo"
}
```

## 9. Respuestas y errores

Formato exitoso:

```json
{
  "success": true,
  "message": "Producto creado correctamente.",
  "data": {}
}
```

Formato de error:

```json
{
  "success": false,
  "error": {
    "code": "DATOS_INVALIDOS",
    "message": "Revisa los datos enviados.",
    "details": {
      "stock": "Debe ser un entero no negativo."
    }
  }
}
```

| Código HTTP | Significado |
|---:|---|
| 200 | Consulta, actualización o desactivación correcta |
| 201 | Recurso creado |
| 400 | JSON, credenciales o paginación incorrectos |
| 401 | Credenciales/token incorrecto o expirado |
| 403 | Usuario sin rol administrador |
| 404 | Recurso inexistente |
| 409 | Conflicto con una restricción de base de datos |
| 415 | El cuerpo no fue enviado como JSON |
| 422 | Campos semánticamente inválidos |

## 10. Demostración en Postman

1. Abre Postman y selecciona **Import**.
2. Importa `docs/postman/Huancayoga_API_REST.postman_collection.json`.
3. Abre las variables de la colección.
4. Coloca el usuario en `adminUsuario` y la contraseña en `adminPassword`.
5. Ejecuta **Login de administrador**. El script guarda el token automáticamente.
6. Ejecuta, en orden, las cinco solicitudes de **Productos CRUD**.
7. Repite con **Publicaciones CRUD**.
8. Comprueba en el panel administrativo que los datos creados por Postman aparecen allí.

Durante una exposición, explica esta correspondencia:

```text
POST   → Create → INSERT
GET    → Read   → SELECT
PUT/PATCH → Update → UPDATE
DELETE → Delete lógico → UPDATE estado='inactivo'
```

No muestres la contraseña ni el contenido de `.env` en capturas o grabaciones.

## 11. Pruebas automatizadas

Ejecuta desde `github_repo`:

```powershell
python -m unittest discover -s tests -v
```

Las pruebas comprueban:

- Normalización de precio y stock.
- Rechazo de valores negativos o fraccionarios inválidos.
- Rechazo de tipos de publicación desconocidos.
- Protección de endpoints cuando falta el token Bearer.

La colección Postman complementa estas pruebas con verificaciones integradas contra MySQL.

## 12. Criterios técnicos para defender

- **Versionado:** `/api/v1` permite crear una futura v2 sin romper clientes actuales.
- **Separación de responsabilidades:** las rutas JSON viven fuera de las vistas HTML.
- **Consultas parametrizadas:** los valores no se concatenan al SQL, reduciendo riesgo de inyección.
- **Autorización:** solamente administradores autenticados modifican datos.
- **Validación:** la API no depende únicamente de restricciones de MySQL.
- **Códigos HTTP:** cada resultado comunica correctamente su significado.
- **Paginación:** evita devolver cantidades ilimitadas de registros.
- **DELETE lógico:** conserva integridad e historial.
- **Transacciones:** cada escritura confirma con `commit` y revierte conflictos controlados.

## 13. Alcance y evolución

Esta primera versión se concentra en recursos maestros simples. Reservas y pedidos necesitan endpoints especializados, no un CRUD genérico, porque manejan disponibilidad, stock y transiciones de estado. Una segunda versión debería agregar:

- Renovación o revocación de tokens.
- Registro persistente de auditoría (`quién`, `qué`, `cuándo`).
- Límite de intentos de login.
- Especificación OpenAPI/Swagger.
- Pruebas de integración sobre una base exclusiva de pruebas.
- Endpoints transaccionales para pedidos y reservas.

Estas mejoras no son necesarias para demostrar los CRUD actuales, pero sí serían parte de una evolución orientada a producción.
