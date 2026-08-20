from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from MySQLdb import IntegrityError
from MySQLdb.cursors import DictCursor
import os
import requests
import secrets
import hashlib
import base64
import json
import html
import math
import re
import time
from urllib.parse import quote, urlencode


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY","huancayoga_clave_temporal_2026")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
    or bool(os.getenv("RENDER"))
)
app.config["APP_DEBUG"] = os.getenv("FLASK_DEBUG", "False").lower() == "true"

# Configuración de MySQL
app.config["MYSQL_HOST"] = os.getenv("DB_HOST")
app.config["MYSQL_USER"] = os.getenv("DB_USER")
app.config["MYSQL_PASSWORD"] = os.getenv("DB_PASSWORD")
app.config["MYSQL_DB"] = os.getenv("DB_NAME")
app.config["MYSQL_PORT"] = int(os.getenv("DB_PORT", 3306))

# Configuración de correo
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True") == "True"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

app.config["MAIL_ENABLED"] = os.getenv("MAIL_ENABLED", "False").lower() == "true"
app.config["EMAIL_PROVIDER"] = os.getenv("EMAIL_PROVIDER", "brevo")
app.config["BREVO_API_KEY"] = os.getenv("BREVO_API_KEY")
app.config["MAIL_TIMEOUT"] = 10

# Configuracion del chatbot con IA
app.config["CHATBOT_PROVIDER"] = os.getenv("CHATBOT_PROVIDER", "local").lower()
app.config["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
app.config["OPENAI_MODEL"] = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
app.config["OPENAI_TIMEOUT"] = int(os.getenv("OPENAI_TIMEOUT", 20))

# Alertas internas opcionales por correo
app.config["SYSTEM_ALERTS_ENABLED"] = os.getenv("SYSTEM_ALERTS_ENABLED", "False").lower() == "true"
app.config["SYSTEM_ALERT_EMAIL"] = os.getenv("SYSTEM_ALERT_EMAIL")
app.config["SYSTEM_ALERT_COOLDOWN_MINUTES"] = int(os.getenv("SYSTEM_ALERT_COOLDOWN_MINUTES", 30))

# Imágenes de productos: carga local y búsqueda opcional en Pexels
app.config["PRODUCT_UPLOAD_FOLDER"] = os.path.join(app.static_folder, "img", "productos")
app.config["PUBLICATION_UPLOAD_FOLDER"] = os.path.join(app.static_folder, "img", "publicaciones")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", 5)) * 1024 * 1024
app.config["PEXELS_API_KEY"] = os.getenv("PEXELS_API_KEY")
app.config["PEXELS_TIMEOUT"] = int(os.getenv("PEXELS_TIMEOUT", 12))

# Rutas y ubicación pública de Huancayoga
app.config["ORS_API_KEY"] = os.getenv("ORS_API_KEY")
app.config["ORS_TIMEOUT"] = int(os.getenv("ORS_TIMEOUT") or 15)
app.config["HUANCAYOGA_LAT"] = float(os.getenv("HUANCAYOGA_LAT") or -12.055280)
app.config["HUANCAYOGA_LON"] = float(os.getenv("HUANCAYOGA_LON") or -75.203375)

# Seguridad, acceso social y agenda externa
app.config["APP_BASE_URL"] = (os.getenv("APP_BASE_URL") or "").rstrip("/")
app.config["OAUTH_TIMEOUT"] = int(os.getenv("OAUTH_TIMEOUT") or 12)
app.config["OAUTH_TOKEN_ENCRYPTION_KEY"] = (
    os.getenv("OAUTH_TOKEN_ENCRYPTION_KEY") or app.secret_key
)
app.config["TURNSTILE_ENABLED"] = os.getenv("TURNSTILE_ENABLED", "False").lower() == "true"
app.config["TURNSTILE_SITE_KEY"] = os.getenv("TURNSTILE_SITE_KEY")
app.config["TURNSTILE_SECRET_KEY"] = os.getenv("TURNSTILE_SECRET_KEY")
app.config["TURNSTILE_EXPECTED_HOSTNAME"] = os.getenv("TURNSTILE_EXPECTED_HOSTNAME")
app.config["TURNSTILE_TIMEOUT"] = int(os.getenv("TURNSTILE_TIMEOUT") or 8)
app.config["GOOGLE_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID")
app.config["GOOGLE_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET")
app.config["GOOGLE_CALENDAR_ID"] = os.getenv("GOOGLE_CALENDAR_ID") or "primary"
app.config["FACEBOOK_APP_ID"] = os.getenv("FACEBOOK_APP_ID")
app.config["FACEBOOK_APP_SECRET"] = os.getenv("FACEBOOK_APP_SECRET")
app.config["FACEBOOK_GRAPH_VERSION"] = os.getenv("FACEBOOK_GRAPH_VERSION")
app.config["TIKTOK_CLIENT_KEY"] = os.getenv("TIKTOK_CLIENT_KEY")
app.config["TIKTOK_CLIENT_SECRET"] = os.getenv("TIKTOK_CLIENT_SECRET")

mail = Mail(app)

mysql = MySQL(app)

ultima_alerta_sistema = {}
cache_rutas_huancayoga = {}
solicitudes_ruta_por_ip = {}

PROVEEDORES_SOCIALES = {
    "google": "Google",
    "facebook": "Facebook",
    "tiktok": "TikTok",
}

EXTENSIONES_IMAGEN_PERMITIDAS = {"jpg", "jpeg", "png", "webp"}
FIRMAS_IMAGEN = {
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "webp": (b"RIFF",),
}


def archivo_imagen_valido(archivo, extension):
    posicion = archivo.stream.tell()
    cabecera = archivo.stream.read(16)
    archivo.stream.seek(posicion)

    if extension == "webp":
        return cabecera.startswith(b"RIFF") and cabecera[8:12] == b"WEBP"

    return any(cabecera.startswith(firma) for firma in FIRMAS_IMAGEN[extension])


def guardar_imagen_producto(archivo):
    if not archivo or not archivo.filename:
        return None

    nombre_seguro = secure_filename(archivo.filename)
    extension = nombre_seguro.rsplit(".", 1)[-1].lower() if "." in nombre_seguro else ""

    if extension not in EXTENSIONES_IMAGEN_PERMITIDAS:
        raise ValueError("Formato no permitido. Usa JPG, PNG o WebP.")

    if not archivo_imagen_valido(archivo, extension):
        raise ValueError("El archivo seleccionado no contiene una imagen válida.")

    os.makedirs(app.config["PRODUCT_UPLOAD_FOLDER"], exist_ok=True)
    base = os.path.splitext(nombre_seguro)[0][:70] or "producto"
    nombre_final = f"{base}-{secrets.token_hex(6)}.{extension}"
    archivo.save(os.path.join(app.config["PRODUCT_UPLOAD_FOLDER"], nombre_final))
    return nombre_final


def guardar_imagen_publicacion(archivo):
    if not archivo or not archivo.filename:
        return None

    nombre_seguro = secure_filename(archivo.filename)
    extension = nombre_seguro.rsplit(".", 1)[-1].lower() if "." in nombre_seguro else ""

    if extension not in EXTENSIONES_IMAGEN_PERMITIDAS:
        raise ValueError("Formato no permitido. Usa JPG, PNG o WebP.")

    if not archivo_imagen_valido(archivo, extension):
        raise ValueError("El archivo seleccionado no contiene una imagen válida.")

    os.makedirs(app.config["PUBLICATION_UPLOAD_FOLDER"], exist_ok=True)
    base = os.path.splitext(nombre_seguro)[0][:70] or "publicacion"
    nombre_final = f"{base}-{secrets.token_hex(6)}.{extension}"
    archivo.save(os.path.join(app.config["PUBLICATION_UPLOAD_FOLDER"], nombre_final))
    return nombre_final


def normalizar_imagen_seleccionada(referencia):
    referencia = (referencia or "").strip()

    if not referencia:
        return ""

    if referencia.startswith("https://images.pexels.com/"):
        if len(referencia) > 255:
            raise ValueError("La dirección de la imagen seleccionada es demasiado larga.")
        return referencia

    if referencia.startswith(("http://", "https://")):
        raise ValueError("Selecciona una imagen obtenida desde el buscador de Pexels.")

    return secure_filename(os.path.basename(referencia))


def generar_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)

    return session["_csrf_token"]


@app.context_processor
def inyectar_csrf_token():
    return {"csrf_token": generar_csrf_token}


def csrf_valido():
    token_session = session.get("_csrf_token")
    token_formulario = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")

    return (
        bool(token_session)
        and bool(token_formulario)
        and secrets.compare_digest(token_session, token_formulario)
    )


def url_externa_segura(endpoint, **valores):
    ruta = url_for(endpoint, **valores)
    base_url = app.config.get("APP_BASE_URL")

    if base_url:
        return f"{base_url}{ruta}"

    esquema = "https" if os.getenv("RENDER") else request.scheme
    return url_for(endpoint, _external=True, _scheme=esquema, **valores)


def turnstile_configurado():
    return bool(
        app.config.get("TURNSTILE_ENABLED")
        and app.config.get("TURNSTILE_SITE_KEY")
        and app.config.get("TURNSTILE_SECRET_KEY")
    )


def validar_turnstile():
    if not app.config.get("TURNSTILE_ENABLED"):
        return True, None

    secret_key = app.config.get("TURNSTILE_SECRET_KEY")
    site_key = app.config.get("TURNSTILE_SITE_KEY")

    if not secret_key or not site_key:
        return False, "La protección anti-bots todavía no está configurada."

    token = (request.form.get("cf-turnstile-response") or "").strip()

    if not token or len(token) > 2048:
        return False, "Completa la verificación de seguridad."

    try:
        respuesta = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": secret_key,
                "response": token,
                "remoteip": ip_cliente_actual(),
                "idempotency_key": secrets.token_hex(16),
            },
            timeout=app.config.get("TURNSTILE_TIMEOUT", 8),
        )
        respuesta.raise_for_status()
        resultado = respuesta.json()
    except (requests.RequestException, ValueError) as error:
        enviar_alerta_sistema("turnstile", "Turnstile no pudo validarse", error)
        return False, "No pudimos completar la verificación de seguridad. Intenta nuevamente."

    if not resultado.get("success"):
        return False, "La verificación de seguridad venció o no fue válida. Intenta nuevamente."

    hostname_esperado = app.config.get("TURNSTILE_EXPECTED_HOSTNAME")

    if hostname_esperado and resultado.get("hostname") != hostname_esperado:
        enviar_alerta_sistema(
            "turnstile-hostname",
            "Turnstile respondió desde un dominio inesperado",
            resultado.get("hostname"),
        )
        return False, "La verificación de seguridad no corresponde a este sitio."

    return True, None


def proveedor_social_configurado(proveedor):
    configuraciones = {
        "google": (
            app.config.get("GOOGLE_CLIENT_ID"),
            app.config.get("GOOGLE_CLIENT_SECRET"),
        ),
        "facebook": (
            app.config.get("FACEBOOK_APP_ID"),
            app.config.get("FACEBOOK_APP_SECRET"),
            app.config.get("FACEBOOK_GRAPH_VERSION"),
        ),
        "tiktok": (
            app.config.get("TIKTOK_CLIENT_KEY"),
            app.config.get("TIKTOK_CLIENT_SECRET"),
        ),
    }
    return proveedor in configuraciones and all(configuraciones[proveedor])


def contexto_seguridad_acceso():
    return {
        "turnstile_enabled": turnstile_configurado(),
        "turnstile_requested": app.config.get("TURNSTILE_ENABLED", False),
        "turnstile_site_key": app.config.get("TURNSTILE_SITE_KEY"),
        "proveedores_sociales": {
            proveedor: {
                "nombre": nombre,
                "configurado": proveedor_social_configurado(proveedor),
            }
            for proveedor, nombre in PROVEEDORES_SOCIALES.items()
        },
    }


@app.before_request
def proteger_post_con_csrf():
    rutas_excluidas = {"api_chatbot", "api_ruta_huancayoga"}

    if request.method == "POST" and request.endpoint not in rutas_excluidas:
        if not csrf_valido():
            flash("La solicitud no pudo validarse. Intenta nuevamente.", "danger")
            return redirect(request.referrer or url_for("index"))


@app.errorhandler(413)
def archivo_demasiado_grande(error):
    flash(
        f"La imagen supera el límite de {os.getenv('MAX_UPLOAD_MB', '5')} MB.",
        "danger"
    )
    return redirect(request.referrer or url_for("admin_productos"))


def enviar_alerta_sistema(clave, asunto, detalle):
    if not app.config.get("SYSTEM_ALERTS_ENABLED"):
        return False

    destinatario = app.config.get("SYSTEM_ALERT_EMAIL")

    if not destinatario:
        return False

    ahora = datetime.now()
    cooldown = timedelta(minutes=app.config.get("SYSTEM_ALERT_COOLDOWN_MINUTES", 30))
    ultima_alerta = ultima_alerta_sistema.get(clave)

    if ultima_alerta and ahora - ultima_alerta < cooldown:
        return False

    ultima_alerta_sistema[clave] = ahora
    detalle_seguro = html.escape(str(detalle))

    contenido = f"""
    <div style="font-family: Arial, sans-serif; background:#faf7f0; padding:24px;">
        <div style="max-width:640px; margin:auto; background:white; border-radius:12px; padding:24px;">
            <h2 style="color:#315545;">Alerta del sistema Huancayoga</h2>
            <p><strong>{html.escape(asunto)}</strong></p>
            <pre style="white-space:pre-wrap; background:#f4f4f4; padding:12px; border-radius:8px;">{detalle_seguro}</pre>
        </div>
    </div>
    """

    return enviar_correo(destinatario, asunto, contenido)


def password_admin_es_hash(password_guardado):
    return password_guardado.startswith(("scrypt:", "pbkdf2:", "argon2:"))


def password_admin_valido(password_guardado, password_ingresado):
    if password_admin_es_hash(password_guardado):
        return check_password_hash(password_guardado, password_ingresado)

    return secrets.compare_digest(password_guardado, password_ingresado)


# funciones
def correo_recuperar_password(nombre, enlace):
    return f"""
    <div style="font-family: Arial, sans-serif; background-color:#f6f2ea; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; padding:30px; border-radius:18px;">
            <h2 style="color:#0b8f5a;">Recupera tu contraseña</h2>

            <p>Hola {nombre},</p>

            <p>
                Recibimos una solicitud para restablecer tu contraseña
                en el sistema de Huancayoga.
            </p>

            <p>
                Haz clic en el siguiente botón para crear una nueva contraseña:
            </p>

            <p style="text-align:center; margin:30px 0;">
                <a href="{enlace}"
                   style="background:#0b8f5a; color:white; padding:14px 24px;
                          text-decoration:none; border-radius:10px;">
                    Restablecer contraseña
                </a>
            </p>

            <p>
                Este enlace vencerá en 30 minutos.
            </p>

            <p style="color:#777;">
                Si tú no solicitaste este cambio, puedes ignorar este mensaje.
            </p>
        </div>
    </div>
    """

def enviar_correo(destinatario, asunto, contenido_html):
    if not destinatario:
        print("Correo omitido: destinatario vacío.")
        return False

    if not app.config.get("MAIL_ENABLED", False):
        print(f"Correo omitido para {destinatario}: MAIL_ENABLED está desactivado.")
        return False

    if app.config.get("EMAIL_PROVIDER") != "brevo":
        print("Proveedor de correo no configurado como Brevo.")
        return False

    api_key = app.config.get("BREVO_API_KEY")

    if not api_key:
        print("No se encontró BREVO_API_KEY.")
        return False

    url = "https://api.brevo.com/v3/smtp/email"

    payload = {
       "sender": {
                "name": "Huancayoga",
                "email": "contacto@huancayoga.dpdns.org"
            },
        "to": [
            {
                "email": destinatario
            }
        ],
        "subject": asunto,
        "htmlContent": contenido_html
    }

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    try:
        respuesta = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=15
        )

        if respuesta.status_code in [200, 201, 202]:
            print(f"Correo enviado correctamente con Brevo a {destinatario}")
            return True

        print("Brevo no pudo enviar el correo.")
        print("Status:", respuesta.status_code)
        print("Respuesta:", respuesta.text)
        return False

    except Exception as e:
        print(f"Error al enviar correo con Brevo: {e}")
        return False
    
