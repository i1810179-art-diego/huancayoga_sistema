from flask import Flask, render_template, request, redirect, url_for, flash,session
from flask_mysqldb import MySQL
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

# Configuración de MySQL
app.config["MYSQL_HOST"] = os.getenv("DB_HOST")
app.config["MYSQL_USER"] = os.getenv("DB_USER")
app.config["MYSQL_PASSWORD"] = os.getenv("DB_PASSWORD")
app.config["MYSQL_DB"] = os.getenv("DB_NAME")

mysql = MySQL(app)


@app.route("/")
def index():
    return render_template("index.html")


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
        flash("Para reservar una cita primero debes registrarte o iniciar sesión.", "warning")
        return redirect(url_for("cliente_login"))
    cur = mysql.connection.cursor()

    # Obtener servicios activos para mostrarlos en el formulario
    cur.execute("SELECT id, nombre, precio FROM servicios WHERE estado = 'activo'")
    servicios = cur.fetchall()

    if request.method == "POST":
        nombre_cliente = request.form["nombre_cliente"]
        celular = request.form["celular"]
        correo = request.form["correo"]
        servicio_id = request.form["servicio_id"]
        fecha = request.form["fecha"]
        hora = request.form["hora"]
        comentario = request.form["comentario"]

        cur.execute("""
            INSERT INTO reservas 
            (nombre_cliente, celular, correo, servicio_id, fecha, hora, comentario, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pendiente')
        """, (
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

        flash("Reserva registrada correctamente. El dueño se comunicará contigo para confirmar.", "success")
        return redirect(url_for("reservar"))

    cur.close()
    return render_template("reservar.html", servicios=servicios)



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

        cur.execute("""
            INSERT INTO pedidos
            (nombre_cliente, celular, producto_id, cantidad, total, estado)
            VALUES (%s, %s, %s, %s, %s, 'pendiente')
        """, (
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
        UPDATE reservas
        SET estado = %s
        WHERE id = %s
    """, (estado, id))

    mysql.connection.commit()
    cur.close()

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

        flash("Registro completado correctamente.", "success")
        return redirect(url_for("cliente_dashboard"))

    return render_template("cliente_registro.html", dni_recibido=dni_recibido)


@app.route("/cliente/dashboard")
def cliente_dashboard():
    if "cliente_id" not in session:
        flash("Primero debes iniciar sesión o registrarte.", "warning")
        return redirect(url_for("cliente_login"))

    return render_template("cliente_dashboard.html")


@app.route("/cliente/logout")
def cliente_logout():
    session.pop("cliente_id", None)
    session.pop("cliente_dni", None)
    session.pop("cliente_nombre", None)

    flash("Sesión de cliente cerrada correctamente.", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)