from flask import Flask, render_template, request, redirect, url_for, flash,session
from flask_mysqldb import MySQL
from dotenv import load_dotenv
from flask_mail import Mail, Message
import os
import requests

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
app.config["MAIL_TIMEOUT"] = 10

mail = Mail(app)

mysql = MySQL(app)


# funciones

def enviar_correo(destinatario, asunto, contenido_html):
    if not destinatario:
        print("Correo omitido: destinatario vacío.")
        return False

    if not app.config.get("MAIL_ENABLED", False):
        print(f"Correo omitido para {destinatario}: MAIL_ENABLED está desactivado.")
        return False

    try:
        mensaje = Message(
            subject=asunto,
            recipients=[destinatario],
            html=contenido_html
        )

        mail.send(mensaje)
        print(f"Correo enviado correctamente a {destinatario}")
        return True

    except Exception as e:
        print(f"No se pudo enviar correo a {destinatario}: {e}")
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

        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, dni, nombres, apellido_paterno, apellido_materno
            FROM clientes
            WHERE dni = %s AND estado = 'activo'
        """, (dni,))

        cliente = cur.fetchone()
        cur.close()

        if cliente:
            session["cliente_id"] = cliente[0]
            session["cliente_dni"] = cliente[1]
            session["cliente_nombre"] = cliente[2]

            flash("Bienvenido a Huancayoga.", "success")
            return redirect(url_for("cliente_dashboard"))
        else:
            flash("DNI no registrado. Primero debes registrarte.", "warning")
            return redirect(url_for("cliente_registro", dni=dni))

    return render_template("cliente_login.html")


@app.route("/cliente/registro", methods=["GET", "POST"])
def cliente_registro():
    dni_recibido = request.args.get("dni", "")

    if request.method == "POST":
        dni = request.form["dni"]
        nombres = request.form["nombres"]
        apellido_paterno = request.form["apellido_paterno"]
        apellido_materno = request.form["apellido_materno"]
        celular = request.form["celular"]
        correo = request.form["correo"]

        cur = mysql.connection.cursor()

        cur.execute("SELECT id FROM clientes WHERE dni = %s", (dni,))
        existe = cur.fetchone()

        if existe:
            cur.close()
            flash("Este DNI ya está registrado. Inicia sesión.", "warning")
            return redirect(url_for("cliente_login"))

        cur.execute("""
            INSERT INTO clientes
            (dni, nombres, apellido_paterno, apellido_materno, celular, correo, estado)
            VALUES (%s, %s, %s, %s, %s, %s, 'activo')
        """, (
            dni,
            nombres,
            apellido_paterno,
            apellido_materno,
            celular,
            correo
        ))

        mysql.connection.commit()

        cur.execute("""
            SELECT id, dni, nombres
            FROM clientes
            WHERE dni = %s
        """, (dni,))

        cliente = cur.fetchone()
        cur.close()

        session["cliente_id"] = cliente[0]
        session["cliente_dni"] = cliente[1]
        session["cliente_nombre"] = cliente[2]
        
        correo_enviado = enviar_correo(
    correo,
    "Bienvenido a Huancayoga 🌿",
    correo_bienvenida(nombres)
)
        if correo_enviado:
            flash("Registro completado correctamente. Te enviamos un correo de bienvenida.", "success")
        else:
            flash("Registro completado correctamente.", "success")

        return redirect(url_for("cliente_dashboard"))


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


if __name__ == "__main__":
    app.run(debug=True)