def correo_bienvenida(nombre):
    return f"""
    <div style="font-family: Arial, sans-serif; background:#faf7f0; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:18px; padding:30px;">
            <h1 style="color:#315545;">Bienvenido a Huancayoga 🌿</h1>
            <p>Hola <strong>{nombre}</strong>,</p>
            <p>
                Gracias por registrarte en Huancayoga, un espacio creado para la relajación,
                el bienestar y la conexión contigo mismo.
            </p>
            <p>
                Desde ahora podrás reservar citas, ver productos y recibir novedades especiales.
            </p>
            <p style="color:#5f9274; font-weight:bold;">
                Respira, conecta y empieza tu camino de bienestar.
            </p>
            <hr>
            <p style="font-size:13px; color:#777;">Huancayoga - Huancayo, Perú</p>
        </div>
    </div>
    """

def correo_nuevo_producto(nombre_producto, descripcion, precio):
    return f"""
    <div style="font-family: Arial, sans-serif; background:#faf7f0; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:18px; padding:30px;">
            <h1 style="color:#315545;">Nuevo producto en Huancayoga 🛍️</h1>
            <p>Tenemos un nuevo producto disponible para ti:</p>

            <h2 style="color:#5f9274;">{nombre_producto}</h2>
            <p>{descripcion}</p>
            <p><strong>Precio:</strong> S/ {precio}</p>

            <p>
                Ingresa al sistema para verlo y realizar tu pedido.
            </p>

            <p style="color:#5f9274; font-weight:bold;">
                Gracias por formar parte de Huancayoga.
            </p>
        </div>
    </div>
    """

def correo_nueva_publicacion(titulo, contenido):
    return f"""
    <div style="font-family: Arial, sans-serif; background:#faf7f0; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:18px; padding:30px;">
            <h1 style="color:#315545;">Nueva inspiración de Huancayoga ✨</h1>

            <h2 style="color:#5f9274;">{titulo}</h2>

            <p>{contenido}</p>

            <p>
                Te invitamos a ingresar al sistema y conocer más sobre el trabajo,
                mensajes y momentos de Huancayoga.
            </p>

            <p style="color:#5f9274; font-weight:bold;">
                Que tengas un día lleno de calma y energía.
            </p>
        </div>
    </div>
    """

def correo_confirmacion_cita(nombre, servicio, fecha, hora, cantidad_personas=1):
    return f"""
    <div style="font-family: Arial, sans-serif; background:#faf7f0; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:18px; padding:30px;">
            <h1 style="color:#315545;">Tu cita fue confirmada ✅</h1>

            <p>Hola <strong>{nombre}</strong>,</p>

            <p>Tu cita en Huancayoga ha sido confirmada.</p>

            <ul>
                <li><strong>Servicio:</strong> {servicio}</li>
                <li><strong>Personas:</strong> {cantidad_personas}</li>
                <li><strong>Fecha:</strong> {fecha}</li>
                <li><strong>Hora:</strong> {hora}</li>
            </ul>

            <p>
                Te esperamos para compartir un momento de bienestar, respiración y relajación.
            </p>

            <p style="color:#5f9274; font-weight:bold;">
                Gracias por confiar en Huancayoga.
            </p>
        </div>
    </div>
    """

def correo_recordatorio_cita(nombre, servicio, fecha, hora, cantidad_personas=1):
    return f"""
    <div style="font-family: Arial, sans-serif; background:#faf7f0; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:18px; padding:30px;">
            <h1 style="color:#315545;">Recordatorio de tu cita 🌿</h1>

            <p>Hola <strong>{nombre}</strong>,</p>

            <p>Te recordamos que tienes una cita programada en Huancayoga.</p>

            <ul>
                <li><strong>Servicio:</strong> {servicio}</li>
                <li><strong>Personas:</strong> {cantidad_personas}</li>
                <li><strong>Fecha:</strong> {fecha}</li>
                <li><strong>Hora:</strong> {hora}</li>
            </ul>

            <p>
                Recuerda asistir con ropa cómoda y llegar unos minutos antes.
            </p>

            <p style="color:#5f9274; font-weight:bold;">
                Te esperamos con mucha energía positiva.
            </p>
        </div>
    </div>
    """

def correo_pedido_registrado(nombre, producto, cantidad, total):
    return f"""
    <div style="font-family: Arial, sans-serif; background:#faf7f0; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:18px; padding:30px;">
            <h1 style="color:#315545;">Pedido registrado correctamente 🛒</h1>

            <p>Hola <strong>{nombre}</strong>,</p>

            <p>Tu pedido fue registrado en el sistema de Huancayoga.</p>

            <ul>
                <li><strong>Producto:</strong> {producto}</li>
                <li><strong>Cantidad:</strong> {cantidad}</li>
                <li><strong>Total:</strong> S/ {total}</li>
            </ul>

            <p>
                La dueña se comunicará contigo para coordinar el pago y la entrega.
            </p>

            <p style="color:#5f9274; font-weight:bold;">
                Gracias por apoyar Huancayoga.
            </p>
        </div>
    </div>
    """


PERFILES_RUTA_ORS = {
    "walking": "foot-walking",
    "cycling": "cycling-regular",
    "driving": "driving-car",
}


def distancia_haversine_km(latitud_origen, longitud_origen, latitud_destino, longitud_destino):
    radio_tierra_km = 6371.0088
    latitud_1 = math.radians(latitud_origen)
    latitud_2 = math.radians(latitud_destino)
    diferencia_latitud = math.radians(latitud_destino - latitud_origen)
    diferencia_longitud = math.radians(longitud_destino - longitud_origen)

    calculo = (
        math.sin(diferencia_latitud / 2) ** 2
        + math.cos(latitud_1)
        * math.cos(latitud_2)
        * math.sin(diferencia_longitud / 2) ** 2
    )
    calculo = min(1, max(0, calculo))
    return radio_tierra_km * 2 * math.atan2(math.sqrt(calculo), math.sqrt(1 - calculo))


def ip_cliente_actual():
    encabezado_proxy = request.headers.get("X-Forwarded-For", "")
    return encabezado_proxy.split(",")[0].strip() or request.remote_addr or "desconocida"


def solicitud_ruta_permitida():
    ahora = time.monotonic()
    ventana_segundos = 60
    limite_por_minuto = 20
    ip_cliente = ip_cliente_actual()
    historial = [
        instante
        for instante in solicitudes_ruta_por_ip.get(ip_cliente, [])
        if ahora - instante < ventana_segundos
    ]

    if len(historial) >= limite_por_minuto:
        solicitudes_ruta_por_ip[ip_cliente] = historial
        return False

    historial.append(ahora)
    solicitudes_ruta_por_ip[ip_cliente] = historial

    if len(solicitudes_ruta_por_ip) > 500:
        inactivos = [
            ip
            for ip, instantes in solicitudes_ruta_por_ip.items()
            if not instantes or ahora - instantes[-1] >= ventana_segundos
        ]
        for ip in inactivos:
            solicitudes_ruta_por_ip.pop(ip, None)

    return True


@app.route("/")
def index():
    return render_template("public/index.html")


@app.route("/como-llegar")
def como_llegar():
    return render_template(
        "public/como_llegar.html",
        huancayoga_lat=app.config["HUANCAYOGA_LAT"],
        huancayoga_lon=app.config["HUANCAYOGA_LON"],
    )


@app.route("/api/rutas/huancayoga", methods=["POST"])
def api_ruta_huancayoga():
    datos = request.get_json(silent=True) or {}
    modo = str(datos.get("modo", "")).strip().lower()

    if modo not in PERFILES_RUTA_ORS:
        return {
            "ok": False,
            "mensaje": "Selecciona caminata, bicicleta o automóvil.",
        }, 400

    try:
        latitud = float(datos.get("latitud"))
        longitud = float(datos.get("longitud"))
    except (TypeError, ValueError):
        return {
            "ok": False,
            "mensaje": "No pudimos leer tu ubicación actual.",
        }, 400

    if (
        not math.isfinite(latitud)
        or not math.isfinite(longitud)
        or not -90 <= latitud <= 90
        or not -180 <= longitud <= 180
    ):
        return {
            "ok": False,
            "mensaje": "Las coordenadas recibidas no son válidas.",
        }, 400

    destino_latitud = app.config["HUANCAYOGA_LAT"]
    destino_longitud = app.config["HUANCAYOGA_LON"]
    distancia_directa = distancia_haversine_km(
        latitud,
        longitud,
        destino_latitud,
        destino_longitud,
    )

    if distancia_directa > 500:
        return {
            "ok": False,
            "mensaje": "Para recorridos mayores a 500 km, abre la ruta directamente en Google Maps.",
        }, 400

    clave_ors = app.config.get("ORS_API_KEY")
    if not clave_ors:
        return {
            "ok": False,
            "mensaje": "El servicio de rutas aún no está configurado.",
        }, 503

    ahora = time.monotonic()
    clave_cache = (round(latitud, 4), round(longitud, 4), modo)
    ruta_guardada = cache_rutas_huancayoga.get(clave_cache)

    if ruta_guardada and ahora - ruta_guardada["creada"] < 90:
        return {"ok": True, "ruta": ruta_guardada["ruta"], "cache": True}

    if not solicitud_ruta_permitida():
        return {
            "ok": False,
            "mensaje": "Se realizaron demasiadas consultas. Espera un minuto e inténtalo nuevamente.",
        }, 429

    perfil_ors = PERFILES_RUTA_ORS[modo]

    try:
        respuesta = requests.post(
            f"https://api.openrouteservice.org/v2/directions/{perfil_ors}/geojson",
            headers={
                "Authorization": clave_ors,
                "Content-Type": "application/json",
                "Accept": "application/geo+json, application/json",
            },
            json={
                "coordinates": [
                    [longitud, latitud],
                    [destino_longitud, destino_latitud],
                ],
                "instructions": True,
                "language": "es",
            },
            timeout=app.config["ORS_TIMEOUT"],
        )

        if respuesta.status_code in (401, 403):
            print("OpenRouteService rechazó la credencial configurada.")
            return {
                "ok": False,
                "mensaje": "El servicio de rutas necesita ser configurado nuevamente.",
            }, 503

        if respuesta.status_code == 429:
            return {
                "ok": False,
                "mensaje": "El servicio de rutas alcanzó temporalmente su límite. Intenta en unos minutos.",
            }, 429

        respuesta.raise_for_status()
        contenido = respuesta.json()
        elementos = contenido.get("features") or []

        if not elementos:
            return {
                "ok": False,
                "mensaje": "No encontramos una ruta disponible desde tu ubicación.",
            }, 404

        elemento = elementos[0]
        propiedades = elemento.get("properties") or {}
        resumen = propiedades.get("summary") or {}
        segmentos = propiedades.get("segments") or []
        pasos = segmentos[0].get("steps", []) if segmentos else []

        ruta = {
            "geometria": elemento.get("geometry"),
            "distancia_m": round(float(resumen.get("distance", 0)), 1),
            "duracion_s": round(float(resumen.get("duration", 0)), 1),
            "modo": modo,
            "destino": {
                "latitud": destino_latitud,
                "longitud": destino_longitud,
            },
            "instrucciones": [
                {
                    "texto": str(paso.get("instruction") or "Continúa por la ruta indicada."),
                    "distancia_m": round(float(paso.get("distance", 0)), 1),
                    "duracion_s": round(float(paso.get("duration", 0)), 1),
                }
                for paso in pasos
            ],
        }

        cache_rutas_huancayoga[clave_cache] = {
            "creada": ahora,
            "ruta": ruta,
        }
        return {"ok": True, "ruta": ruta, "cache": False}

    except requests.Timeout:
        return {
            "ok": False,
            "mensaje": "El cálculo de la ruta está tardando demasiado. Intenta nuevamente.",
        }, 504
    except (requests.RequestException, ValueError, TypeError, KeyError) as error:
        print(f"Error al consultar OpenRouteService: {error}")
        return {
            "ok": False,
            "mensaje": "No pudimos calcular la ruta en este momento.",
        }, 502


@app.route("/check-db")
def check_db():
    if "admin_id" not in session and os.getenv("CHECK_DB_PUBLIC", "False").lower() != "true":
        abort(404)

    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT DATABASE();")
        db = cur.fetchone()
        cur.close()
        return {
            "mensaje": "Conexión correcta a MySQL",
            "base_de_datos": db[0]
        }
    except Exception as e:
        return {
            "mensaje": "Error al conectar con MySQL",
            "error": str(e)
        }


# ==========================
# MÓDULO DE RESERVAS
# ==========================

MAX_ASISTENTES_RESERVA = 40
INTERVALO_AGENDA_MINUTOS = 15
HORA_INICIO_AGENDA = 7
HORA_FIN_AGENDA = 20
DURACIONES_PROGRAMA = (45, 60, 90, 120)
HORAS_RESERVA = tuple(
    (datetime(2000, 1, 1, HORA_INICIO_AGENDA) + timedelta(minutes=minutos)).strftime("%H:%M")
    for minutos in range(
        0,
        (HORA_FIN_AGENDA - HORA_INICIO_AGENDA) * 60 + 1,
        INTERVALO_AGENDA_MINUTOS,
    )
)
CATEGORIAS_PROGRAMA = {
    "colegio": "Colegio",
    "instituto": "Instituto",
    "universidad": "Universidad",
    "corporativo": "Programa corporativo para empresas",
    "ninos": "Yoga para niños",
    "adultos_mayores": "Yoga para adultos mayores",
    "inclusivo_adaptado": "Yoga inclusivo o adaptado",
    "asociacion_familiar": "Asociación o grupo familiar",
    "otro": "Otro grupo",
}


def bloques_de_horario(fecha, hora, duracion_minutos):
    inicio = datetime.combine(fecha, hora)
    fin = inicio + timedelta(minutes=duracion_minutos)
    bloques = []
    bloque = inicio

    while bloque < fin:
        bloques.append((fecha, bloque.time()))
        bloque += timedelta(minutes=INTERVALO_AGENDA_MINUTOS)

    return bloques


def correo_reserva_valido(correo):
    if not correo:
        return True

    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", correo))


def telefono_reserva_valido(telefono):
    digitos = re.sub(r"\D", "", telefono or "")
    return 7 <= len(digitos) <= 15


def texto_reserva(formulario, campo, maximo, obligatorio=False):
    valor = (formulario.get(campo) or "").strip()

    if obligatorio and not valor:
        raise ValueError(f"El campo {campo.replace('_', ' ')} es obligatorio.")

    if len(valor) > maximo:
        raise ValueError(f"El campo {campo.replace('_', ' ')} es demasiado largo.")

    return valor


def hora_reserva(valor):
    valor = (valor or "").strip()

    for formato in ("%H:%M", "%H:%M:%S", "%H:%M:%S.%f"):
        try:
            return datetime.strptime(valor, formato).time()
        except ValueError:
            continue

    raise ValueError("Hora de reserva no válida.")


def google_calendar_configurado():
    return bool(
        app.config.get("GOOGLE_CLIENT_ID")
        and app.config.get("GOOGLE_CLIENT_SECRET")
        and app.config.get("OAUTH_TOKEN_ENCRYPTION_KEY")
    )


