from flask import Flask, render_template, request, redirect, url_for, flash,session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask_mail import Mail, Message
import os
import requests
import secrets
import json


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY","huancayoga_clave_temporal_2026")

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

mail = Mail(app)

mysql = MySQL(app)


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

def correo_confirmacion_cita(nombre, servicio, fecha, hora):
    return f"""
    <div style="font-family: Arial, sans-serif; background:#faf7f0; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:18px; padding:30px;">
            <h1 style="color:#315545;">Tu cita fue confirmada ✅</h1>

            <p>Hola <strong>{nombre}</strong>,</p>

            <p>Tu cita en Huancayoga ha sido confirmada.</p>

            <ul>
                <li><strong>Servicio:</strong> {servicio}</li>
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

def correo_recordatorio_cita(nombre, servicio, fecha, hora):
    return f"""
    <div style="font-family: Arial, sans-serif; background:#faf7f0; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:18px; padding:30px;">
            <h1 style="color:#315545;">Recordatorio de tu cita 🌿</h1>

            <p>Hola <strong>{nombre}</strong>,</p>

            <p>Te recordamos que tienes una cita programada en Huancayoga.</p>

            <ul>
                <li><strong>Servicio:</strong> {servicio}</li>
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


@app.route("/")
def index():
    return render_template("public/index.html")


@app.route("/check-db")
def check_db():
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
        SELECT id, nombre, precio
        FROM servicios
        WHERE estado = 'activo'
    """)

    servicios = cur.fetchall()

    if request.method == "POST":
        cliente_id = session["cliente_id"]
        nombre_cliente = request.form["nombre_cliente"]
        celular = request.form["celular"]
        correo = request.form["correo"]
        servicio_id = request.form["servicio_id"]
        fecha = request.form["fecha"]
        hora = request.form["hora"]
        comentario = request.form["comentario"]

        cur.execute("""
            INSERT INTO reservas
            (
                cliente_id,
                nombre_cliente,
                celular,
                correo,
                servicio_id,
                fecha,
                hora,
                comentario,
                estado
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendiente')
        """, (
            cliente_id,
            nombre_cliente,
            celular,
            correo,
            servicio_id,
            fecha,
            hora,
            comentario
        ))

        mysql.connection.commit()
        cur.close()

        flash(
            "Reserva registrada correctamente. La dueña revisará tu solicitud.",
            "success"
        )

        return redirect(url_for("cliente_mis_citas"))

    cur.close()

    return render_template(
        "reservar.html",
        servicios=servicios
    )


# ==========================
# MÓDULO DE PRODUCTOS
# ==========================

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
        imagen = request.form["imagen"]

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
        imagen = request.form["imagen"]
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


@app.route("/admin/productos/eliminar/<int:id>")
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
        usuario = request.form["usuario"]
        password = request.form["password"]

        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, nombre, usuario, password, rol
            FROM usuarios
            WHERE usuario = %s AND password = %s
        """, (usuario, password))

        admin = cur.fetchone()
        cur.close()

        if admin:
            session["admin_id"] = admin[0]
            session["admin_nombre"] = admin[1]
            session["admin_usuario"] = admin[2]
            session["admin_rol"] = admin[4]

            flash("Bienvenido al panel administrativo.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Usuario o contraseña incorrectos.", "danger")
            return redirect(url_for("admin_login"))

    return render_template("login.html")


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


@app.route("/admin/reservas")
def admin_reservas():
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT 
            r.id,
            r.nombre_cliente,
            r.celular,
            r.correo,
            s.nombre AS servicio,
            r.fecha,
            r.hora,
            r.comentario,
            r.estado,
            r.fecha_registro
        FROM reservas r
        INNER JOIN servicios s ON r.servicio_id = s.id
        ORDER BY r.fecha_registro DESC
    """)

    reservas = cur.fetchall()
    cur.close()

    return render_template("admin/reservas.html", reservas=reservas)


@app.route("/admin/reserva/estado/<int:id>/<estado>")
def cambiar_estado_reserva(id, estado):
    if "admin_id" not in session:
        flash("Debes iniciar sesión para ingresar al panel.", "warning")
        return redirect(url_for("admin_login"))

    estados_permitidos = ["pendiente", "confirmada", "cancelada", "atendida"]

    if estado not in estados_permitidos:
        flash("Estado no permitido.", "danger")
        return redirect(url_for("admin_reservas"))

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT 
        r.nombre_cliente,
        r.correo,
        s.nombre,
        r.fecha,
        r.hora
    FROM reservas r
    INNER JOIN servicios s ON r.servicio_id = s.id
    WHERE r.id = %s
""", (id,))

    reserva = cur.fetchone()

    cur.execute("""
            UPDATE reservas
            SET estado = %s
            WHERE id = %s
    """, (estado, id))

    mysql.connection.commit()
    cur.close()

    if reserva and estado == "confirmada":
        nombre_cliente = reserva[0]
        correo_cliente = reserva[1]
        servicio = reserva[2]
        fecha = reserva[3]
        hora = reserva[4]

        enviar_correo(
            correo_cliente,
            "Tu cita en Huancayoga fue confirmada ✅",
            correo_confirmacion_cita(nombre_cliente, servicio, fecha, hora)
    )

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


