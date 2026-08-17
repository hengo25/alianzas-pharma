import os
import json

from flask import Flask, render_template, request, redirect, url_for, make_response
from flask_cors import CORS

import firebase_admin
from firebase_admin import credentials, firestore


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)
CORS(app)

# Vercel necesita encontrar la aplicación Flask
main = app


# ============================================================
# FIREBASE
# ============================================================

db = None


def conectar_firebase():
    global db

    try:
        # ----------------------------------------------------
        # Buscar llave Firebase
        # ----------------------------------------------------

        base_dir = os.path.dirname(os.path.abspath(__file__))

        posibles_rutas = [
            os.path.join(base_dir, "llave-firebase.json"),
            "/var/task/llave-firebase.json",
        ]

        ruta_llave = None

        for ruta in posibles_rutas:
            if os.path.exists(ruta):
                ruta_llave = ruta
                break

        if not ruta_llave:
            print("❌ FIREBASE: No se encontró llave-firebase.json")
            return None

        print(f"🔑 FIREBASE: usando llave {ruta_llave}")

        # ----------------------------------------------------
        # Leer credenciales
        # ----------------------------------------------------

        with open(ruta_llave, "r", encoding="utf-8") as archivo:
            datos_json = json.load(archivo)

        # Corregir saltos de línea de private_key
        if "private_key" in datos_json:
            datos_json["private_key"] = datos_json["private_key"].replace(
                "\\n",
                "\n"
            )

        # ----------------------------------------------------
        # Inicializar Firebase
        # ----------------------------------------------------

        if not firebase_admin._apps:
            cred = credentials.Certificate(datos_json)

            firebase_app = firebase_admin.initialize_app(
                cred
            )

            print("🚀 FIREBASE: aplicación inicializada")

        else:
            firebase_app = firebase_admin.get_app()

            print("♻️ FIREBASE: usando aplicación existente")

        # ----------------------------------------------------
        # Firestore
        # ----------------------------------------------------

        firestore_db = firestore.client(
            app=firebase_app
        )

        # ----------------------------------------------------
        # PRUEBA REAL DE CONEXIÓN
        # ----------------------------------------------------

        firestore_db.collection("clientes").limit(1).stream()

        print("✅ FIREBASE: conexión con Firestore funcionando")

        return firestore_db

    except Exception as e:

        print(
            f"❌ FIREBASE ERROR: {type(e).__name__}: {e}"
        )

        return None


# Conectar Firebase al iniciar la aplicación
db = conectar_firebase()


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def obtener_cliente_logueado():

    nit_usuario = request.cookies.get("cliente_nit")

    if not nit_usuario:
        return None

    if not db:
        return None

    try:

        doc = (
            db.collection("clientes")
            .document(nit_usuario)
            .get()
        )

        if doc.exists:
            return doc.to_dict()

        return None

    except Exception as e:

        print(
            f"❌ ERROR obteniendo cliente: {e}"
        )

        return None


def cargar_productos():

    lista_productos = []

    if not db:
        print("❌ PRODUCTOS: Firebase no está conectado")
        return lista_productos

    try:

        productos_ref = (
            db.collection("productos")
            .stream()
        )

        for doc in productos_ref:

            p = doc.to_dict()

            try:
                precio = int(p.get("precio", 0))
            except:
                precio = 0

            try:
                existencias = int(
                    p.get("existencias", 0)
                )
            except:
                existencias = 0

            lista_productos.append(
                {
                    "id": doc.id,

                    "nombre": p.get(
                        "nombre",
                        "Medicamento sin nombre"
                    ),

                    "precio": precio,

                    "imagen": p.get(
                        "imagen",
                        "/public/placeholder.jpg"
                    ),

                    "existencias": existencias,
                }
            )

        lista_productos.sort(
            key=lambda x: x["nombre"].lower()
        )

        print(
            f"✅ PRODUCTOS: {len(lista_productos)} productos cargados"
        )

    except Exception as e:

        print(
            f"❌ PRODUCTOS ERROR: {type(e).__name__}: {e}"
        )

    return lista_productos


# ============================================================
# INICIO
# ============================================================