def guardar_integracion_google_calendar(datos_token, cuenta_email):
    access_token = datos_token.get("access_token")
    refresh_token = datos_token.get("refresh_token")

    if not access_token or not refresh_token:
        raise ValueError("Google no devolvió acceso permanente al calendario.")

    expira_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        seconds=max(60, int(datos_token.get("expires_in", 3600)))
    )
    clave = app.config["OAUTH_TOKEN_ENCRYPTION_KEY"]
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO integraciones_oauth
        (
            proveedor,
            cuenta_email,
            access_token_cifrado,
            refresh_token_cifrado,
            token_expira_at,
            scopes,
            recurso_id,
            estado
        )
        VALUES (
            'google_calendar',
            %s,
            AES_ENCRYPT(%s, UNHEX(SHA2(%s, 512))),
            AES_ENCRYPT(%s, UNHEX(SHA2(%s, 512))),
            %s,
            %s,
            %s,
            'activo'
        )
        ON DUPLICATE KEY UPDATE
            cuenta_email = VALUES(cuenta_email),
            access_token_cifrado = VALUES(access_token_cifrado),
            refresh_token_cifrado = VALUES(refresh_token_cifrado),
            token_expira_at = VALUES(token_expira_at),
            scopes = VALUES(scopes),
            recurso_id = VALUES(recurso_id),
            estado = 'activo'
    """, (
        cuenta_email,
        access_token,
        clave,
        refresh_token,
        clave,
        expira_at,
        datos_token.get("scope", ""),
        app.config.get("GOOGLE_CALENDAR_ID", "primary"),
    ))
    mysql.connection.commit()
    cur.close()


def cargar_integracion_google_calendar(incluir_tokens=False):
    clave = app.config.get("OAUTH_TOKEN_ENCRYPTION_KEY")
    cur = mysql.connection.cursor(DictCursor)

    if incluir_tokens:
        cur.execute("""
            SELECT
                proveedor,
                cuenta_email,
                CONVERT(
                    AES_DECRYPT(access_token_cifrado, UNHEX(SHA2(%s, 512)))
                    USING utf8mb4
                ) AS access_token,
                CONVERT(
                    AES_DECRYPT(refresh_token_cifrado, UNHEX(SHA2(%s, 512)))
                    USING utf8mb4
                ) AS refresh_token,
                token_expira_at,
                scopes,
                recurso_id,
                estado,
                conectado_at,
                actualizado_at
            FROM integraciones_oauth
            WHERE proveedor = 'google_calendar'
        """, (clave, clave))
    else:
        cur.execute("""
            SELECT
                proveedor,
                cuenta_email,
                token_expira_at,
                scopes,
                recurso_id,
                estado,
                conectado_at,
                actualizado_at
            FROM integraciones_oauth
            WHERE proveedor = 'google_calendar'
        """)

    integracion = cur.fetchone()
    cur.close()
    return integracion


def token_google_calendar(forzar_actualizacion=False):
    if not google_calendar_configurado():
        return None, "Las credenciales OAuth de Google no están configuradas."

    integracion = cargar_integracion_google_calendar(incluir_tokens=True)

    if not integracion:
        return None, "La dueña todavía no conectó Google Calendar."

    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    if (
        not forzar_actualizacion
        and integracion["access_token"]
        and integracion["token_expira_at"] > ahora + timedelta(seconds=90)
    ):
        return integracion["access_token"], None

    if not integracion["refresh_token"]:
        return None, "Google Calendar necesita volver a autorizarse."

    try:
        respuesta = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": app.config["GOOGLE_CLIENT_ID"],
                "client_secret": app.config["GOOGLE_CLIENT_SECRET"],
                "refresh_token": integracion["refresh_token"],
                "grant_type": "refresh_token",
            },
            timeout=app.config.get("OAUTH_TIMEOUT", 12),
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
        nuevo_token = datos.get("access_token")
        if not nuevo_token:
            raise ValueError("Google no devolvió un nuevo access token.")
    except (requests.RequestException, ValueError, TypeError) as error:
        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE integraciones_oauth
            SET estado = 'error'
            WHERE proveedor = 'google_calendar'
        """)
        mysql.connection.commit()
        cur.close()
        enviar_alerta_sistema("google-calendar-token", "No se pudo renovar Google Calendar", error)
        return None, "No se pudo renovar el acceso a Google Calendar."

    expira_at = ahora + timedelta(seconds=max(60, int(datos.get("expires_in", 3600))))
    clave = app.config["OAUTH_TOKEN_ENCRYPTION_KEY"]
    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE integraciones_oauth
        SET access_token_cifrado = AES_ENCRYPT(%s, UNHEX(SHA2(%s, 512))),
            token_expira_at = %s,
            estado = 'activo'
        WHERE proveedor = 'google_calendar'
    """, (nuevo_token, clave, expira_at))
    mysql.connection.commit()
    cur.close()
    return nuevo_token, None


def datos_evento_reserva(reserva_id, estado_forzado=None):
    cur = mysql.connection.cursor(DictCursor)
    cur.execute("""
        SELECT
            r.id,
            r.nombre_cliente,
            r.celular,
            r.correo,
            r.fecha,
            r.hora,
            r.duracion_minutos,
            r.cantidad_personas,
            r.tipo_reserva,
            r.tipo_lugar,
            r.direccion_externa,
            r.comentario,
            r.estado,
            s.nombre AS servicio,
            d.categoria,
            d.nombre_organizacion,
            d.rango_edad,
            d.necesidades_apoyo,
            ce.evento_id,
            ce.sync_estado
        FROM reservas r
        INNER JOIN servicios s ON s.id = r.servicio_id
        LEFT JOIN reserva_programa_detalles d ON d.reserva_id = r.id
        LEFT JOIN reserva_calendario_eventos ce
            ON ce.reserva_id = r.id
           AND ce.proveedor = 'google_calendar'
        WHERE r.id = %s
    """, (reserva_id,))
    reserva = cur.fetchone()
    cur.close()

    if reserva and estado_forzado:
        reserva["estado"] = estado_forzado

    return reserva


def payload_evento_google(reserva):
    inicio = datetime.combine(reserva["fecha"], (datetime.min + reserva["hora"]).time() if isinstance(reserva["hora"], timedelta) else reserva["hora"])
    fin = inicio + timedelta(minutes=reserva["duracion_minutos"])
    categoria = CATEGORIAS_PROGRAMA.get(reserva["categoria"], "Clase regular o grupal")
    organizacion = reserva["nombre_organizacion"] or reserva["nombre_cliente"]
    prefijo = "✓ " if reserva["estado"] == "atendida" else ""
    titulo = f"{prefijo}Huancayoga · {categoria if reserva['tipo_reserva'] == 'institucional' else reserva['servicio']}"
    lugar = (
        reserva["direccion_externa"]
        if reserva["tipo_lugar"] == "externo"
        else "Local de Huancayoga, Huancayo"
    )
    descripcion = [
        f"Reserva #{reserva['id']}",
        f"Modalidad: {'Programa privado o institucional' if reserva['tipo_reserva'] == 'institucional' else 'Clase regular o grupal'}",
        f"Organización/cliente: {organizacion}",
        f"Responsable: {reserva['nombre_cliente']}",
        f"Asistentes: {reserva['cantidad_personas']}/40",
        f"Teléfono: {reserva['celular']}",
    ]
    if reserva["correo"]:
        descripcion.append(f"Correo: {reserva['correo']}")
    if reserva["rango_edad"]:
        descripcion.append(f"Rango de edad: {reserva['rango_edad']}")
    if reserva["necesidades_apoyo"]:
        descripcion.append(f"Necesidades de apoyo: {reserva['necesidades_apoyo']}")
    if reserva["comentario"]:
        descripcion.append(f"Observaciones: {reserva['comentario']}")

    return {
        "summary": titulo[:1024],
        "description": "\n".join(descripcion),
        "location": lugar,
        "start": {"dateTime": inicio.isoformat(), "timeZone": "America/Lima"},
        "end": {"dateTime": fin.isoformat(), "timeZone": "America/Lima"},
        "extendedProperties": {
            "private": {
                "huancayoga_reserva_id": str(reserva["id"]),
                "huancayoga_estado": reserva["estado"],
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 60},
                {"method": "popup", "minutes": 24 * 60},
            ],
        },
    }


def guardar_estado_calendario(reserva_id, estado, evento_id=None, evento_url=None, error=None):
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO reserva_calendario_eventos
        (
            reserva_id,
            proveedor,
            evento_id,
            evento_url,
            sync_estado,
            ultimo_error,
            sincronizado_at
        )
        VALUES (%s, 'google_calendar', %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            evento_id = COALESCE(%s, evento_id),
            evento_url = COALESCE(%s, evento_url),
            sync_estado = %s,
            ultimo_error = %s,
            sincronizado_at = %s
    """, (
        reserva_id,
        evento_id,
        evento_url,
        estado,
        (error or "")[:500] or None,
        datetime.now() if estado in {"sincronizado", "eliminado"} else None,
        evento_id,
        evento_url,
        estado,
        (error or "")[:500] or None,
        datetime.now() if estado in {"sincronizado", "eliminado"} else None,
    ))
    mysql.connection.commit()
    cur.close()


def sincronizar_reserva_google_calendar(reserva_id, estado=None):
    reserva = datos_evento_reserva(reserva_id, estado_forzado=estado)

    if not reserva:
        return False, "No se encontró la reserva."

    if reserva["estado"] not in {"confirmada", "cancelada", "atendida"}:
        return False, "Solo se sincronizan reservas confirmadas, canceladas o atendidas."

    integracion = cargar_integracion_google_calendar()
    if not google_calendar_configurado() or not integracion:
        if reserva["estado"] == "confirmada":
            guardar_estado_calendario(reserva_id, "pendiente", error="Google Calendar no está conectado")
        return False, "Google Calendar todavía no está conectado."

    token, error_token = token_google_calendar()
    if not token:
        guardar_estado_calendario(reserva_id, "error", error=error_token)
        return False, error_token

    calendar_id = quote(integracion["recurso_id"], safe="")
    base_url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    evento_id = reserva["evento_id"]

    def solicitar(method, url, payload=None, access_token=None):
        return requests.request(
            method,
            url,
            json=payload,
            headers={"Authorization": f"Bearer {access_token or token}"},
            timeout=app.config.get("OAUTH_TIMEOUT", 12),
        )

    try:
        if reserva["estado"] == "cancelada":
            if not evento_id:
                guardar_estado_calendario(reserva_id, "eliminado")
                return True, None
            respuesta = solicitar("DELETE", f"{base_url}/{quote(evento_id, safe='')}")
            if respuesta.status_code == 401:
                token_nuevo, error_token = token_google_calendar(forzar_actualizacion=True)
                if not token_nuevo:
                    raise ValueError(error_token)
                respuesta = solicitar("DELETE", f"{base_url}/{quote(evento_id, safe='')}", access_token=token_nuevo)
            if respuesta.status_code not in {204, 404, 410}:
                respuesta.raise_for_status()
            guardar_estado_calendario(reserva_id, "eliminado", evento_id=evento_id)
            return True, None

        payload = payload_evento_google(reserva)
        if evento_id:
            respuesta = solicitar("PATCH", f"{base_url}/{quote(evento_id, safe='')}", payload)
            if respuesta.status_code in {404, 410}:
                evento_id = None
                respuesta = solicitar("POST", base_url, payload)
        else:
            respuesta = solicitar("POST", base_url, payload)

        if respuesta.status_code == 401:
            token_nuevo, error_token = token_google_calendar(forzar_actualizacion=True)
            if not token_nuevo:
                raise ValueError(error_token)
            url_reintento = f"{base_url}/{quote(evento_id, safe='')}" if evento_id else base_url
            metodo_reintento = "PATCH" if evento_id else "POST"
            respuesta = solicitar(metodo_reintento, url_reintento, payload, token_nuevo)

        respuesta.raise_for_status()
        datos_evento = respuesta.json()
        evento_id_respuesta = datos_evento.get("id")
        if not evento_id_respuesta:
            raise ValueError("Google Calendar no devolvió el identificador del evento.")
        evento_url = datos_evento.get("htmlLink")
        if evento_url and not evento_url.startswith((
            "https://calendar.google.com/",
            "https://www.google.com/calendar/",
        )):
            evento_url = None
        guardar_estado_calendario(
            reserva_id,
            "sincronizado",
            evento_id=evento_id_respuesta,
            evento_url=evento_url,
        )
        return True, None
    except (requests.RequestException, ValueError, TypeError) as error:
        detalle = str(error) or "Google Calendar rechazó la sincronización."
        guardar_estado_calendario(reserva_id, "error", evento_id=evento_id, error=detalle)
        enviar_alerta_sistema("google-calendar-sync", "Error al sincronizar una reserva", detalle)
        return False, "La reserva se guardó, pero Google Calendar quedó pendiente de sincronización."

