import os
import json

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    make_response
)

from flask_cors import CORS

import firebase_admin
from firebase_admin import credentials, firestore


# =========================================================
# APLICACIÓN
# =========================================================

app = Flask(__name__)
CORS(app)

# Necesario para Vercel
main = app


# =========================================================
# FIREBASE
# =========================================================

db = None
firebase_inicializado = False


def conectar_firebase():

    global db
    global firebase_inicializado

    # Si ya está conectado, reutilizamos la conexión
    if firebase_inicializado and db is not None:
        return db

    try:

        print("🔥 FIREBASE: iniciando conexión...")

        # -------------------------------------------------
        # OPCIÓN 1:
        # Buscar archivo llave-firebase.json
        # -------------------------------------------------

        base_dir = os.path.dirname(os.path.abspath(__file__))

        ruta_llave = os.path.join(
            base_dir,
            "llave-firebase.json"
        )

        if not os.path.exists(ruta_llave):
            ruta_llave = "/var/task/llave-firebase.json"


        # -------------------------------------------------
        # CARGAR CREDENCIALES
        # -------------------------------------------------

        if os.path.exists(ruta_llave):

            print(
                f"🔥 FIREBASE: usando archivo {ruta_llave}"
            )

            with open(
                ruta_llave,
                "r",
                encoding="utf-8"
            ) as archivo:

                datos_json = json.load(archivo)

            # Corregir saltos de línea de private_key
            if "private_key" in datos_json:

                datos_json["private_key"] = (
                    datos_json["private_key"]
                    .replace("\\n", "\n")
                )

            # Crear aplicación Firebase solamente una vez
            if not firebase_admin._apps:

                cred = credentials.Certificate(
                    datos_json
                )

                firebase_admin.initialize_app(cred)

                print(
                    "✅ FIREBASE: aplicación inicializada"
                )

            else:

                print(
                    "✅ FIREBASE: aplicación ya estaba inicializada"
                )

        else:

            # -------------------------------------------------
            # OPCIÓN 2:
            # Credenciales mediante variable de entorno
            # -------------------------------------------------

            firebase_json = os.environ.get(
                "FIREBASE_SERVICE_ACCOUNT"
            )

            if not firebase_json:

                print(
                    "❌ FIREBASE: no se encontró "
                    "llave-firebase.json ni "
                    "FIREBASE_SERVICE_ACCOUNT"
                )

                return None

            print(
                "🔥 FIREBASE: usando variable "
                "FIREBASE_SERVICE_ACCOUNT"
            )

            datos_json = json.loads(firebase_json)

            if "private_key" in datos_json:

                datos_json["private_key"] = (
                    datos_json["private_key"]
                    .replace("\\n", "\n")
                )

            if not firebase_admin._apps:

                cred = credentials.Certificate(
                    datos_json
                )

                firebase_admin.initialize_app(cred)

                print(
                    "✅ FIREBASE: aplicación inicializada"
                )


        # -------------------------------------------------
        # CREAR CLIENTE FIRESTORE
        # -------------------------------------------------

        db = firestore.client()

        firebase_inicializado = True

        print(
            "🚀 FIREBASE: conexión preparada correctamente"
        )

        return db

    except Exception as e:

        print(
            "❌ FIREBASE ERROR:",
            repr(e)
        )

        db = None
        firebase_inicializado = False

        return None


# =========================================================
# OBTENER CLIENTE LOGUEADO
# =========================================================

def obtener_cliente_logueado():

    nit_usuario = request.cookies.get(
        "cliente_nit"
    )

    if not nit_usuario:
        return None

    base_datos = conectar_firebase()

    if base_datos is None:
        return None

    try:

        doc = (
            base_datos
            .collection("clientes")
            .document(nit_usuario)
            .get()
        )

        if doc.exists:
            return doc.to_dict()

        return None

    except Exception as e:

        print(
            "❌ ERROR obteniendo cliente:",
            repr(e)
        )

        return None


# =========================================================
# CARGAR PRODUCTOS
# =========================================================