@app.route("/admin/pedido/estado/<int:id>/<estado>")
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

@app.route("/cliente/login", methods=["GET", "POST"])
def cliente_login():
    if request.method == "POST":
        dni = request.form["dni"]
        password = request.form["password"]

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
            flash("Tu cuenta no tiene contraseña registrada. Regístrate nuevamente o recupera tu contraseña.", "warning")
            return redirect(url_for("cliente_login"))

        if not check_password_hash(cliente[3], password):
            flash("La contraseña es incorrecta.", "danger")
            return redirect(url_for("cliente_login"))

        session["cliente_id"] = cliente[0]
        session["cliente_dni"] = cliente[1]
        session["cliente_nombre"] = cliente[2]

        flash("Bienvenido a Huancayoga.", "success")
        return redirect(url_for("cliente_dashboard"))

    return render_template("cliente_login.html")

@app.route("/cliente/registro", methods=["GET", "POST"])
def cliente_registro():
    dni_recibido = request.args.get("dni", "")

    if request.method == "POST":
        dni = request.form["dni"].strip()
        nombres = request.form["nombres"].strip()
        apellido_paterno = request.form["apellido_paterno"].strip()
        apellido_materno = request.form["apellido_materno"].strip()
        celular = request.form["celular"].strip()
        correo = request.form["correo"].strip()
        password = request.form["password"]
        confirmar_password = request.form["confirmar_password"]

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
            SELECT id
            FROM clientes
            WHERE dni = %s
        """, (dni,))

        existe = cur.fetchone()

        if existe:
            cur.close()
            flash("Este DNI ya está registrado. Inicia sesión.", "warning")
            return redirect(url_for("cliente_login"))

        # Registrar cliente con contraseña cifrada
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
        dni_recibido=dni_recibido
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
            r.estado
        FROM reservas r
        INNER JOIN servicios s
            ON r.servicio_id = s.id
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
        ultima_publicacion=ultima_publicacion
    )
@app.route("/cliente/mis-citas")
def cliente_mis_citas():
    if "cliente_id" not in session:
        flash("Debes iniciar sesión como cliente.", "warning")
        return redirect(url_for("cliente_login"))

    cliente_id = session["cliente_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            r.id,
            s.nombre,
            r.fecha,
            r.hora,
            r.comentario,
            r.estado,
            r.fecha_registro
        FROM reservas r
        INNER JOIN servicios s
            ON r.servicio_id = s.id
        WHERE r.cliente_id = %s
        ORDER BY r.fecha DESC, r.hora DESC
    """, (cliente_id,))

    citas = cur.fetchall()
    cur.close()

    return render_template(
        "cliente/mis_citas.html",
        citas=citas
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

@app.route("/admin/reserva/recordatorio/<int:id>")
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
            r.hora
        FROM reservas r
        INNER JOIN servicios s ON r.servicio_id = s.id
        WHERE r.id = %s
    """, (id,))

    reserva = cur.fetchone()
    cur.close()

    if reserva:
        enviar_correo(
            reserva[1],
            "Recordatorio de tu cita en Huancayoga 🌿",
            correo_recordatorio_cita(reserva[0], reserva[2], reserva[3], reserva[4])
        )

        flash("Recordatorio enviado correctamente.", "success")
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
        imagen = request.form["imagen"]
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
        imagen = request.form["imagen"]
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


@app.route("/admin/publicaciones/eliminar/<int:id>")
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
            return None

        texto = extraer_texto_openai(respuesta_http.json())

        if not texto:
            return None

        return normalizar_respuesta_ia(texto, mensaje)

    except Exception as e:
        print(f"Error al consultar OpenAI para el chatbot: {e}")
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
    app.run(debug=True)