@app.route("/reservar", methods=["GET", "POST"])
def reservar():
    if "cliente_id" not in session:
        flash(
            "Para reservar una cita primero debes registrarte o iniciar sesión.",
            "warning"
        )
        return redirect(url_for("cliente_login"))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombre, precio, duracion_minutos
        FROM servicios
        WHERE estado = 'activo'
        ORDER BY nombre
    """)

    servicios = cur.fetchall()

    cur.execute("""
        SELECT
            nombres,
            apellido_paterno,
            apellido_materno,
            celular,
            correo
        FROM clientes
        WHERE id = %s
          AND estado = 'activo'
    """, (session["cliente_id"],))

    fila_cliente = cur.fetchone()

    if fila_cliente is None:
        cur.close()
        session.pop("cliente_id", None)
        flash("Tu cuenta no está disponible. Inicia sesión nuevamente.", "warning")
        return redirect(url_for("cliente_login"))

    nombre_cliente_guardado = " ".join(
        parte for parte in fila_cliente[:3] if parte
    )
    cliente = {
        "nombre": nombre_cliente_guardado,
        "celular": fila_cliente[3] or "",
        "correo": fila_cliente[4] or "",
    }

    zona_horaria_peru = timezone(timedelta(hours=-5))
    fecha_minima = datetime.now(zona_horaria_peru).date()

    if request.method == "POST":
        cliente_id = session["cliente_id"]
        tipo_reserva = (request.form.get("tipo_reserva") or "regular").strip()
        prefijo = "institucion_" if tipo_reserva == "institucional" else ""
        errores = []

        if tipo_reserva not in {"regular", "institucional"}:
            errores.append("Selecciona una modalidad de reserva válida.")

        try:
            nombre_cliente = texto_reserva(
                request.form,
                f"{prefijo}nombre_cliente",
                100,
                obligatorio=True,
            )
            celular = texto_reserva(
                request.form,
                f"{prefijo}celular",
                20,
                obligatorio=True,
            )
            correo = texto_reserva(
                request.form,
                f"{prefijo}correo",
                100,
                obligatorio=tipo_reserva == "institucional",
            )
            comentario = texto_reserva(request.form, f"{prefijo}comentario", 2000)
        except ValueError as error:
            errores.append(str(error))
            nombre_cliente = celular = correo = comentario = ""

        if celular and not telefono_reserva_valido(celular):
            errores.append("Ingresa un teléfono válido de 7 a 15 dígitos.")

        if correo and not correo_reserva_valido(correo):
            errores.append("Ingresa un correo electrónico válido.")

        try:
            servicio_id = int(request.form.get(f"{prefijo}servicio_id", ""))
        except (TypeError, ValueError):
            servicio_id = None
            errores.append("Selecciona un servicio válido.")

        try:
            cantidad_personas = int(request.form.get(f"{prefijo}cantidad_personas", "1"))
        except (TypeError, ValueError):
            cantidad_personas = 0

        try:
            fecha = datetime.strptime(
                request.form.get(f"{prefijo}fecha", ""),
                "%Y-%m-%d",
            ).date()
        except (TypeError, ValueError):
            fecha = None
            errores.append("Selecciona una fecha válida.")

        try:
            hora = hora_reserva(request.form.get(f"{prefijo}hora", ""))
        except (TypeError, ValueError):
            hora = None
            errores.append("Selecciona una hora válida.")

        if not 1 <= cantidad_personas <= MAX_ASISTENTES_RESERVA:
            errores.append("La reserva debe incluir entre 1 y 40 asistentes en total.")

        servicio = next(
            (fila for fila in servicios if fila[0] == servicio_id),
            None,
        )

        if servicio is None:
            errores.append("El servicio seleccionado no está disponible.")

        if tipo_reserva == "institucional":
            try:
                duracion_minutos = int(request.form.get("institucion_duracion_minutos", ""))
            except (TypeError, ValueError):
                duracion_minutos = 0

            if duracion_minutos not in DURACIONES_PROGRAMA:
                errores.append("Selecciona una duración válida para el programa.")
        else:
            duracion_minutos = int(servicio[3]) if servicio else 0

        if not 15 <= duracion_minutos <= 240:
            errores.append("La duración del servicio no es válida para la agenda.")

        if fecha and fecha < fecha_minima:
            errores.append("No puedes reservar una fecha que ya pasó.")

        if hora and hora.strftime("%H:%M") not in HORAS_RESERVA:
            errores.append(
                "Selecciona un horario disponible entre las 07:00 y las 20:00, "
                "en intervalos de 15 minutos."
            )

        if fecha and hora and duracion_minutos:
            inicio = datetime.combine(fecha, hora)
            fin = inicio + timedelta(minutes=duracion_minutos)
            ahora_peru = datetime.now(zona_horaria_peru).replace(tzinfo=None)

            if inicio <= ahora_peru:
                errores.append("Selecciona una fecha y hora futuras.")

            if fin.date() != fecha:
                errores.append("La sesión debe terminar el mismo día en que comienza.")

        categoria = None
        nombre_organizacion = None
        rango_edad = None
        necesidades_apoyo = None

        if tipo_reserva == "institucional":
            categoria = (request.form.get("categoria") or "").strip()
            tipo_lugar = (request.form.get("tipo_lugar") or "local").strip()

            try:
                nombre_organizacion = texto_reserva(
                    request.form,
                    "nombre_organizacion",
                    150,
                    obligatorio=True,
                )
                direccion_externa = texto_reserva(
                    request.form,
                    "direccion_externa",
                    255,
                    obligatorio=tipo_lugar == "externo",
                )
                rango_edad = texto_reserva(request.form, "rango_edad", 80) or None
                necesidades_apoyo = texto_reserva(
                    request.form,
                    "necesidades_apoyo",
                    2000,
                ) or None
            except ValueError as error:
                errores.append(str(error))
                nombre_organizacion = nombre_organizacion or ""
                direccion_externa = None

            if categoria not in CATEGORIAS_PROGRAMA:
                errores.append("Selecciona el tipo de grupo o institución.")

            if tipo_lugar not in {"local", "externo"}:
                errores.append("Selecciona un lugar válido para la sesión.")

            if tipo_lugar == "externo" and len(direccion_externa or "") < 5:
                errores.append("Ingresa la dirección de las instalaciones del cliente.")

            if tipo_lugar == "local":
                direccion_externa = None
        else:
            tipo_lugar = "local"
            direccion_externa = None

        if errores:
            cur.close()
            for mensaje in dict.fromkeys(errores):
                flash(mensaje, "danger")
            return render_template(
                "reservar.html",
                servicios=servicios,
                fecha_minima=fecha_minima.isoformat(),
                cliente=cliente,
                categorias_programa=CATEGORIAS_PROGRAMA,
                duraciones_programa=DURACIONES_PROGRAMA,
                horas_reserva=HORAS_RESERVA,
                form_data=request.form,
            ), 400

        try:
            cur.execute("""
                INSERT INTO reservas
                (
                    cliente_id,
                    nombre_cliente,
                    celular,
                    correo,
                    servicio_id,
                    cantidad_personas,
                    fecha,
                    hora,
                    duracion_minutos,
                    tipo_lugar,
                    direccion_externa,
                    comentario,
                    estado,
                    tipo_reserva
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, 'pendiente', %s
                )
            """, (
                cliente_id,
                nombre_cliente,
                celular,
                correo,
                servicio_id,
                cantidad_personas,
                fecha,
                hora,
                duracion_minutos,
                tipo_lugar,
                direccion_externa,
                comentario,
                tipo_reserva,
            ))

            reserva_id = cur.lastrowid

            if tipo_reserva == "institucional":
                cur.execute("""
                    INSERT INTO reserva_programa_detalles
                    (
                        reserva_id,
                        categoria,
                        nombre_organizacion,
                        rango_edad,
                        necesidades_apoyo
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    reserva_id,
                    categoria,
                    nombre_organizacion,
                    rango_edad,
                    necesidades_apoyo,
                ))

            bloques = [
                (fecha_bloque, hora_bloque, reserva_id)
                for fecha_bloque, hora_bloque in bloques_de_horario(
                    fecha,
                    hora,
                    duracion_minutos,
                )
            ]
            cur.executemany("""
                INSERT INTO reserva_bloques_horario
                    (fecha, hora_bloque, reserva_id)
                VALUES (%s, %s, %s)
            """, bloques)

            mysql.connection.commit()
        except IntegrityError as error:
            mysql.connection.rollback()
            cur.close()

            if error.args and error.args[0] == 1062:
                flash(
                    "Ese horario se cruza con otra reserva activa. Elige otra hora o fecha.",
                    "warning",
                )
                return redirect(url_for("reservar"))

            raise

        cur.close()

        flash(
            "Solicitud registrada correctamente. Huancayoga revisará la disponibilidad y te confirmará.",
            "success"
        )

        return redirect(url_for("cliente_mis_citas"))

    cur.close()

    return render_template(
        "reservar.html",
        servicios=servicios,
        fecha_minima=fecha_minima.isoformat(),
        cliente=cliente,
        categorias_programa=CATEGORIAS_PROGRAMA,
        duraciones_programa=DURACIONES_PROGRAMA,
        horas_reserva=HORAS_RESERVA,
        form_data={},
    )


# ==========================
# MÓDULO DE PRODUCTOS
# ==========================

@app.route("/api/admin/productos/imagenes")
@app.route("/api/admin/publicaciones/imagenes")
def api_admin_imagenes_productos():
    if "admin_id" not in session:
        return {"ok": False, "mensaje": "Debes iniciar sesión como administradora."}, 401

    consulta = " ".join(request.args.get("q", "").split())[:160]

    if len(consulta) < 2:
        return {"ok": False, "mensaje": "Escribe el nombre o la descripción del producto."}, 400

    api_key = app.config.get("PEXELS_API_KEY")

    if not api_key:
        return {
            "ok": False,
            "mensaje": "La búsqueda de imágenes aún no está configurada. Agrega PEXELS_API_KEY al archivo .env."
        }, 503

    try:
        respuesta = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={
                "query": consulta,
                "per_page": 8,
                "orientation": "landscape",
                "locale": "es-ES"
            },
            timeout=app.config["PEXELS_TIMEOUT"]
        )

        if respuesta.status_code == 401:
            return {"ok": False, "mensaje": "La clave de Pexels no es válida."}, 502

        respuesta.raise_for_status()
        fotos = []

        for foto in respuesta.json().get("photos", []):
            imagen = foto.get("src", {}).get("large")
            miniatura = foto.get("src", {}).get("medium") or imagen

            if not imagen or not imagen.startswith("https://images.pexels.com/"):
                continue

            fotos.append({
                "id": foto.get("id"),
                "imagen": imagen,
                "miniatura": miniatura,
                "alt": foto.get("alt") or f"Imagen relacionada con {consulta}",
                "fotografo": foto.get("photographer") or "Pexels",
                "fotografo_url": foto.get("photographer_url"),
                "pexels_url": foto.get("url")
            })

        return {"ok": True, "imagenes": fotos}

    except requests.RequestException as error:
        print(f"Error al consultar Pexels: {error}")
        return {"ok": False, "mensaje": "No se pudo consultar Pexels en este momento."}, 502


@app.route("/productos")
def productos():
    if "cliente_id" not in session:
        flash("Para ver los productos primero debes registrarte o iniciar sesión.", "warning")
        return redirect(url_for("cliente_login"))
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombre, descripcion, precio, stock, imagen
        FROM productos
        WHERE estado = 'activo'
    """)

    productos = cur.fetchall()
    cur.close()

    return render_template("productos.html", productos=productos)


@app.route("/comprar/<int:id>", methods=["GET", "POST"])
def comprar(id):
    if "cliente_id" not in session:
        flash("Para comprar un producto primero debes registrarte o iniciar sesión.", "warning")
        return redirect(url_for("cliente_login"))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombre, descripcion, precio, stock, imagen
        FROM productos
        WHERE id = %s AND estado = 'activo'
    """, (id,))

    producto = cur.fetchone()

    if producto is None:
        cur.close()
        flash("El producto no existe o no está disponible.", "danger")
        return redirect(url_for("productos"))

    if request.method == "POST":
        nombre_cliente = request.form["nombre_cliente"]
        celular = request.form["celular"]
        cantidad = int(request.form["cantidad"])
        correo = request.form["correo"]

        precio = float(producto[3])
        stock = int(producto[4])

        if cantidad <= 0:
            flash("La cantidad debe ser mayor a 0.", "danger")
            cur.close()
            return redirect(url_for("comprar", id=id))

        if cantidad > stock:
            flash("No hay suficiente stock disponible.", "danger")
            cur.close()
            return redirect(url_for("comprar", id=id))

        total = precio * cantidad

        cliente_id = session["cliente_id"]
        cur.execute("""
            INSERT INTO pedidos
            (
                cliente_id,
                 nombre_cliente,
                celular,
                producto_id,
                cantidad,
                total,
                estado
            )
    VALUES (%s, %s, %s, %s, %s, %s, 'pendiente')
""", (
    cliente_id,
    nombre_cliente,
    celular,
    id,
    cantidad,
    total
))

        nuevo_stock = stock - cantidad

        cur.execute("""
            UPDATE productos
            SET stock = %s
            WHERE id = %s
        """, (
            nuevo_stock,
            id
        ))

        mysql.connection.commit()
        cur.close()

        enviar_correo(
        correo,
        "Pedido registrado en Huancayoga 🛒",
        correo_pedido_registrado(nombre_cliente, producto[1], cantidad, total)
        )

        flash("Pedido registrado correctamente. Ahora puedes coordinar el pago por WhatsApp.", "success")
        return redirect(url_for("comprar", id=id))

    cur.close()
    return render_template("comprar.html", producto=producto)

@app.route("/admin/productos/nuevo", methods=["GET", "POST"])
def admin_nuevo_producto():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        nombre = request.form["nombre"]
        descripcion = request.form["descripcion"]
        precio = request.form["precio"]
        stock = request.form["stock"]
        try:
            imagen_subida = guardar_imagen_producto(request.files.get("imagen_archivo"))
            imagen = imagen_subida or normalizar_imagen_seleccionada(request.form.get("imagen"))
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("admin_nuevo_producto"))

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO productos
            (nombre, descripcion, precio, stock, imagen, estado)
            VALUES (%s, %s, %s, %s, %s, 'activo')
        """, (
            nombre,
            descripcion,
            precio,
            stock,
            imagen
        ))

        mysql.connection.commit()
        cur.close()

        # Enviar correo a todos los clientes registrados
        cur = mysql.connection.cursor()
        cur.execute("SELECT correo FROM clientes WHERE correo IS NOT NULL AND correo != '' AND estado = 'activo'")
        clientes = cur.fetchall()
        cur.close()

        for cliente in clientes:
            enviar_correo(
                cliente[0],
                "Nuevo producto disponible en Huancayoga 🛍️",
                correo_nuevo_producto(nombre, descripcion, precio)
                            )

        flash("Producto registrado correctamente.", "success")
        return redirect(url_for("admin_productos"))

    return render_template("admin/nuevo_producto.html")


@app.route("/admin/productos/editar/<int:id>", methods=["GET", "POST"])
def admin_editar_producto(id):
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombre, descripcion, precio, stock, imagen, estado
        FROM productos
        WHERE id = %s
    """, (id,))

    producto = cur.fetchone()

    if producto is None:
        cur.close()
        flash("El producto no existe.", "danger")
        return redirect(url_for("admin_productos"))

    if request.method == "POST":
        nombre = request.form["nombre"]
        descripcion = request.form["descripcion"]
        precio = request.form["precio"]
        stock = request.form["stock"]
        try:
            imagen_subida = guardar_imagen_producto(request.files.get("imagen_archivo"))
            imagen_seleccionada = normalizar_imagen_seleccionada(request.form.get("imagen"))
            quitar_imagen = request.form.get("eliminar_imagen") == "1"
            imagen = imagen_subida or imagen_seleccionada or ("" if quitar_imagen else producto[5])
        except ValueError as error:
            cur.close()
            flash(str(error), "danger")
            return redirect(url_for("admin_editar_producto", id=id))
        estado = request.form["estado"]

        cur.execute("""
            UPDATE productos
            SET nombre = %s,
                descripcion = %s,
                precio = %s,
                stock = %s,
                imagen = %s,
                estado = %s
            WHERE id = %s
        """, (
            nombre,
            descripcion,
            precio,
            stock,
            imagen,
            estado,
            id
        ))

        mysql.connection.commit()
        cur.close()

        flash("Producto actualizado correctamente.", "success")
        return redirect(url_for("admin_productos"))

    cur.close()
    return render_template("admin/editar_producto.html", producto=producto)


@app.route("/admin/productos/eliminar/<int:id>", methods=["POST"])
def admin_eliminar_producto(id):
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE productos
        SET estado = 'inactivo'
        WHERE id = %s
    """, (id,))

    mysql.connection.commit()
    cur.close()

    flash("Producto desactivado correctamente.", "success")
    return redirect(url_for("admin_productos"))

# ==========================
# MÓDULO ADMINISTRADOR
# ==========================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        turnstile_ok, turnstile_error = validar_turnstile()

        if not turnstile_ok:
            flash(turnstile_error, "danger")
            return redirect(url_for("admin_login"))

        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")

        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, nombre, usuario, password, rol
            FROM usuarios
            WHERE usuario = %s
        """, (usuario,))

        admin = cur.fetchone()

        if admin and password_admin_valido(admin[3], password):
            if not password_admin_es_hash(admin[3]):
                cur.execute("""
                    UPDATE usuarios
                    SET password = %s
                    WHERE id = %s
                """, (
                    generate_password_hash(password),
                    admin[0]
                ))
                mysql.connection.commit()

            cur.close()

            session["admin_id"] = admin[0]
            session["admin_nombre"] = admin[1]
            session["admin_usuario"] = admin[2]
            session["admin_rol"] = admin[4]

            flash("Bienvenido al panel administrativo.", "success")
            return redirect(url_for("admin_dashboard"))
        cur.close()
        flash("Usuario o contraseña incorrectos.", "danger")
        return redirect(url_for("admin_login"))

    return render_template("login.html", **contexto_seguridad_acceso())


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM reservas")
    total_reservas = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM reservas WHERE estado = 'pendiente'")
    reservas_pendientes = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM productos")
    total_productos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM pedidos")
    total_pedidos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM pedidos WHERE estado = 'pendiente'")
    pedidos_pendientes = cur.fetchone()[0]

    cur.close()

    return render_template(
        "admin/dashboard.html",
        total_reservas=total_reservas,
        reservas_pendientes=reservas_pendientes,
        total_productos=total_productos,
        total_pedidos=total_pedidos,
        pedidos_pendientes=pedidos_pendientes
    )