@app.route("/")
def inicio():

    cliente = obtener_cliente_logueado()

    # --------------------------------------------------------
    # Si no hay sesión, mostrar el MISMO formulario
    # --------------------------------------------------------

    if not cliente:

        return """
<!DOCTYPE html>
<html lang="es">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>Ingreso - Alianzas Pharma</title>

<style>

body{
    font-family:'Segoe UI',sans-serif;
    background:#f4f6f9;
    display:flex;
    align-items:center;
    justify-content:center;
    height:100vh;
    margin:0;
}

.box{
    background:white;
    padding:40px 30px;
    border-radius:16px;
    box-shadow:0 10px 25px rgba(0,0,0,0.05);
    text-align:center;
    width:320px;
}

input{
    width:92%;
    padding:12px;
    margin-bottom:12px;
    border:1px solid #cbd5e1;
    border-radius:8px;
    outline:none;
    font-size:1rem;
}

.btn{
    background:#3498db;
    color:white;
    border:none;
    padding:12px;
    border-radius:25px;
    font-weight:bold;
    cursor:pointer;
    width:100%;
    font-size:1rem;
    margin-top:10px;
    box-shadow:0 4px 12px rgba(52,152,219,0.2);
}

.btn:hover{
    background:#2980b9;
}

</style>

</head>

<body>

<div class="box">

<h2 style="
color:#2c3e50;
margin:0 0 5px 0;
font-size:1.4rem;
">
ALIANZAS PHARMA
</h2>

<p style="
color:#64748b;
font-size:0.85rem;
margin-bottom:25px;
font-weight:bold;
">
Portal de Pedidos para Droguerías Afiliadas
</p>

<form
method="POST"
action="/ingresar-portal"
>

<input
type="text"
name="nit"
placeholder="Escribe el NIT de la Droguería"
required
>

<input
type="password"
name="password"
placeholder="Contraseña secreta"
required
>

<button
type="submit"
class="btn"
>
Iniciar Sesión
</button>

</form>

<div style="
display:flex;
justify-content:space-between;
margin-top:25px;
">

<a
href="/registro-cliente"
style="
color:#3498db;
text-decoration:none;
font-size:0.85rem;
font-weight:600;
"
>
Crear Cuenta
</a>

<a
href="/recuperar-clave"
style="
color:#e67e22;
text-decoration:none;
font-size:0.85rem;
font-weight:600;
"
>
Olvidé mi clave
</a>

</div>

</div>

</body>

</html>
"""

    # --------------------------------------------------------
    # Usuario logueado
    # --------------------------------------------------------

    productos = cargar_productos()

    return render_template(
        "index.html",
        productos=productos,
        cliente=cliente
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/ingresar-portal",
    methods=["POST"]
)
def ingresar_portal():

    nit = request.form.get(
        "nit",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    ).strip()

    print(
        f"🔎 LOGIN: intentando NIT {nit}"
    )

    # --------------------------------------------------------
    # Validación básica
    # --------------------------------------------------------

    if not nit or not password:

        return """
<html>
<head>
<title>Datos incompletos</title>
<style>

body{
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
margin:0;
}

.box{
background:white;
padding:40px;
border-radius:16px;
text-align:center;
box-shadow:0 10px 25px rgba(0,0,0,0.05);
}

a{
background:#3498db;
color:white;
padding:10px 20px;
border-radius:20px;
text-decoration:none;
font-weight:bold;
display:inline-block;
margin-top:15px;
}

</style>
</head>

<body>

<div class="box">

<h2>⚠️ Datos incompletos</h2>

<p>
Debes ingresar el NIT y la contraseña.
</p>

<a href="/">
Intentar de Nuevo
</a>

</div>

</body>
</html>
"""

    # --------------------------------------------------------
    # Firebase desconectado
    # --------------------------------------------------------

    if not db:

        print(
            "❌ LOGIN: Firebase no está conectado"
        )

        return """
<html>
<head>
<title>Error de conexión</title>

<style>

body{
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
margin:0;
}

.box{
background:white;
padding:40px;
border-radius:16px;
text-align:center;
box-shadow:0 10px 25px rgba(0,0,0,0.05);
}

a{
background:#3498db;
color:white;
padding:10px 20px;
border-radius:20px;
text-decoration:none;
font-weight:bold;
display:inline-block;
margin-top:15px;
}

</style>

</head>

<body>

<div class="box">

<h2>❌ Error de conexión</h2>

<p>
No fue posible conectar con la base de datos.
</p>

<a href="/">
Intentar de Nuevo
</a>

</div>

</body>
</html>
"""

    # --------------------------------------------------------
    # Buscar cliente en Firestore
    # --------------------------------------------------------

    try:

        print(
            f"🔎 FIREBASE: buscando clientes/{nit}"
        )

        doc = (
            db.collection("clientes")
            .document(nit)
            .get()
        )

        # ----------------------------------------------------
        # NIT no existe
        # ----------------------------------------------------

        if not doc.exists:

            print(
                f"❌ LOGIN: NIT {nit} no existe"
            )

            return """
<html>
<head>
<title>Datos incorrectos</title>

<style>

body{
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
margin:0;
}

.box{
background:white;
padding:40px;
border-radius:16px;
text-align:center;
box-shadow:0 10px 25px rgba(0,0,0,0.05);
}

a{
background:#3498db;
color:white;
padding:10px 20px;
border-radius:20px;
text-decoration:none;
font-weight:bold;
display:inline-block;
margin-top:15px;
}

</style>

</head>

<body>

<div class="box">

<h2>❌ NIT no registrado</h2>

<p>
El NIT no está registrado en Alianzas Pharma.
</p>

<a href="/">
Intentar de Nuevo
</a>

</div>

</body>
</html>
"""

        # ----------------------------------------------------
        # Datos del cliente
        # ----------------------------------------------------

        datos_cliente = doc.to_dict()

        password_db = str(
            datos_cliente.get(
                "password",
                ""
            )
        ).strip()

        # ----------------------------------------------------
        # Comparar contraseña
        # ----------------------------------------------------

        if password_db != password:

            print(
                f"❌ LOGIN: contraseña incorrecta para {nit}"
            )

            return """
<html>
<head>
<title>Datos incorrectos</title>

<style>

body{
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
margin:0;
}

.box{
background:white;
padding:40px;
border-radius:16px;
text-align:center;
box-shadow:0 10px 25px rgba(0,0,0,0.05);
}

a{
background:#3498db;
color:white;
padding:10px 20px;
border-radius:20px;
text-decoration:none;
font-weight:bold;
display:inline-block;
margin-top:15px;
}

</style>

</head>

<body>

<div class="box">

<h2>❌ Contraseña Incorrecta</h2>

<p>
La contraseña no coincide con la registrada en Firebase.
</p>

<a href="/">
Intentar de Nuevo
</a>

</div>

</body>
</html>
"""

        # ----------------------------------------------------
        # LOGIN CORRECTO
        # ----------------------------------------------------

        print(
            f"✅ LOGIN CORRECTO: {nit}"
        )

        productos = cargar_productos()

        # ----------------------------------------------------
        # Mostrar tienda
        # ----------------------------------------------------

        resp = make_response(
            render_template(
                "index.html",
                productos=productos,
                cliente=datos_cliente
            )
        )

        # Cookie del cliente
        resp.set_cookie(
            "cliente_nit",
            nit,
            path="/",
            httponly=True,
            secure=True,
            samesite="None"
        )

        return resp

    # --------------------------------------------------------
    # Error Firebase
    # --------------------------------------------------------

    except Exception as e:

        print(
            f"❌ LOGIN FIREBASE ERROR: "
            f"{type(e).__name__}: {e}"
        )

        return """
<html>
<head>
<title>Error de Firebase</title>

<style>

body{
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
margin:0;
}

.box{
background:white;
padding:40px;
border-radius:16px;
text-align:center;
box-shadow:0 10px 25px rgba(0,0,0,0.05);
}

a{
background:#3498db;
color:white;
padding:10px 20px;
border-radius:20px;
text-decoration:none;
font-weight:bold;
display:inline-block;
margin-top:15px;
}

</style>

</head>

<body>

<div class="box">

<h2>❌ Error de conexión con Firebase</h2>

<p>
No fue posible consultar la base de datos.
</p>

<a href="/">
Intentar de Nuevo
</a>

</div>

</body>
</html>
"""


# ============================================================
# REGISTRO DE CLIENTE
# ============================================================

@app.route(
    "/registro-cliente",
    methods=["GET", "POST"]
)
def registro_cliente():

    if request.method == "POST":

        nit = request.form.get(
            "nit",
            ""
        ).strip()

        nombre = request.form.get(
            "nombre",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        if db:

            try:

                db.collection(
                    "clientes"
                ).document(
                    nit
                ).set(
                    {
                        "nit": nit,
                        "nombre": nombre,
                        "password": password
                    }
                )

                print(
                    f"✅ CLIENTE REGISTRADO: {nit}"
                )

                return redirect(
                    url_for("inicio")
                )

            except Exception as e:

                print(
                    f"❌ ERROR registrando cliente: {e}"
                )

    return render_template(
        "registro_cliente.html"
    )


# ============================================================
# SALIR
# ============================================================

@app.route("/salir")
def salir():

    resp = make_response(
        redirect(
            url_for("inicio")
        )
    )

    resp.set_cookie(
        "cliente_nit",
        "",
        expires=0,
        path="/"
    )

    return resp