def obtener_productos():

    base_datos = conectar_firebase()

    if base_datos is None:
        print(
            "⚠️ PRODUCTOS: Firebase no disponible"
        )

        return []

    lista = []

    try:

        print(
            "📦 PRODUCTOS: consultando Firestore..."
        )

        productos_ref = (
            base_datos
            .collection("productos")
            .stream()
        )

        for doc in productos_ref:

            p = doc.to_dict()

            try:
                precio = int(
                    p.get("precio", 0)
                )
            except:
                precio = 0

            try:
                existencias = int(
                    p.get("existencias", 0)
                )
            except:
                existencias = 0

            lista.append({

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

                "existencias": existencias
            })

        lista.sort(
            key=lambda x:
            x["nombre"].lower()
        )

        print(
            f"✅ PRODUCTOS: {len(lista)} productos cargados"
        )

    except Exception as e:

        print(
            "❌ PRODUCTOS ERROR:",
            repr(e)
        )

    return lista


# =========================================================
# INICIO
# =========================================================

@app.route("/")
def inicio():

    cliente = obtener_cliente_logueado()

    # -----------------------------------------------------
    # SI NO ESTÁ LOGUEADO
    # -----------------------------------------------------

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

<h2
style="
color:#2c3e50;
margin:0 0 5px 0;
font-size:1.4rem;
">
ALIANZAS PHARMA
</h2>

<p
style="
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

<div
style="
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
">
Crear Cuenta
</a>

<a
href="/recuperar-clave"
style="
color:#e67e22;
text-decoration:none;
font-size:0.85rem;
font-weight:600;
">
Olvidé mi clave
</a>

</div>

</div>

</body>

</html>
"""


    # -----------------------------------------------------
    # CLIENTE LOGUEADO
    # -----------------------------------------------------

    lista = obtener_productos()

    return render_template(
        "index.html",
        productos=lista,
        cliente=cliente
    )


# =========================================================
# LOGIN
# =========================================================

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


    # -----------------------------------------------------
    # VALIDACIÓN
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # CONECTAR FIREBASE
    # -----------------------------------------------------

    base_datos = conectar_firebase()

    if base_datos is None:

        print(
            "❌ LOGIN: Firebase no está conectado."
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


    # -----------------------------------------------------
    # BUSCAR CLIENTE
    # -----------------------------------------------------

    try:

        print(
            f"🔎 LOGIN: buscando NIT {nit}"
        )

        doc = (
            base_datos
            .collection("clientes")
            .document(nit)
            .get()
        )


        if not doc.exists:

            print(
                f"❌ LOGIN: NIT {nit} no existe"
            )

            return """
<html>

<head>

<title>NIT no registrado</title>

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


        # -------------------------------------------------
        # DATOS DEL CLIENTE
        # -------------------------------------------------

        datos_cliente = doc.to_dict()

        pass_db = str(
            datos_cliente.get(
                "password",
                ""
            )
        ).strip()


        # -------------------------------------------------
        # COMPROBAR CONTRASEÑA
        # -------------------------------------------------

        if pass_db != password:

            print(
                f"❌ LOGIN: contraseña incorrecta "
                f"para NIT {nit}"
            )

            return """
<html>

<head>

<title>Contraseña incorrecta</title>

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


        # -------------------------------------------------
        # LOGIN CORRECTO
        # -------------------------------------------------

        print(
            f"✅ LOGIN CORRECTO: NIT {nit}"
        )

        lista_productos = obtener_productos()


        # -------------------------------------------------
        # MOSTRAR TIENDA
        # -------------------------------------------------

        resp = make_response(
            render_template(
                "index.html",
                productos=lista_productos,
                cliente=datos_cliente
            )
        )


        resp.set_cookie(
            "cliente_nit",
            nit,
            path="/",
            httponly=True,
            secure=True,
            samesite="None"
        )


        return resp


    except Exception as e:

        print(
            "❌ LOGIN FIREBASE ERROR:",
            repr(e)
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


# =========================================================
# REGISTRO
# =========================================================

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


        base_datos = conectar_firebase()

        if base_datos is not None:

            try:

                base_datos.collection(
                    "clientes"
                ).document(nit).set({

                    "nit": nit,

                    "nombre": nombre,

                    "password": password

                })

                return redirect(
                    url_for("inicio")
                )

            except Exception as e:

                print(
                    "❌ ERROR registrando cliente:",
                    repr(e)
                )


    return render_template(
        "registro_cliente.html"
    )


# =========================================================
# SALIR
# =========================================================

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