@app.route("/admin/integraciones/google-calendar")
def admin_google_calendar():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    integracion = cargar_integracion_google_calendar()
    cur = mysql.connection.cursor(DictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(ce.sync_estado = 'sincronizado'), 0) AS sincronizadas,
            COALESCE(SUM(ce.sync_estado = 'pendiente'), 0) AS pendientes,
            COALESCE(SUM(ce.sync_estado = 'error'), 0) AS errores
        FROM reservas r
        LEFT JOIN reserva_calendario_eventos ce
            ON ce.reserva_id = r.id
           AND ce.proveedor = 'google_calendar'
        WHERE r.estado = 'confirmada'
          AND r.fecha >= CURDATE()
    """)
    resumen = cur.fetchone()
    cur.execute("""
        SELECT
            r.id,
            r.nombre_cliente,
            r.fecha,
            LEFT(CAST(r.hora AS CHAR), 5) AS hora_texto,
            r.cantidad_personas,
            s.nombre AS servicio,
            ce.sync_estado,
            ce.evento_url,
            ce.ultimo_error
        FROM reservas r
        INNER JOIN servicios s ON s.id = r.servicio_id
        LEFT JOIN reserva_calendario_eventos ce
            ON ce.reserva_id = r.id
           AND ce.proveedor = 'google_calendar'
        WHERE r.estado = 'confirmada'
          AND r.fecha >= CURDATE()
        ORDER BY r.fecha ASC, r.hora ASC
        LIMIT 20
    """)
    proximas = cur.fetchall()
    cur.close()

    return render_template(
        "admin/integracion_calendario.html",
        integracion=integracion,
        resumen=resumen,
        proximas=proximas,
        configurado=google_calendar_configurado(),
        callback_url=url_externa_segura("admin_google_calendar_callback"),
    )


@app.route("/admin/integraciones/google-calendar/conectar")
def admin_google_calendar_conectar():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    if not google_calendar_configurado():
        flash("Configura las credenciales OAuth de Google antes de conectar el calendario.", "warning")
        return redirect(url_for("admin_google_calendar"))

    state = secrets.token_urlsafe(32)
    session["google_calendar_state"] = state
    session["google_calendar_started_at"] = int(time.time())
    callback_url = url_externa_segura("admin_google_calendar_callback")
    parametros = {
        "client_id": app.config["GOOGLE_CLIENT_ID"],
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid email profile https://www.googleapis.com/auth/calendar.events",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return redirect(
        "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(parametros)
    )


@app.route("/admin/integraciones/google-calendar/callback")
def admin_google_calendar_callback():
    if "admin_id" not in session:
        flash("La sesión administrativa venció. Inicia sesión y vuelve a conectar Google Calendar.", "warning")
        return redirect(url_for("admin_login"))

    state_recibido = request.args.get("state") or ""
    state_guardado = session.pop("google_calendar_state", "")
    iniciado = session.pop("google_calendar_started_at", 0)

    if (
        not state_guardado
        or not secrets.compare_digest(state_guardado, state_recibido)
        or int(time.time()) - int(iniciado or 0) > 600
    ):
        flash("La autorización de Google Calendar venció o no es válida.", "danger")
        return redirect(url_for("admin_google_calendar"))

    if request.args.get("error"):
        flash("La conexión con Google Calendar fue cancelada.", "warning")
        return redirect(url_for("admin_google_calendar"))

    codigo = request.args.get("code") or ""
    if not codigo:
        flash("Google no devolvió el código necesario para conectar el calendario.", "danger")
        return redirect(url_for("admin_google_calendar"))

    callback_url = url_externa_segura("admin_google_calendar_callback")
    try:
        respuesta_token = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": codigo,
                "client_id": app.config["GOOGLE_CLIENT_ID"],
                "client_secret": app.config["GOOGLE_CLIENT_SECRET"],
                "redirect_uri": callback_url,
                "grant_type": "authorization_code",
            },
            timeout=app.config.get("OAUTH_TIMEOUT", 12),
        )
        respuesta_token.raise_for_status()
        datos_token = respuesta_token.json()

        access_token = datos_token.get("access_token")
        if not access_token:
            raise ValueError("Google no devolvió un token de acceso.")

        respuesta_perfil = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=app.config.get("OAUTH_TIMEOUT", 12),
        )
        respuesta_perfil.raise_for_status()
        cuenta_email = (respuesta_perfil.json().get("email") or "").strip().lower()
        guardar_integracion_google_calendar(datos_token, cuenta_email or None)
    except (requests.RequestException, ValueError, TypeError) as error:
        enviar_alerta_sistema("google-calendar-connect", "Error al conectar Google Calendar", error)
        flash(
            "No se pudo completar la conexión. Revisa las credenciales y la URL de redirección de Google.",
            "danger",
        )
        return redirect(url_for("admin_google_calendar"))

    flash("Google Calendar quedó conectado correctamente con la agenda de Huancayoga.", "success")
    return redirect(url_for("admin_google_calendar"))


@app.route("/admin/integraciones/google-calendar/sincronizar", methods=["POST"])
def admin_google_calendar_sincronizar():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    if not cargar_integracion_google_calendar():
        flash("Primero conecta la cuenta de Google Calendar de la dueña.", "warning")
        return redirect(url_for("admin_google_calendar"))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT r.id
        FROM reservas r
        LEFT JOIN reserva_calendario_eventos ce
            ON ce.reserva_id = r.id
           AND ce.proveedor = 'google_calendar'
        WHERE r.estado = 'confirmada'
          AND r.fecha >= CURDATE()
          AND (ce.sync_estado IS NULL OR ce.sync_estado IN ('pendiente', 'error'))
        ORDER BY r.fecha ASC, r.hora ASC
        LIMIT 25
    """)
    reserva_ids = [fila[0] for fila in cur.fetchall()]
    cur.close()

    correctas = 0
    errores = 0
    for reserva_id in reserva_ids:
        sincronizada, _ = sincronizar_reserva_google_calendar(reserva_id, "confirmada")
        correctas += int(sincronizada)
        errores += int(not sincronizada)

    if not reserva_ids:
        flash("No hay reservas pendientes de sincronización.", "info")
    elif errores:
        flash(f"Se sincronizaron {correctas} reservas y {errores} quedaron para reintento.", "warning")
    else:
        flash(f"Se sincronizaron correctamente {correctas} reservas.", "success")
    return redirect(url_for("admin_google_calendar"))


@app.route("/admin/reserva/<int:reserva_id>/sincronizar-calendario", methods=["POST"])
def admin_reserva_sincronizar_calendario(reserva_id):
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    sincronizada, error = sincronizar_reserva_google_calendar(reserva_id)
    flash(
        "La reserva se sincronizó con Google Calendar." if sincronizada else error,
        "success" if sincronizada else "warning",
    )
    return redirect(request.referrer or url_for("admin_reservas"))


@app.route("/admin/integraciones/google-calendar/desconectar", methods=["POST"])
def admin_google_calendar_desconectar():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    integracion = cargar_integracion_google_calendar(incluir_tokens=True)
    if integracion and integracion.get("refresh_token"):
        try:
            requests.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": integracion["refresh_token"]},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=app.config.get("OAUTH_TIMEOUT", 12),
            )
        except requests.RequestException as error:
            enviar_alerta_sistema("google-calendar-revoke", "Google no confirmó la revocación", error)

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM integraciones_oauth WHERE proveedor = 'google_calendar'")
    cur.execute("""
        UPDATE reserva_calendario_eventos ce
        INNER JOIN reservas r ON r.id = ce.reserva_id
        SET ce.sync_estado = 'pendiente',
            ce.ultimo_error = 'Google Calendar fue desconectado'
        WHERE ce.proveedor = 'google_calendar'
          AND r.estado = 'confirmada'
          AND r.fecha >= CURDATE()
    """)
    mysql.connection.commit()
    cur.close()

    flash("Google Calendar fue desconectado. Las reservas del sistema se conservaron.", "success")
    return redirect(url_for("admin_google_calendar"))


@app.route("/admin/reservas")
def admin_reservas():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT
            r.id,
            r.nombre_cliente,
            r.celular,
            r.correo,
            s.nombre AS servicio,
            r.fecha,
            r.hora,
            LEFT(CAST(r.hora AS CHAR), 5) AS hora_texto,
            r.duracion_minutos,
            r.comentario,
            r.estado,
            r.fecha_registro,
            r.cantidad_personas,
            r.tipo_reserva,
            r.tipo_lugar,
            r.direccion_externa,
            d.categoria,
            d.nombre_organizacion,
            d.rango_edad,
            d.necesidades_apoyo,
            ce.sync_estado AS calendar_sync_estado,
            ce.evento_url AS calendar_evento_url,
            ce.ultimo_error AS calendar_sync_error
        FROM reservas r
        INNER JOIN servicios s ON r.servicio_id = s.id
        LEFT JOIN reserva_programa_detalles d ON d.reserva_id = r.id
        LEFT JOIN reserva_calendario_eventos ce
            ON ce.reserva_id = r.id
           AND ce.proveedor = 'google_calendar'
        ORDER BY r.fecha DESC, r.hora DESC, r.fecha_registro DESC
    """)

    reservas = cur.fetchall()
    cur.close()

    return render_template(
        "admin/reservas.html",
        reservas=reservas,
        categorias_programa=CATEGORIAS_PROGRAMA,
        max_asistentes=MAX_ASISTENTES_RESERVA,
    )


@app.route("/admin/reserva/estado/<int:id>/<estado>", methods=["POST"])
def cambiar_estado_reserva(id, estado):
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    transiciones_permitidas = {
        "pendiente": {"confirmada", "cancelada"},
        "confirmada": {"atendida", "cancelada"},
        "cancelada": set(),
        "atendida": set(),
    }

    if estado not in {"confirmada", "cancelada", "atendida"}:
        flash("Estado no permitido.", "danger")
        return redirect(url_for("admin_reservas"))

    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
    SELECT 
        r.id,
        r.nombre_cliente,
        r.correo,
        s.nombre AS servicio,
        r.fecha,
        r.hora,
        r.cantidad_personas,
        r.estado
    FROM reservas r
    INNER JOIN servicios s ON r.servicio_id = s.id
    WHERE r.id = %s
    FOR UPDATE
""", (id,))

    reserva = cur.fetchone()

    if reserva is None:
        mysql.connection.rollback()
        cur.close()
        flash("No se encontró la reserva.", "danger")
        return redirect(url_for("admin_reservas"))

    if estado not in transiciones_permitidas.get(reserva["estado"], set()):
        mysql.connection.rollback()
        cur.close()
        flash(
            f"Una reserva {reserva['estado']} no puede pasar al estado {estado}.",
            "warning",
        )
        return redirect(url_for("admin_reservas"))

    cur.execute("""
            UPDATE reservas
            SET estado = %s
            WHERE id = %s
    """, (estado, id))

    if estado in {"cancelada", "atendida"}:
        cur.execute("""
            DELETE FROM reserva_bloques_horario
            WHERE reserva_id = %s
        """, (id,))

    mysql.connection.commit()
    cur.close()

    if estado == "confirmada":
        enviar_correo(
            reserva["correo"],
            "Tu cita en Huancayoga fue confirmada ✅",
            correo_confirmacion_cita(
                reserva["nombre_cliente"],
                reserva["servicio"],
                reserva["fecha"],
                reserva["hora"],
                reserva["cantidad_personas"],
            )
        )

    calendario_sincronizado, error_calendario = sincronizar_reserva_google_calendar(id, estado)

    if not calendario_sincronizado and cargar_integracion_google_calendar():
        flash(error_calendario, "warning")

    flash("Estado de reserva actualizado correctamente.", "success")
    return redirect(url_for("admin_reservas"))


@app.route("/admin/pedidos")
def admin_pedidos():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT 
            p.id,
            p.nombre_cliente,
            p.celular,
            pr.nombre AS producto,
            p.cantidad,
            p.total,
            p.estado,
            p.fecha_pedido
        FROM pedidos p
        INNER JOIN productos pr ON p.producto_id = pr.id
        ORDER BY p.fecha_pedido DESC
    """)

    pedidos = cur.fetchall()
    cur.close()

    return render_template("admin/pedidos.html", pedidos=pedidos)


@app.route("/admin/pedido/estado/<int:id>/<estado>", methods=["POST"])
def cambiar_estado_pedido(id, estado):
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    estados_permitidos = ["pendiente", "pagado", "entregado", "cancelado"]

    if estado not in estados_permitidos:
        flash("Estado no permitido.", "danger")
        return redirect(url_for("admin_pedidos"))

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE pedidos
        SET estado = %s
        WHERE id = %s
    """, (estado, id))

    mysql.connection.commit()
    cur.close()

    flash("Estado de pedido actualizado correctamente.", "success")
    return redirect(url_for("admin_pedidos"))


@app.route("/admin/productos")
def admin_productos():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombre, descripcion, precio, stock, imagen, estado
        FROM productos
        ORDER BY id DESC
    """)

    productos = cur.fetchall()
    cur.close()

    return render_template("admin/productos.html", productos=productos)

# ==========================
# MÓDULO CLIENTE / USUARIO
# ==========================

def iniciar_sesion_cliente(cliente):
    session["cliente_id"] = cliente["id"]
    session["cliente_dni"] = cliente["dni"]
    session["cliente_nombre"] = cliente["nombres"]


def url_autorizacion_social(proveedor, callback_url, state):
    if proveedor == "google":
        verifier = secrets.token_urlsafe(64)[:128]
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        session["oauth_social_pkce"] = verifier
        parametros = {
            "client_id": app.config["GOOGLE_CLIENT_ID"],
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(parametros)}"

    if proveedor == "facebook":
        version = app.config["FACEBOOK_GRAPH_VERSION"]
        parametros = {
            "client_id": app.config["FACEBOOK_APP_ID"],
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": "email,public_profile",
            "state": state,
        }
        return f"https://www.facebook.com/{version}/dialog/oauth?{urlencode(parametros)}"

    parametros = {
        "client_key": app.config["TIKTOK_CLIENT_KEY"],
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "user.info.basic",
        "state": state,
    }
    return f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(parametros)}"


def obtener_perfil_social(proveedor, codigo, callback_url):
    timeout = app.config.get("OAUTH_TIMEOUT", 12)

    try:
        if proveedor == "google":
            respuesta_token = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": codigo,
                    "client_id": app.config["GOOGLE_CLIENT_ID"],
                    "client_secret": app.config["GOOGLE_CLIENT_SECRET"],
                    "redirect_uri": callback_url,
                    "grant_type": "authorization_code",
                    "code_verifier": session.pop("oauth_social_pkce", ""),
                },
                timeout=timeout,
            )
            respuesta_token.raise_for_status()
            token = respuesta_token.json().get("access_token")

            if not token:
                raise ValueError("Google no devolvió un token de acceso.")

            respuesta_perfil = requests.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {token}"},
                timeout=timeout,
            )
            respuesta_perfil.raise_for_status()
            datos = respuesta_perfil.json()
            perfil = {
                "id": datos.get("sub"),
                "nombre": datos.get("name"),
                "correo": datos.get("email"),
                "correo_verificado": bool(datos.get("email_verified")),
                "avatar": datos.get("picture"),
            }
        elif proveedor == "facebook":
            version = app.config["FACEBOOK_GRAPH_VERSION"]
            respuesta_token = requests.get(
                f"https://graph.facebook.com/{version}/oauth/access_token",
                params={
                    "client_id": app.config["FACEBOOK_APP_ID"],
                    "client_secret": app.config["FACEBOOK_APP_SECRET"],
                    "redirect_uri": callback_url,
                    "code": codigo,
                },
                timeout=timeout,
            )
            respuesta_token.raise_for_status()
            token = respuesta_token.json().get("access_token")

            if not token:
                raise ValueError("Facebook no devolvió un token de acceso.")

            respuesta_perfil = requests.get(
                f"https://graph.facebook.com/{version}/me",
                params={"fields": "id,name,email,picture.type(large)"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=timeout,
            )
            respuesta_perfil.raise_for_status()
            datos = respuesta_perfil.json()
            perfil = {
                "id": datos.get("id"),
                "nombre": datos.get("name"),
                "correo": datos.get("email"),
                "correo_verificado": False,
                "avatar": ((datos.get("picture") or {}).get("data") or {}).get("url"),
            }
        else:
            respuesta_token = requests.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                data={
                    "client_key": app.config["TIKTOK_CLIENT_KEY"],
                    "client_secret": app.config["TIKTOK_CLIENT_SECRET"],
                    "code": codigo,
                    "grant_type": "authorization_code",
                    "redirect_uri": callback_url,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=timeout,
            )
            respuesta_token.raise_for_status()
            datos_token = respuesta_token.json()
            token = datos_token.get("access_token")

            if not token:
                raise ValueError("TikTok no devolvió un token de acceso.")

            respuesta_perfil = requests.get(
                "https://open.tiktokapis.com/v2/user/info/",
                params={"fields": "open_id,union_id,avatar_url,display_name"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=timeout,
            )
            respuesta_perfil.raise_for_status()
            datos = ((respuesta_perfil.json().get("data") or {}).get("user") or {})
            perfil = {
                "id": datos.get("open_id") or datos_token.get("open_id"),
                "nombre": datos.get("display_name"),
                "correo": None,
                "correo_verificado": False,
                "avatar": datos.get("avatar_url"),
            }
    except (requests.RequestException, ValueError, TypeError) as error:
        raise ValueError(
            f"No pudimos obtener tu identidad desde {PROVEEDORES_SOCIALES[proveedor]}."
        ) from error

    if not perfil.get("id"):
        raise ValueError(
            f"{PROVEEDORES_SOCIALES[proveedor]} no devolvió un identificador de usuario."
        )

    perfil["id"] = str(perfil["id"])[:255]
    perfil["nombre"] = (perfil.get("nombre") or "")[:150] or None
    perfil["correo"] = (perfil.get("correo") or "").strip().lower()[:254] or None
    perfil["avatar"] = (perfil.get("avatar") or "")[:500] or None
    return perfil


def vincular_y_autenticar_social(dni, proveedor, perfil):
    cur = mysql.connection.cursor(DictCursor)

    try:
        cur.execute("""
            SELECT
                cs.cliente_id,
                c.dni,
                c.nombres,
                c.correo,
                c.estado
            FROM cliente_cuentas_sociales cs
            INNER JOIN clientes c ON c.id = cs.cliente_id
            WHERE cs.proveedor = %s
              AND cs.proveedor_usuario_id = %s
            FOR UPDATE
        """, (proveedor, perfil["id"]))
        cuenta_existente = cur.fetchone()

        if cuenta_existente and cuenta_existente["dni"] != dni:
            mysql.connection.rollback()
            return None, "Esta cuenta social ya está vinculada a otro DNI."

        cur.execute("""
            SELECT id, dni, nombres, correo, estado
            FROM clientes
            WHERE dni = %s
            FOR UPDATE
        """, (dni,))
        cliente = cur.fetchone()

        if cliente is None:
            mysql.connection.rollback()
            return "registro", None

        if cliente["estado"] != "activo":
            mysql.connection.rollback()
            return None, "La cuenta asociada a este DNI no está activa."

        if cuenta_existente and cuenta_existente["cliente_id"] != cliente["id"]:
            mysql.connection.rollback()
            return None, "La identidad social no corresponde a este DNI."

        cur.execute("""
            SELECT id, proveedor_usuario_id
            FROM cliente_cuentas_sociales
            WHERE cliente_id = %s
              AND proveedor = %s
            FOR UPDATE
        """, (cliente["id"], proveedor))
        vinculacion_cliente = cur.fetchone()

        if vinculacion_cliente and vinculacion_cliente["proveedor_usuario_id"] != perfil["id"]:
            mysql.connection.rollback()
            return None, f"Este DNI ya tiene otra cuenta de {PROVEEDORES_SOCIALES[proveedor]} vinculada."

        if vinculacion_cliente:
            cur.execute("""
                UPDATE cliente_cuentas_sociales
                SET correo_proveedor = %s,
                    correo_proveedor_verificado = %s,
                    nombre_proveedor = %s,
                    avatar_url = %s,
                    ultimo_acceso_at = NOW()
                WHERE id = %s
            """, (
                perfil["correo"],
                int(perfil["correo_verificado"]),
                perfil["nombre"],
                perfil["avatar"],
                vinculacion_cliente["id"],
            ))
        else:
            cur.execute("""
                INSERT INTO cliente_cuentas_sociales
                (
                    cliente_id,
                    proveedor,
                    proveedor_usuario_id,
                    correo_proveedor,
                    correo_proveedor_verificado,
                    nombre_proveedor,
                    avatar_url,
                    ultimo_acceso_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                cliente["id"],
                proveedor,
                perfil["id"],
                perfil["correo"],
                int(perfil["correo_verificado"]),
                perfil["nombre"],
                perfil["avatar"],
            ))

        if not cliente["correo"] and perfil["correo"] and perfil["correo_verificado"]:
            cur.execute("SELECT id FROM clientes WHERE correo = %s", (perfil["correo"],))
            propietario_correo = cur.fetchone()
            if propietario_correo is None:
                cur.execute("""
                    UPDATE clientes
                    SET correo = %s,
                        correo_verificado_at = NOW()
                    WHERE id = %s
                """, (perfil["correo"], cliente["id"]))
                cliente["correo"] = perfil["correo"]

        cur.execute("""
            UPDATE clientes
            SET ultimo_acceso_at = NOW()
            WHERE id = %s
        """, (cliente["id"],))
        mysql.connection.commit()
    except Exception:
        mysql.connection.rollback()
        raise
    finally:
        cur.close()

    iniciar_sesion_cliente(cliente)
    return cliente, None


