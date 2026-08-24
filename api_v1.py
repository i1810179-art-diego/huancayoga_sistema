"""API REST v1 de Huancayoga.

Expone CRUD JSON para productos y publicaciones sin acoplarlo a las vistas HTML.
"""

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from MySQLdb import IntegrityError
from MySQLdb.cursors import DictCursor


api = Blueprint("api_v1", __name__, url_prefix="/api/v1")
_mysql = None
_password_validator = None

ESTADOS = {"activo", "inactivo"}
TIPOS_PUBLICACION = {"monologo", "frase", "noticia", "foto", "promocion"}


def register_api(app, mysql, password_validator):
    """Registra la API y recibe las dependencias ya configuradas por la aplicación."""
    global _mysql, _password_validator
    _mysql = mysql
    _password_validator = password_validator
    app.config.setdefault("API_TOKEN_TTL_SECONDS", 3600)
    app.register_blueprint(api)


def respuesta(data=None, message=None, status=200, meta=None):
    body = {"success": True}
    if message:
        body["message"] = message
    if data is not None:
        body["data"] = data
    if meta is not None:
        body["meta"] = meta
    return jsonify(body), status


def error(code, message, status, details=None):
    body = {"success": False, "error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="huancayoga-api-v1")


def _crear_token(usuario):
    return _serializer().dumps({
        "sub": usuario["id"],
        "usuario": usuario["usuario"],
        "rol": usuario["rol"],
    })


def requiere_token(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return error("TOKEN_REQUERIDO", "Envía un token Bearer válido.", 401)
        try:
            g.api_user = _serializer().loads(
                token,
                max_age=current_app.config["API_TOKEN_TTL_SECONDS"],
            )
        except SignatureExpired:
            return error("TOKEN_EXPIRADO", "El token de acceso ha expirado.", 401)
        except BadSignature:
            return error("TOKEN_INVALIDO", "El token de acceso no es válido.", 401)
        if g.api_user.get("rol") != "admin":
            return error("PERMISO_DENEGADO", "Se requiere el rol de administrador.", 403)
        return func(*args, **kwargs)
    return wrapper


def _json_body():
    if not request.is_json:
        return None, error(
            "CONTENT_TYPE_INVALIDO",
            "Envía el cuerpo con Content-Type: application/json.",
            415,
        )
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, error("JSON_INVALIDO", "El cuerpo JSON debe ser un objeto.", 400)
    return data, None


def _texto(data, field, errors, required=False, max_length=None, nullable=False):
    if field not in data:
        if required:
            errors[field] = "Este campo es obligatorio."
        return None
    value = data[field]
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        errors[field] = "Debe ser un texto no vacío."
        return None
    value = value.strip()
    if max_length and len(value) > max_length:
        errors[field] = f"No debe superar {max_length} caracteres."
    return value


def validar_producto(data, partial=False):
    errors, clean = {}, {}
    for field, limit, nullable in (
        ("nombre", 100, False),
        ("descripcion", None, True),
        ("imagen", 255, True),
    ):
        value = _texto(
            data, field, errors,
            required=not partial and field == "nombre",
            max_length=limit, nullable=nullable,
        )
        if field in data and field not in errors:
            clean[field] = value

    for field, integer in (("precio", False), ("stock", True)):
        if field not in data:
            if not partial:
                errors[field] = "Este campo es obligatorio."
            continue
        value = data[field]
        try:
            number = Decimal(str(value))
            if not number.is_finite() or number < 0 or (integer and number != int(number)):
                raise ValueError
            clean[field] = int(number) if integer else number.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            errors[field] = "Debe ser un entero no negativo." if integer else "Debe ser un número no negativo."

    if "estado" in data:
        if data["estado"] not in ESTADOS:
            errors["estado"] = "Valores permitidos: activo, inactivo."
        else:
            clean["estado"] = data["estado"]
    return clean, errors


def validar_publicacion(data, partial=False):
    errors, clean = {}, {}
    for field, limit, nullable in (
        ("titulo", 150, False),
        ("contenido", None, False),
        ("imagen", 255, True),
    ):
        value = _texto(
            data, field, errors,
            required=not partial and field in {"titulo", "contenido"},
            max_length=limit, nullable=nullable,
        )
        if field in data and field not in errors:
            clean[field] = value
    if "tipo" not in data and not partial:
        errors["tipo"] = "Este campo es obligatorio."
    elif "tipo" in data:
        if data["tipo"] not in TIPOS_PUBLICACION:
            errors["tipo"] = f"Valores permitidos: {', '.join(sorted(TIPOS_PUBLICACION))}."
        else:
            clean["tipo"] = data["tipo"]
    if "estado" in data:
        if data["estado"] not in ESTADOS:
            errors["estado"] = "Valores permitidos: activo, inactivo."
        else:
            clean["estado"] = data["estado"]
    return clean, errors


def _serializar(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def _fila_json(row):
    return {key: _serializar(value) for key, value in row.items()}


def _paginacion():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return None, error("PAGINACION_INVALIDA", "page y per_page deben ser enteros.", 400)
    if page < 1 or not 1 <= per_page <= 100:
        return None, error("PAGINACION_INVALIDA", "page debe ser >= 1 y per_page debe estar entre 1 y 100.", 400)
    return (page, per_page), None


@api.post("/auth/login")
def api_login():
    data, failure = _json_body()
    if failure:
        return failure
    usuario = str(data.get("usuario", "")).strip()
    password = data.get("password", "")
    if not usuario or not isinstance(password, str) or not password:
        return error("CREDENCIALES_REQUERIDAS", "usuario y password son obligatorios.", 400)
    cursor = _mysql.connection.cursor(DictCursor)
    cursor.execute(
        "SELECT id, nombre, usuario, password, rol FROM usuarios WHERE usuario = %s",
        (usuario,),
    )
    admin = cursor.fetchone()
    cursor.close()
    if not admin or not _password_validator(admin["password"], password):
        return error("CREDENCIALES_INVALIDAS", "Usuario o contraseña incorrectos.", 401)
    if admin["rol"] != "admin":
        return error("PERMISO_DENEGADO", "La cuenta no tiene permisos administrativos.", 403)
    token = _crear_token(admin)
    return respuesta({
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": current_app.config["API_TOKEN_TTL_SECONDS"],
        "usuario": {"id": admin["id"], "nombre": admin["nombre"], "rol": admin["rol"]},
    }, message="Autenticación correcta")


def _listar(tabla, columnas, orden):
    pagination, failure = _paginacion()
    if failure:
        return failure
    page, per_page = pagination
    estado = request.args.get("estado")
    if estado and estado not in ESTADOS:
        return error("FILTRO_INVALIDO", "estado debe ser activo o inactivo.", 400)
    where, params = (" WHERE estado = %s", [estado]) if estado else ("", [])
    cursor = _mysql.connection.cursor(DictCursor)
    cursor.execute(f"SELECT COUNT(*) AS total FROM {tabla}{where}", tuple(params))
    total = cursor.fetchone()["total"]
    cursor.execute(
        f"SELECT {columnas} FROM {tabla}{where} ORDER BY {orden} LIMIT %s OFFSET %s",
        tuple(params + [per_page, (page - 1) * per_page]),
    )
    rows = [_fila_json(row) for row in cursor.fetchall()]
    cursor.close()
    pages = (total + per_page - 1) // per_page
    return respuesta(rows, meta={"page": page, "per_page": per_page, "total": total, "pages": pages})


def _obtener(tabla, columnas, item_id, nombre_recurso):
    cursor = _mysql.connection.cursor(DictCursor)
    cursor.execute(f"SELECT {columnas} FROM {tabla} WHERE id = %s", (item_id,))
    row = cursor.fetchone()
    cursor.close()
    if not row:
        return None, error("NO_ENCONTRADO", f"{nombre_recurso} no encontrado.", 404)
    return _fila_json(row), None


PRODUCTO_COLS = "id, nombre, descripcion, precio, stock, imagen, estado, fecha_creacion"
PUBLICACION_COLS = "id, titulo, contenido, imagen, tipo, estado, fecha_publicacion"


@api.get("/productos")
@requiere_token
def listar_productos():
    return _listar("productos", PRODUCTO_COLS, "id DESC")


@api.get("/productos/<int:item_id>")
@requiere_token
def obtener_producto(item_id):
    item, failure = _obtener("productos", PRODUCTO_COLS, item_id, "Producto")
    return failure or respuesta(item)


@api.post("/productos")
@requiere_token
def crear_producto():
    data, failure = _json_body()
    if failure:
        return failure
    clean, errors = validar_producto(data)
    if errors:
        return error("DATOS_INVALIDOS", "Revisa los datos enviados.", 422, errors)
    cursor = _mysql.connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO productos (nombre, descripcion, precio, stock, imagen, estado) VALUES (%s, %s, %s, %s, %s, %s)",
            (clean["nombre"], clean.get("descripcion"), clean["precio"], clean["stock"], clean.get("imagen"), clean.get("estado", "activo")),
        )
        item_id = cursor.lastrowid
        _mysql.connection.commit()
    except IntegrityError:
        _mysql.connection.rollback()
        return error("CONFLICTO_DATOS", "El producto no pudo registrarse por una restricción de datos.", 409)
    finally:
        cursor.close()
    item, _ = _obtener("productos", PRODUCTO_COLS, item_id, "Producto")
    return respuesta(item, "Producto creado correctamente.", 201)


def _actualizar(tabla, columnas, item_id, clean, nombre):
    existing, failure = _obtener(tabla, columnas, item_id, nombre)
    if failure:
        return failure
    if not clean:
        return error("SIN_CAMBIOS", "Envía al menos un campo para actualizar.", 422)
    assignments = ", ".join(f"{field} = %s" for field in clean)
    cursor = _mysql.connection.cursor()
    try:
        cursor.execute(f"UPDATE {tabla} SET {assignments} WHERE id = %s", tuple(clean.values()) + (item_id,))
        _mysql.connection.commit()
    except IntegrityError:
        _mysql.connection.rollback()
        return error("CONFLICTO_DATOS", f"{nombre} no pudo actualizarse por una restricción de datos.", 409)
    finally:
        cursor.close()
    item, _ = _obtener(tabla, columnas, item_id, nombre)
    return respuesta(item, f"{nombre} actualizado correctamente.")


@api.route("/productos/<int:item_id>", methods=["PUT", "PATCH"])
@requiere_token
def actualizar_producto(item_id):
    data, failure = _json_body()
    if failure:
        return failure
    clean, errors = validar_producto(data, partial=request.method == "PATCH")
    if errors:
        return error("DATOS_INVALIDOS", "Revisa los datos enviados.", 422, errors)
    return _actualizar("productos", PRODUCTO_COLS, item_id, clean, "Producto")


@api.delete("/productos/<int:item_id>")
@requiere_token
def eliminar_producto(item_id):
    _, failure = _obtener("productos", PRODUCTO_COLS, item_id, "Producto")
    if failure:
        return failure
    cursor = _mysql.connection.cursor()
    cursor.execute("UPDATE productos SET estado = 'inactivo' WHERE id = %s", (item_id,))
    _mysql.connection.commit()
    cursor.close()
    return respuesta(message="Producto desactivado correctamente.")


@api.get("/publicaciones")
@requiere_token
def listar_publicaciones():
    return _listar("publicaciones", PUBLICACION_COLS, "fecha_publicacion DESC")


@api.get("/publicaciones/<int:item_id>")
@requiere_token
def obtener_publicacion(item_id):
    item, failure = _obtener("publicaciones", PUBLICACION_COLS, item_id, "Publicación")
    return failure or respuesta(item)


@api.post("/publicaciones")
@requiere_token
def crear_publicacion():
    data, failure = _json_body()
    if failure:
        return failure
    clean, errors = validar_publicacion(data)
    if errors:
        return error("DATOS_INVALIDOS", "Revisa los datos enviados.", 422, errors)
    cursor = _mysql.connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO publicaciones (titulo, contenido, imagen, tipo, estado) VALUES (%s, %s, %s, %s, %s)",
            (clean["titulo"], clean["contenido"], clean.get("imagen"), clean["tipo"], clean.get("estado", "activo")),
        )
        item_id = cursor.lastrowid
        _mysql.connection.commit()
    except IntegrityError:
        _mysql.connection.rollback()
        return error("CONFLICTO_DATOS", "La publicación no pudo registrarse por una restricción de datos.", 409)
    finally:
        cursor.close()
    item, _ = _obtener("publicaciones", PUBLICACION_COLS, item_id, "Publicación")
    return respuesta(item, "Publicación creada correctamente.", 201)


@api.route("/publicaciones/<int:item_id>", methods=["PUT", "PATCH"])
@requiere_token
def actualizar_publicacion(item_id):
    data, failure = _json_body()
    if failure:
        return failure
    clean, errors = validar_publicacion(data, partial=request.method == "PATCH")
    if errors:
        return error("DATOS_INVALIDOS", "Revisa los datos enviados.", 422, errors)
    return _actualizar("publicaciones", PUBLICACION_COLS, item_id, clean, "Publicación")


@api.delete("/publicaciones/<int:item_id>")
@requiere_token
def eliminar_publicacion(item_id):
    _, failure = _obtener("publicaciones", PUBLICACION_COLS, item_id, "Publicación")
    if failure:
        return failure
    cursor = _mysql.connection.cursor()
    cursor.execute("UPDATE publicaciones SET estado = 'inactivo' WHERE id = %s", (item_id,))
    _mysql.connection.commit()
    cursor.close()
    return respuesta(message="Publicación desactivada correctamente.")


@api.errorhandler(405)
def metodo_no_permitido(_error):
    return error("METODO_NO_PERMITIDO", "El método HTTP no está permitido para este endpoint.", 405)