@app.route("/cliente/social/preparar", methods=["POST"])
def cliente_social_preparar():
    dni = (request.form.get("dni") or "").strip()
    proveedor = (request.form.get("proveedor") or "").strip().lower()
    turnstile_ok, turnstile_error = validar_turnstile()

    if not turnstile_ok:
        flash(turnstile_error, "danger")
        return redirect(url_for("cliente_login"))

    if not re.fullmatch(r"[0-9]{8}", dni):
        flash("Ingresa un DNI válido de 8 dígitos.", "danger")
        return redirect(url_for("cliente_login"))

    if proveedor not in PROVEEDORES_SOCIALES:
        flash("Selecciona un proveedor de acceso válido.", "danger")
        return redirect(url_for("cliente_login"))

    if not proveedor_social_configurado(proveedor):
        flash(f"El acceso con {PROVEEDORES_SOCIALES[proveedor]} todavía no está configurado.", "warning")
        return redirect(url_for("cliente_login"))

    cur = mysql.connection.cursor()
    cur.execute("SELECT estado FROM clientes WHERE dni = %s", (dni,))
    fila_cliente = cur.fetchone()
    cur.close()

    if fila_cliente and fila_cliente[0] != "activo":
        flash("La cuenta asociada a este DNI no está activa.", "warning")
        return redirect(url_for("cliente_login"))

    state = secrets.token_urlsafe(32)
    session["oauth_social_state"] = state
    session["oauth_social_provider"] = proveedor
    session["oauth_social_dni"] = dni
    session["oauth_social_started_at"] = int(time.time())
    session.pop("oauth_social_pkce", None)
    callback_url = url_externa_segura("cliente_social_callback", proveedor=proveedor)
    return redirect(url_autorizacion_social(proveedor, callback_url, state))


@app.route("/cliente/oauth/<proveedor>/callback")
def cliente_social_callback(proveedor):
    proveedor = proveedor.lower()
    state_recibido = request.args.get("state") or ""
    state_guardado = session.pop("oauth_social_state", "")
    proveedor_guardado = session.pop("oauth_social_provider", "")
    dni = session.pop("oauth_social_dni", "")
    iniciado = session.pop("oauth_social_started_at", 0)

    if (
        proveedor not in PROVEEDORES_SOCIALES
        or proveedor != proveedor_guardado
        or not state_guardado
        or not secrets.compare_digest(state_guardado, state_recibido)
        or int(time.time()) - int(iniciado or 0) > 600
    ):
        session.pop("oauth_social_pkce", None)
        flash("La solicitud de acceso social venció o no es válida.", "danger")
        return redirect(url_for("cliente_login"))

    if request.args.get("error"):
        session.pop("oauth_social_pkce", None)
        flash(f"Cancelaste el acceso con {PROVEEDORES_SOCIALES[proveedor]}.", "warning")
        return redirect(url_for("cliente_login"))

    codigo = request.args.get("code") or ""

    if not codigo:
        flash("El proveedor no devolvió un código de autorización.", "danger")
        return redirect(url_for("cliente_login"))

    callback_url = url_externa_segura("cliente_social_callback", proveedor=proveedor)

    try:
        perfil = obtener_perfil_social(proveedor, codigo, callback_url)
        resultado, error = vincular_y_autenticar_social(dni, proveedor, perfil)
    except ValueError as error_oauth:
        enviar_alerta_sistema("oauth-social", "Error en acceso social", error_oauth)
        flash(str(error_oauth), "danger")
        return redirect(url_for("cliente_login"))

    if error:
        flash(error, "danger")
        return redirect(url_for("cliente_login"))

    if resultado == "registro":
        session["registro_social_pendiente"] = {
            "dni": dni,
            "proveedor": proveedor,
            "proveedor_usuario_id": perfil["id"],
            "nombre_proveedor": perfil["nombre"],
            "correo": perfil["correo"],
            "correo_verificado": bool(perfil["correo_verificado"]),
            "avatar": perfil["avatar"],
            "creado_at": int(time.time()),
        }
        flash("Completa tus datos para crear la cuenta vinculada a tu DNI.", "info")
        return redirect(url_for("cliente_registro_social"))

    flash(f"Ingresaste correctamente con {PROVEEDORES_SOCIALES[proveedor]}.", "success")

    if not resultado.get("correo"):
        return redirect(url_for("cliente_completar_correo"))

    return redirect(url_for("cliente_dashboard"))


@app.route("/cliente/registro-social", methods=["GET", "POST"])
def cliente_registro_social():
    pendiente = session.get("registro_social_pendiente") or {}

    if not pendiente or int(time.time()) - int(pendiente.get("creado_at", 0)) > 900:
        session.pop("registro_social_pendiente", None)
        flash("El registro social venció. Comienza nuevamente desde el acceso.", "warning")
        return redirect(url_for("cliente_login"))

    if request.method == "POST":
        dni = (request.form.get("dni") or "").strip()
        nombres = (request.form.get("nombres") or "").strip()
        apellido_paterno = (request.form.get("apellido_paterno") or "").strip()
        apellido_materno = (request.form.get("apellido_materno") or "").strip()
        celular = (request.form.get("celular") or "").strip()
        correo = (request.form.get("correo") or "").strip().lower()

        if dni != pendiente["dni"] or not re.fullmatch(r"[0-9]{8}", dni):
            flash("El DNI del registro no coincide con el DNI verificado.", "danger")
            return redirect(url_for("cliente_registro_social"))

        if not nombres or not apellido_paterno or not apellido_materno:
            flash("Completa tus nombres y apellidos.", "danger")
            return redirect(url_for("cliente_registro_social"))

        if not re.fullmatch(r"9[0-9]{8}", celular):
            flash("Ingresa un celular peruano válido de 9 dígitos.", "danger")
            return redirect(url_for("cliente_registro_social"))

        if not correo or not correo_reserva_valido(correo) or len(correo) > 254:
            flash("Ingresa un correo electrónico válido.", "danger")
            return redirect(url_for("cliente_registro_social"))

        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute("SELECT id FROM clientes WHERE dni = %s OR correo = %s FOR UPDATE", (dni, correo))
            if cur.fetchone():
                mysql.connection.rollback()
                flash("El DNI o correo ya está registrado. Inicia sesión.", "warning")
                return redirect(url_for("cliente_login"))

            cur.execute("""
                INSERT INTO clientes
                (
                    dni, nombres, apellido_paterno, apellido_materno,
                    celular, correo, correo_verificado_at, password_hash,
                    ultimo_acceso_at, estado
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NOW(), 'activo')
            """, (
                dni,
                nombres[:100],
                apellido_paterno[:100],
                apellido_materno[:100],
                celular,
                correo[:254],
                datetime.now() if pendiente.get("correo_verificado") and correo == pendiente.get("correo") else None,
            ))
            cliente_id = cur.lastrowid
            cur.execute("""
                INSERT INTO cliente_cuentas_sociales
                (
                    cliente_id, proveedor, proveedor_usuario_id,
                    correo_proveedor, correo_proveedor_verificado,
                    nombre_proveedor, avatar_url, ultimo_acceso_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                cliente_id,
                pendiente["proveedor"],
                pendiente["proveedor_usuario_id"],
                pendiente.get("correo"),
                int(pendiente.get("correo_verificado", False)),
                pendiente.get("nombre_proveedor"),
                pendiente.get("avatar"),
            ))
            mysql.connection.commit()
        except IntegrityError:
            mysql.connection.rollback()
            flash("El DNI, correo o cuenta social ya está registrado.", "warning")
            return redirect(url_for("cliente_login"))
        finally:
            cur.close()

        session.pop("registro_social_pendiente", None)
        iniciar_sesion_cliente({"id": cliente_id, "dni": dni, "nombres": nombres})
        flash("Tu cuenta fue creada y vinculada correctamente.", "success")
        return redirect(url_for("cliente_dashboard"))

    return render_template("cliente_registro_social.html", pendiente=pendiente)


@app.route("/cliente/completar-correo", methods=["GET", "POST"])
def cliente_completar_correo():
    if "cliente_id" not in session:
        return redirect(url_for("cliente_login"))

    if request.method == "POST":
        correo = (request.form.get("correo") or "").strip().lower()

        if not correo or not correo_reserva_valido(correo) or len(correo) > 254:
            flash("Ingresa un correo electrónico válido.", "danger")
            return redirect(url_for("cliente_completar_correo"))

        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM clientes WHERE correo = %s AND id <> %s", (correo, session["cliente_id"]))
        if cur.fetchone():
            cur.close()
            flash("Ese correo ya está asociado a otra cuenta.", "danger")
            return redirect(url_for("cliente_completar_correo"))

        cur.execute("UPDATE clientes SET correo = %s WHERE id = %s", (correo, session["cliente_id"]))
        mysql.connection.commit()
        cur.close()
        flash("Correo guardado correctamente para tus notificaciones.", "success")
        return redirect(url_for("cliente_dashboard"))

    return render_template("cliente_completar_correo.html")

@app.route("/cliente/login", methods=["GET", "POST"])
def cliente_login():
    if request.method == "POST":
        turnstile_ok, turnstile_error = validar_turnstile()

        if not turnstile_ok:
            flash(turnstile_error, "danger")
            return redirect(url_for("cliente_login"))

        dni = request.form.get("dni", "").strip()
        password = request.form.get("password", "")

        if not re.fullmatch(r"[0-9]{8}", dni):
            flash("Ingresa un DNI válido de 8 dígitos.", "danger")
            return redirect(url_for("cliente_login"))

        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT
                id,
                dni,
                nombres,
                password_hash,
                estado
            FROM clientes
            WHERE dni = %s
        """, (dni,))

        cliente = cur.fetchone()
        cur.close()

        if cliente is None:
            flash("El DNI no está registrado.", "danger")
            return redirect(url_for("cliente_login"))

        if cliente[4] != "activo":
            flash("Tu cuenta no está activa.", "warning")
            return redirect(url_for("cliente_login"))

        if cliente[3] is None:
            flash("Esta cuenta se creó con acceso social. Ingresa con la cuenta vinculada o usa recuperación para crear una contraseña.", "warning")
            return redirect(url_for("cliente_login"))

        if not check_password_hash(cliente[3], password):
            flash("La contraseña es incorrecta.", "danger")
            return redirect(url_for("cliente_login"))

        iniciar_sesion_cliente({
            "id": cliente[0],
            "dni": cliente[1],
            "nombres": cliente[2],
        })

        flash("Bienvenido a Huancayoga.", "success")
        return redirect(url_for("cliente_dashboard"))

    return render_template("cliente_login.html", **contexto_seguridad_acceso())

@app.route("/cliente/registro", methods=["GET", "POST"])
def cliente_registro():
    dni_recibido = request.args.get("dni", "")

    if request.method == "POST":
        turnstile_ok, turnstile_error = validar_turnstile()

        if not turnstile_ok:
            flash(turnstile_error, "danger")
            return redirect(url_for("cliente_registro"))

        dni = request.form.get("dni", "").strip()
        nombres = request.form.get("nombres", "").strip()
        apellido_paterno = request.form.get("apellido_paterno", "").strip()
        apellido_materno = request.form.get("apellido_materno", "").strip()
        celular = request.form.get("celular", "").strip()
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "")
        confirmar_password = request.form.get("confirmar_password", "")

        if not re.fullmatch(r"[0-9]{8}", dni):
            flash("Ingresa un DNI válido de 8 dígitos.", "danger")
            return redirect(url_for("cliente_registro", dni=dni))

        if not all((nombres, apellido_paterno, apellido_materno)):
            flash("Primero valida el DNI y completa los nombres y apellidos.", "danger")
            return redirect(url_for("cliente_registro", dni=dni))

        if any(len(valor) > 100 for valor in (nombres, apellido_paterno, apellido_materno)):
            flash("Los nombres o apellidos son demasiado largos.", "danger")
            return redirect(url_for("cliente_registro", dni=dni))

        if not re.fullmatch(r"9[0-9]{8}", celular):
            flash("Ingresa un celular peruano válido de 9 dígitos.", "danger")
            return redirect(url_for("cliente_registro", dni=dni))

        if not correo or not correo_reserva_valido(correo) or len(correo) > 254:
            flash("Ingresa un correo electrónico válido.", "danger")
            return redirect(url_for("cliente_registro", dni=dni))

        # Validar contraseñas
        if password != confirmar_password:
            flash("Las contraseñas no coinciden.", "danger")
            return redirect(url_for("cliente_registro"))

        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.", "danger")
            return redirect(url_for("cliente_registro"))

        # Cifrar contraseña
        password_hash = generate_password_hash(password)

        cur = mysql.connection.cursor()

        # Verificar si el DNI ya existe
        cur.execute("""
            SELECT id, dni, correo
            FROM clientes
            WHERE dni = %s OR correo = %s
        """, (dni, correo))

        existe = cur.fetchone()

        if existe:
            cur.close()
            flash("Este DNI o correo ya está registrado. Inicia sesión.", "warning")
            return redirect(url_for("cliente_login"))

        # Registrar cliente con contraseña cifrada
        try:
            cur.execute("""
                INSERT INTO clientes
                (
                    dni,
                    nombres,
                    apellido_paterno,
                    apellido_materno,
                    celular,
                    correo,
                    password_hash,
                    estado
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'activo')
            """, (
                dni,
                nombres,
                apellido_paterno,
                apellido_materno,
                celular,
                correo,
                password_hash
            ))
            mysql.connection.commit()
        except IntegrityError:
            mysql.connection.rollback()
            cur.close()
            flash("Este DNI o correo ya está registrado. Inicia sesión.", "warning")
            return redirect(url_for("cliente_login"))

        # Obtener cliente recién registrado
        cur.execute("""
            SELECT id, dni, nombres
            FROM clientes
            WHERE dni = %s
        """, (dni,))

        cliente = cur.fetchone()
        cur.close()

        # Crear sesión del cliente
        session["cliente_id"] = cliente[0]
        session["cliente_dni"] = cliente[1]
        session["cliente_nombre"] = cliente[2]

        # Enviar correo de bienvenida
        correo_enviado = enviar_correo(
            correo,
            "Bienvenido a Huancayoga 🌿",
            correo_bienvenida(nombres)
        )

        if correo_enviado:
            flash(
                "Registro completado correctamente. Te enviamos un correo de bienvenida.",
                "success"
            )
        else:
            flash(
                "Registro completado correctamente.",
                "success"
            )

        return redirect(url_for("cliente_dashboard"))

    return render_template(
        "cliente_registro.html",
        dni_recibido=dni_recibido,
        **contexto_seguridad_acceso(),
    )

@app.route("/cliente/dashboard")
def cliente_dashboard():
    if "cliente_id" not in session:
        flash("Debes iniciar sesión como cliente.", "warning")
        return redirect(url_for("cliente_login"))

    cliente_id = session["cliente_id"]

    cur = mysql.connection.cursor()

    # Datos del cliente
    cur.execute("""
        SELECT
            id,
            dni,
            nombres,
            apellido_paterno,
            apellido_materno,
            celular,
            correo
        FROM clientes
        WHERE id = %s
    """, (cliente_id,))

    cliente = cur.fetchone()

    # Total de citas del cliente
    cur.execute("""
        SELECT COUNT(*)
        FROM reservas
        WHERE cliente_id = %s
    """, (cliente_id,))

    total_citas = cur.fetchone()[0]

    # Citas pendientes
    cur.execute("""
        SELECT COUNT(*)
        FROM reservas
        WHERE cliente_id = %s
        AND estado = 'pendiente'
    """, (cliente_id,))

    citas_pendientes = cur.fetchone()[0]

    # Total de pedidos
    cur.execute("""
        SELECT COUNT(*)
        FROM pedidos
        WHERE cliente_id = %s
    """, (cliente_id,))

    total_pedidos = cur.fetchone()[0]

    # Próxima cita
    cur.execute("""
        SELECT
            r.id,
            s.nombre,
            r.fecha,
            r.hora,
            r.estado,
            r.cantidad_personas,
            r.tipo_reserva,
            d.categoria,
            d.nombre_organizacion
        FROM reservas r
        INNER JOIN servicios s
            ON r.servicio_id = s.id
        LEFT JOIN reserva_programa_detalles d
            ON d.reserva_id = r.id
        WHERE r.cliente_id = %s
        AND r.fecha >= CURDATE()
        AND r.estado IN ('pendiente', 'confirmada')
        ORDER BY r.fecha ASC, r.hora ASC
        LIMIT 1
    """, (cliente_id,))

    proxima_cita = cur.fetchone()

    # Última publicación
    cur.execute("""
        SELECT
            id,
            titulo,
            contenido,
            imagen,
            tipo,
            fecha_publicacion
        FROM publicaciones
        WHERE estado = 'activo'
        ORDER BY fecha_publicacion DESC
        LIMIT 1
    """)

    ultima_publicacion = cur.fetchone()

    cur.close()

    return render_template(
        "cliente/dashboard.html",
        cliente=cliente,
        total_citas=total_citas,
        citas_pendientes=citas_pendientes,
        total_pedidos=total_pedidos,
        proxima_cita=proxima_cita,
        ultima_publicacion=ultima_publicacion,
        categorias_programa=CATEGORIAS_PROGRAMA,
    )
@app.route("/cliente/mis-citas")
def cliente_mis_citas():
    if "cliente_id" not in session:
        flash("Debes iniciar sesión como cliente.", "warning")
        return redirect(url_for("cliente_login"))

    cliente_id = session["cliente_id"]

    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT
            r.id,
            s.nombre AS servicio,
            r.fecha,
            r.hora,
            LEFT(CAST(r.hora AS CHAR), 5) AS hora_texto,
            r.duracion_minutos,
            r.comentario,
            r.estado,
            r.fecha_registro,
            r.cantidad_personas,
            r.tipo_reserva,
            r.tipo_lugar,
            r.direccion_externa,
            d.categoria,
            d.nombre_organizacion,
            d.rango_edad,
            d.necesidades_apoyo
        FROM reservas r
        INNER JOIN servicios s
            ON r.servicio_id = s.id
        LEFT JOIN reserva_programa_detalles d
            ON d.reserva_id = r.id
        WHERE r.cliente_id = %s
        ORDER BY r.fecha DESC, r.hora DESC
    """, (cliente_id,))

    citas = cur.fetchall()
    cur.close()

    return render_template(
        "cliente/mis_citas.html",
        citas=citas,
        categorias_programa=CATEGORIAS_PROGRAMA,
        max_asistentes=MAX_ASISTENTES_RESERVA,
    )


@app.route("/cliente/mis-pedidos")
def cliente_mis_pedidos():
    if "cliente_id" not in session:
        flash("Debes iniciar sesión como cliente.", "warning")
        return redirect(url_for("cliente_login"))

    cliente_id = session["cliente_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            p.id,
            pr.nombre,
            p.cantidad,
            p.total,
            p.estado,
            p.fecha_pedido
        FROM pedidos p
        INNER JOIN productos pr
            ON p.producto_id = pr.id
        WHERE p.cliente_id = %s
        ORDER BY p.fecha_pedido DESC
    """, (cliente_id,))

    pedidos = cur.fetchall()
    cur.close()

    return render_template(
        "cliente/mis_pedidos.html",
        pedidos=pedidos
    )


@app.route("/cliente/perfil")
def cliente_perfil():
    if "cliente_id" not in session:
        flash("Debes iniciar sesión como cliente.", "warning")
        return redirect(url_for("cliente_login"))

    cliente_id = session["cliente_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            id,
            dni,
            nombres,
            apellido_paterno,
            apellido_materno,
            celular,
            correo,
            fecha_registro
        FROM clientes
        WHERE id = %s
    """, (cliente_id,))

    cliente = cur.fetchone()
    cur.close()

    return render_template(
        "cliente/perfil.html",
        cliente=cliente
    )


@app.route("/cliente/logout")
def cliente_logout():
    session.pop("cliente_id", None)
    session.pop("cliente_dni", None)
    session.pop("cliente_nombre", None)

    flash("Sesión de cliente cerrada correctamente.", "success")
    return redirect(url_for("index"))

@app.route("/admin/reserva/recordatorio/<int:id>", methods=["POST"])
def enviar_recordatorio_reserva(id):
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT 
            r.nombre_cliente,
            r.correo,
            s.nombre,
            r.fecha,
            r.hora,
            r.cantidad_personas,
            r.estado
        FROM reservas r
        INNER JOIN servicios s ON r.servicio_id = s.id
        WHERE r.id = %s
    """, (id,))

    reserva = cur.fetchone()
    cur.close()

    if reserva and reserva[6] == "confirmada":
        enviar_correo(
            reserva[1],
            "Recordatorio de tu cita en Huancayoga 🌿",
            correo_recordatorio_cita(
                reserva[0],
                reserva[2],
                reserva[3],
                reserva[4],
                reserva[5]
            )
        )

        flash("Recordatorio enviado correctamente.", "success")
    elif reserva:
        flash("Solo puedes enviar recordatorios de reservas confirmadas.", "warning")
    else:
        flash("No se encontró la reserva.", "danger")

    return redirect(url_for("admin_reservas"))

# ==========================
# MÓDULO DE PUBLICACIONES
# ==========================

@app.route("/admin/publicaciones")
def admin_publicaciones():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, titulo, contenido, imagen, tipo, estado, fecha_publicacion
        FROM publicaciones
        ORDER BY fecha_publicacion DESC
    """)
    publicaciones = cur.fetchall()
    cur.close()

    return render_template(
        "admin/publicaciones.html",
        publicaciones=publicaciones
    )


@app.route("/admin/publicaciones/nueva", methods=["GET", "POST"])
def admin_nueva_publicacion():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        titulo = request.form["titulo"]
        contenido = request.form["contenido"]
        try:
            imagen_subida = guardar_imagen_publicacion(request.files.get("imagen_archivo"))
            imagen = imagen_subida or normalizar_imagen_seleccionada(request.form.get("imagen"))
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("admin_nueva_publicacion"))
        tipo = request.form["tipo"]

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO publicaciones
            (titulo, contenido, imagen, tipo, estado)
            VALUES (%s, %s, %s, %s, 'activo')
        """, (
            titulo,
            contenido,
            imagen,
            tipo
        ))

        mysql.connection.commit()
        cur.close()

        # Enviar correo a los clientes
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT correo
            FROM clientes
            WHERE correo IS NOT NULL
            AND correo != ''
            AND estado = 'activo'
        """)
        clientes = cur.fetchall()
        cur.close()

        for cliente in clientes:
            enviar_correo(
                cliente[0],
                "Nueva publicación de Huancayoga ✨",
                correo_nueva_publicacion(titulo, contenido)
            )

        flash("Publicación registrada y notificada correctamente.", "success")
        return redirect(url_for("admin_publicaciones"))

    return render_template("admin/nueva_publicacion.html")


@app.route("/admin/publicaciones/editar/<int:id>", methods=["GET", "POST"])
def admin_editar_publicacion(id):
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, titulo, contenido, imagen, tipo, estado
        FROM publicaciones
        WHERE id = %s
    """, (id,))

    publicacion = cur.fetchone()

    if publicacion is None:
        cur.close()
        flash("La publicación no existe.", "danger")
        return redirect(url_for("admin_publicaciones"))

    if request.method == "POST":
        titulo = request.form["titulo"]
        contenido = request.form["contenido"]
        try:
            imagen_subida = guardar_imagen_publicacion(request.files.get("imagen_archivo"))
            imagen_seleccionada = normalizar_imagen_seleccionada(request.form.get("imagen"))
            quitar_imagen = request.form.get("eliminar_imagen") == "1"
            imagen = imagen_subida or imagen_seleccionada or ("" if quitar_imagen else publicacion[3])
        except ValueError as error:
            cur.close()
            flash(str(error), "danger")
            return redirect(url_for("admin_editar_publicacion", id=id))
        tipo = request.form["tipo"]
        estado = request.form["estado"]

        cur.execute("""
            UPDATE publicaciones
            SET titulo = %s,
                contenido = %s,
                imagen = %s,
                tipo = %s,
                estado = %s
            WHERE id = %s
        """, (
            titulo,
            contenido,
            imagen,
            tipo,
            estado,
            id
        ))

        mysql.connection.commit()
        cur.close()

        flash("Publicación actualizada correctamente.", "success")
        return redirect(url_for("admin_publicaciones"))

    cur.close()
    return render_template(
        "admin/editar_publicacion.html",
        publicacion=publicacion
    )


@app.route("/admin/publicaciones/eliminar/<int:id>", methods=["POST"])
def admin_eliminar_publicacion(id):
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE publicaciones
        SET estado = 'inactivo'
        WHERE id = %s
    """, (id,))

    mysql.connection.commit()
    cur.close()

    flash("Publicación desactivada correctamente.", "success")
    return redirect(url_for("admin_publicaciones"))


@app.route("/publicaciones")
def publicaciones_publicas():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, titulo, contenido, imagen, tipo, fecha_publicacion
        FROM publicaciones
        WHERE estado = 'activo'
        ORDER BY fecha_publicacion DESC
    """)
    publicaciones = cur.fetchall()
    cur.close()
    
    return render_template(
        "public/publicaciones.html",
        publicaciones=publicaciones
    )

# ==========================
# ACCESO CORTO PARA LA DUEÑA
# ==========================

@app.route("/duena")
def acceso_duena():
    return redirect(url_for("admin_login"))



# ==========================
# API RENIEC / DECOLECTA - BUSCAR DNI
# ==========================

@app.route("/api/reniec/<dni>")
def api_reniec(dni):
    if len(dni) != 8 or not dni.isdigit():
        return {
            "ok": False,
            "mensaje": "El DNI debe tener 8 dígitos."
        }, 400

    reniec_url = os.getenv("RENIEC_API_URL")
    reniec_token = os.getenv("RENIEC_API_TOKEN")

    if not reniec_url or not reniec_token:
        return {
            "ok": False,
            "mensaje": "La API RENIEC no está configurada."
        }, 500

    try:
        respuesta = requests.get(
            reniec_url,
            params={"numero": dni},
            headers={
                "Authorization": f"Bearer {reniec_token}",
                "Accept": "application/json"
            },
            timeout=15
        )

        print("STATUS RENIEC:", respuesta.status_code)
        print("RESPUESTA RENIEC:", respuesta.text)

        if respuesta.status_code != 200:
            return {
                "ok": False,
                "mensaje": "No se pudo consultar el DNI."
            }, 400

        data = respuesta.json()

        # Algunos proveedores devuelven los datos dentro de "data"
        datos = data.get("data", data)

        nombres = (
            datos.get("nombres")
            or datos.get("nombre")
            or ""
        )

        apellido_paterno = (
            datos.get("apellido_paterno")
            or datos.get("apellidoPaterno")
            or ""
        )

        apellido_materno = (
            datos.get("apellido_materno")
            or datos.get("apellidoMaterno")
            or ""
        )

        # Algunos servicios devuelven nombre completo como:
        # "ROBLES ARRIETA DIEGO PAOLO" o "ROBLES ARRIETA, DIEGO PAOLO"
        nombre_completo = (
            datos.get("nombre_completo")
            or datos.get("nombreCompleto")
            or datos.get("full_name")
            or ""
        )

        if not nombres and nombre_completo:
            nombre_completo = nombre_completo.replace(",", " ")
            partes = nombre_completo.split()

            if len(partes) >= 3:
                apellido_paterno = apellido_paterno or partes[0]
                apellido_materno = apellido_materno or partes[1]
                nombres = nombres or " ".join(partes[2:])

        if not nombres:
            return {
                "ok": False,
                "mensaje": "No se encontraron datos para este DNI."
            }, 404

        return {
            "ok": True,
            "dni": dni,
            "nombres": nombres,
            "apellido_paterno": apellido_paterno,
            "apellido_materno": apellido_materno
        }

    except Exception as e:
        print("Error RENIEC:", e)
        return {
            "ok": False,
            "mensaje": "Error al consultar RENIEC."
        }, 500
    
@app.route("/cliente/recuperar", methods=["GET", "POST"])
def cliente_recuperar():
    if request.method == "POST":
        correo = request.form["correo"].strip()

        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT id, nombres, correo
            FROM clientes
            WHERE correo = %s
        """, (correo,))

        cliente = cur.fetchone()

        if cliente is None:
            cur.close()
            flash("No encontramos una cuenta con ese correo.", "warning")
            return redirect(url_for("cliente_recuperar"))

        token = secrets.token_urlsafe(32)
        expira = datetime.now() + timedelta(minutes=30)

        cur.execute("""
            UPDATE clientes
            SET reset_token = %s,
                reset_token_expira = %s
            WHERE id = %s
        """, (
            token,
            expira,
            cliente[0]
        ))

        mysql.connection.commit()
        cur.close()

        enlace = url_for(
            "cliente_restablecer",
            token=token,
            _external=True
        )

        enviar_correo(
            cliente[2],
            "Recupera tu contraseña - Huancayoga",
            correo_recuperar_password(cliente[1], enlace)
        )

        flash(
            "Te enviamos un enlace para recuperar tu contraseña.",
            "success"
        )
        return redirect(url_for("cliente_login"))

    return render_template("cliente_recuperar.html")

@app.route("/cliente/restablecer/<token>", methods=["GET", "POST"])
def cliente_restablecer(token):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombres, reset_token_expira
        FROM clientes
        WHERE reset_token = %s
    """, (token,))

    cliente = cur.fetchone()

    if cliente is None:
        cur.close()
        flash("El enlace no es válido.", "danger")
        return redirect(url_for("cliente_login"))

    if cliente[2] < datetime.now():
        cur.close()
        flash("El enlace ha expirado. Solicita uno nuevo.", "warning")
        return redirect(url_for("cliente_recuperar"))

    if request.method == "POST":
        password = request.form["password"]
        confirmar_password = request.form["confirmar_password"]

        if password != confirmar_password:
            cur.close()
            flash("Las contraseñas no coinciden.", "danger")
            return redirect(url_for("cliente_restablecer", token=token))

        if len(password) < 6:
            cur.close()
            flash("La contraseña debe tener al menos 6 caracteres.", "danger")
            return redirect(url_for("cliente_restablecer", token=token))

        password_hash = generate_password_hash(password)

        cur.execute("""
            UPDATE clientes
            SET password_hash = %s,
                reset_token = NULL,
                reset_token_expira = NULL
            WHERE id = %s
        """, (
            password_hash,
            cliente[0]
        ))

        mysql.connection.commit()
        cur.close()

        flash("Tu contraseña fue actualizada correctamente.", "success")
        return redirect(url_for("cliente_login"))

    cur.close()
    return render_template("cliente_restablecer.html")

# ==================================================
# CHATBOT HUANCAYOGA - PRIMERA VERSIÓN LOCAL
# ==================================================

def obtener_respuesta_chatbot_local(mensaje):
    texto = mensaje.lower().strip()

    # Informacion tecnica del servicio de IA
    if any(frase in texto for frase in [
        "servicio ia", "servicio de ia", "inteligencia artificial",
        "openai", "api", "modelo de ia", "de donde viene tu ia",
        "de dónde viene tu ia"
    ]):
        return {
            "respuesta": (
                "Mi servicio de inteligencia artificial esta integrado con la API de OpenAI "
                "desde el backend del sistema Huancayoga. El navegador envia tu mensaje a Flask, "
                "Flask consulta OpenAI usando una clave privada guardada en variables de entorno "
                "y luego devuelve la respuesta al chatbot."
            ),
            "boton_texto": None,
            "boton_url": None
        }

    # Saludo
    if any(palabra in texto for palabra in [
        "hola", "buenos días", "buenas tardes", "buenas noches"
    ]):
        return {
            "respuesta": (
                "¡Hola! 🌿 Soy el asistente virtual de Huancayoga. "
                "Puedo ayudarte con reservas, citas, productos, pedidos, "
                "horarios y servicios de yoga."
            ),
            "boton_texto": None,
            "boton_url": None
        }

    # Reservar
    if any(palabra in texto for palabra in [
        "reservar", "reserva", "agendar", "cita", "inscribirme"
    ]):
        return {
            "respuesta": (
                "Para reservar una sesión, entra a la sección Reservar. "
                "Ahí podrás seleccionar el servicio, la fecha y la hora disponible."
            ),
            "boton_texto": "Reservar una cita",
            "boton_url": "/reservar"
        }

    # Consultar citas
    if any(frase in texto for frase in [
        "mis citas", "ver citas", "consultar citas", "próxima cita"
    ]):
        return {
            "respuesta": (
                "Puedes consultar tus citas registradas y revisar su estado "
                "desde la sección Mis citas."
            ),
            "boton_texto": "Ver mis citas",
            "boton_url": "/cliente/mis-citas"
        }

    # Productos
    if any(palabra in texto for palabra in [
        "producto", "productos", "comprar", "precio", "aceite",
        "incienso", "mat", "bloque", "botella"
    ]):
        return {
            "respuesta": (
                "Puedes revisar los productos disponibles de Huancayoga, "
                "sus precios y características desde el catálogo."
            ),
            "boton_texto": "Ver productos",
            "boton_url": "/productos"
        }

    # Pedidos
    if any(frase in texto for frase in [
        "mis pedidos", "ver pedidos", "pedido", "estado de mi pedido"
    ]):
        return {
            "respuesta": (
                "Puedes consultar los productos solicitados y el estado "
                "de tus compras desde la sección Mis pedidos."
            ),
            "boton_texto": "Ver mis pedidos",
            "boton_url": "/cliente/mis-pedidos"
        }

    # Perfil
    if any(frase in texto for frase in [
        "mi perfil", "mis datos", "datos personales", "cambiar mis datos"
    ]):
        return {
            "respuesta": (
                "Desde Mi perfil puedes revisar y actualizar tus datos personales."
            ),
            "boton_texto": "Ir a mi perfil",
            "boton_url": "/cliente/perfil"
        }

    # Horarios
    if any(palabra in texto for palabra in [
        "horario", "horarios", "hora", "atienden", "disponibilidad"
    ]):
        return {
            "respuesta": (
                "Los horarios dependen de la disponibilidad de las sesiones. "
                "Puedes ingresar a Reservar para consultar las fechas y horas disponibles."
            ),
            "boton_texto": "Consultar horarios",
            "boton_url": "/reservar"
        }

    # Recomendación básica
    if any(palabra in texto for palabra in [
        "estrés", "estres", "relajarme", "ansiedad",
        "espalda", "principiante", "meditación", "meditacion"
    ]):
        return {
            "respuesta": (
                "Para relajación y reducción del estrés podrías considerar "
                "una sesión de respiración, meditación o yoga suave. "
                "La instructora podrá orientarte según tu condición y experiencia."
            ),
            "boton_texto": "Reservar orientación",
            "boton_url": "/reservar"
        }

    # Pregunta desconocida
    return {
        "respuesta": (
            "Todavía no comprendí completamente tu pregunta. 🌿 "
            "Puedes preguntarme cómo reservar, consultar citas, ver productos, "
            "revisar pedidos, horarios o servicios de yoga."
        ),
        "boton_texto": None,
        "boton_url": None
    }


RUTAS_CHATBOT_PERMITIDAS = {
    "/reservar": "Reservar una cita",
    "/productos": "Ver productos",
    "/cliente/mis-citas": "Ver mis citas",
    "/cliente/mis-pedidos": "Ver mis pedidos",
    "/cliente/perfil": "Ir a mi perfil",
    "/publicaciones": "Ver publicaciones"
}


def obtener_contexto_chatbot():
    contexto = [
        "Huancayoga es un sistema web de reservas, productos, pedidos y publicaciones de bienestar.",
        "El cliente puede reservar citas, revisar sus citas, comprar productos, ver pedidos y leer publicaciones.",
        "Si falta informacion exacta, orienta al cliente a la seccion correcta del sistema."
    ]

    try:
        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT nombre, precio
            FROM servicios
            WHERE estado = 'activo'
            ORDER BY nombre ASC
            LIMIT 8
        """)
        servicios = cur.fetchall()

        if servicios:
            servicios_texto = ", ".join(
                f"{servicio[0]} (S/ {servicio[1]})"
                for servicio in servicios
            )
            contexto.append(f"Servicios activos: {servicios_texto}.")

        cur.execute("""
            SELECT nombre, precio, stock
            FROM productos
            WHERE estado = 'activo'
            ORDER BY nombre ASC
            LIMIT 8
        """)
        productos = cur.fetchall()

        if productos:
            productos_texto = ", ".join(
                f"{producto[0]} (S/ {producto[1]}, stock {producto[2]})"
                for producto in productos
            )
            contexto.append(f"Productos activos: {productos_texto}.")

        if "cliente_id" in session:
            cliente_id = session["cliente_id"]

            cur.execute("""
                SELECT nombres
                FROM clientes
                WHERE id = %s
            """, (cliente_id,))
            cliente = cur.fetchone()

            if cliente:
                contexto.append(f"Cliente conectado: {cliente[0]}.")

            cur.execute("""
                SELECT s.nombre, r.fecha, r.hora, r.estado
                FROM reservas r
                INNER JOIN servicios s ON r.servicio_id = s.id
                WHERE r.cliente_id = %s
                AND r.fecha >= CURDATE()
                AND r.estado IN ('pendiente', 'confirmada')
                ORDER BY r.fecha ASC, r.hora ASC
                LIMIT 1
            """, (cliente_id,))
            proxima_cita = cur.fetchone()

            if proxima_cita:
                contexto.append(
                    "Proxima cita del cliente: "
                    f"{proxima_cita[0]} el {proxima_cita[1]} "
                    f"a las {proxima_cita[2]}, estado {proxima_cita[3]}."
                )

            cur.execute("""
                SELECT COUNT(*)
                FROM pedidos
                WHERE cliente_id = %s
            """, (cliente_id,))
            total_pedidos = cur.fetchone()[0]
            contexto.append(f"Total de pedidos del cliente: {total_pedidos}.")

        cur.close()

    except Exception as e:
        print(f"No se pudo construir el contexto del chatbot: {e}")

    return "\n".join(contexto)


def extraer_texto_openai(data):
    if isinstance(data.get("output_text"), str):
        return data["output_text"].strip()

    textos = []

    for item in data.get("output", []):
        for contenido in item.get("content", []):
            texto = contenido.get("text")

            if isinstance(texto, str):
                textos.append(texto)

    return "\n".join(textos).strip()


def normalizar_respuesta_ia(texto, mensaje_original):
    texto = texto.strip()

    if texto.startswith("```"):
        texto = texto.strip("`").strip()
        if texto.lower().startswith("json"):
            texto = texto[4:].strip()

    try:
        data = json.loads(texto)
        respuesta = str(data.get("respuesta", "")).strip()
        boton_texto = data.get("boton_texto")
        boton_url = data.get("boton_url")
    except Exception:
        respuesta = texto
        boton_texto = None
        boton_url = None

    if not respuesta:
        respuesta = obtener_respuesta_chatbot_local(mensaje_original)["respuesta"]

    if boton_url not in RUTAS_CHATBOT_PERMITIDAS:
        fallback = obtener_respuesta_chatbot_local(mensaje_original)
        boton_texto = fallback.get("boton_texto")
        boton_url = fallback.get("boton_url")

    if boton_url and not boton_texto:
        boton_texto = RUTAS_CHATBOT_PERMITIDAS.get(boton_url)

    return {
        "respuesta": respuesta,
        "boton_texto": boton_texto,
        "boton_url": boton_url
    }


def obtener_respuesta_chatbot_openai(mensaje):
    api_key = app.config.get("OPENAI_API_KEY")

    if not api_key:
        return None

    instrucciones = """
Eres Huancayoga Bot, asistente virtual del sistema Huancayoga.
Responde siempre en espanol, con tono amable, breve y claro.

Puedes ayudar con:
- reservas de citas y orientacion para elegir servicios
- consulta general de citas, horarios y disponibilidad
- productos, precios y stock cuando aparezcan en el contexto
- pedidos y perfil del cliente
- publicaciones de inspiracion y bienestar
- dudas generales de yoga, meditacion, respiracion y relajacion
- preguntas tecnicas sobre tu propia integracion de IA

Reglas:
- Si preguntan de donde viene tu servicio de IA, que tecnologia usas, si usas OpenAI,
  o como estas integrado, responde que usas la API de OpenAI desde el backend Flask
  del sistema Huancayoga. Explica que el navegador envia el mensaje a Flask,
  Flask consulta OpenAI con una API key privada guardada en variables de entorno
  y devuelve la respuesta al chatbot. No digas que tienes ubicacion fisica propia.
- No inventes precios, stock, fechas, estados de pedidos ni horarios exactos.
- Si el cliente necesita hacer una accion, recomienda una de estas rutas:
  /reservar, /productos, /cliente/mis-citas, /cliente/mis-pedidos, /cliente/perfil, /publicaciones.
- No des diagnosticos medicos. Para dolor fuerte, lesiones o ansiedad intensa, recomienda consultar a un profesional.
- Devuelve solo JSON valido con esta forma:
  {"respuesta":"texto para el cliente","boton_texto":"texto opcional","boton_url":"ruta opcional"}
- Si no hace falta boton, usa null en boton_texto y boton_url.
"""

    payload = {
        "model": app.config.get("OPENAI_MODEL", "gpt-5.4-mini"),
        "instructions": instrucciones,
        "input": (
            "Contexto disponible del sistema:\n"
            f"{obtener_contexto_chatbot()}\n\n"
            f"Mensaje del cliente: {mensaje}"
        ),
        "max_output_tokens": 350
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        respuesta_http = requests.post(
            "https://api.openai.com/v1/responses",
            headers=headers,
            json=payload,
            timeout=app.config.get("OPENAI_TIMEOUT", 20)
        )

        if respuesta_http.status_code not in [200, 201]:
            print("OpenAI chatbot no respondio correctamente.")
            print("Status:", respuesta_http.status_code)
            print("Respuesta:", respuesta_http.text[:500])
            enviar_alerta_sistema(
                "openai_chatbot_status",
                "OpenAI no respondio correctamente",
                f"Status: {respuesta_http.status_code}\nRespuesta: {respuesta_http.text[:500]}"
            )
            return None

        texto = extraer_texto_openai(respuesta_http.json())

        if not texto:
            return None

        return normalizar_respuesta_ia(texto, mensaje)

    except Exception as e:
        print(f"Error al consultar OpenAI para el chatbot: {e}")
        enviar_alerta_sistema(
            "openai_chatbot_exception",
            "Error al consultar OpenAI",
            str(e)
        )
        return None


def obtener_respuesta_chatbot(mensaje):
    provider = app.config.get("CHATBOT_PROVIDER", "local")

    if provider != "local":
        respuesta_ia = obtener_respuesta_chatbot_openai(mensaje)

        if respuesta_ia:
            return respuesta_ia

    return obtener_respuesta_chatbot_local(mensaje)


@app.route("/api/chatbot", methods=["POST"])
def api_chatbot():
    datos = request.get_json(silent=True) or {}
    mensaje = datos.get("mensaje", "").strip()

    if not mensaje:
        return {
            "ok": False,
            "respuesta": "Escribe una pregunta para poder ayudarte.",
            "boton_texto": None,
            "boton_url": None
        }, 400

    resultado = obtener_respuesta_chatbot(mensaje)

    return {
        "ok": True,
        "respuesta": resultado["respuesta"],
        "boton_texto": resultado["boton_texto"],
        "boton_url": resultado["boton_url"]
    }

if __name__ == "__main__":
    app.run(debug=app.config.get("APP_DEBUG", False))
