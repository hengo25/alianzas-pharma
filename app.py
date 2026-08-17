import os
import json
from urllib.parse import quote

import requests

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    make_response
)

from flask_cors import CORS

from google.oauth2 import service_account
from google.auth.transport.requests import Request


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)
CORS(app)

# Vercel reconoce "app" directamente
main = app


# =========================================================
# CONFIGURACIÓN FIREBASE REST
# =========================================================

FIRESTORE_SCOPE = "https://www.googleapis.com/auth/datastore"

firebase_credentials = None
firebase_project_id = None


# =========================================================
# CARGAR LLAVE FIREBASE
# =========================================================
# CARGAR LLAVE FIREBASE
# ============================================================

base_dir = os.path.dirname(
    os.path.abspath(__file__)
)

print("==============================================")
print("🔐 CARGANDO CREDENCIALES FIREBASE")
print("==============================================")

firebase_credentials_env = os.getenv("FIREBASE_CREDENTIALS")

if not firebase_credentials_env:
    raise ValueError(
        "La variable FIREBASE_CREDENTIALS no está configurada"
    )

try:
    datos_firebase = json.loads(firebase_credentials_env)
except json.JSONDecodeError as e:
    raise ValueError(
        f"FIREBASE_CREDENTIALS no contiene un JSON válido: {e}"
    )

print("✅ FIREBASE_CREDENTIALS encontrada")
print(f"📁 Proyecto: {datos_firebase.get('project_id')}")

# ============================================================
# CORREGIR PRIVATE KEY
# ============================================================

if "private_key" in datos_firebase:
    datos_firebase["private_key"] = (
        datos_firebase["private_key"]
        .replace("\\n", "\n")
    )

firebase_project_id = datos_firebase.get(
    "project_id"
)

if not firebase_project_id:
    raise ValueError(
        "La llave Firebase no contiene project_id"
    )


    # -----------------------------------------------------
    # CREAR CREDENCIALES
    # -----------------------------------------------------

   # ============================================================
# CREAR CREDENCIALES
# ============================================================

try:
    firebase_credentials = (
        service_account.Credentials.from_service_account_info(
            datos_firebase,
            scopes=[FIRESTORE_SCOPE]
        )
    )

    print("==============================================")
    print("✅ LLAVE FIREBASE CARGADA")
    print(f"📁 Proyecto: {firebase_project_id}")
    print("==============================================")

except Exception as e:
    firebase_credentials = None

    print("==============================================")
    print("❌ ERROR CARGANDO FIREBASE")
    print(str(e))
    print("==============================================")


# ============================================================
# OBTENER TOKEN GOOGLE
# ============================================================

# =========================================================
# OBTENER TOKEN GOOGLE
# =========================================================

def obtener_token_firebase():

    if not firebase_credentials:

        raise RuntimeError(
            "Las credenciales de Firebase no están disponibles."
        )

    try:

        if not firebase_credentials.valid:

            firebase_credentials.refresh(
                Request()
            )

        return firebase_credentials.token

    except Exception as e:

        print(
            f"❌ Error obteniendo token Firebase: {e}"
        )

        raise


# =========================================================
# URL BASE FIRESTORE REST
# =========================================================

def firestore_base_url():

    if not firebase_project_id:

        raise RuntimeError(
            "No existe firebase_project_id."
        )

    return (
        "https://firestore.googleapis.com/v1/"
        f"projects/{quote(firebase_project_id, safe='')}"
        "/databases/(default)/documents"
    )


# =========================================================
# HEADERS FIRESTORE
# =========================================================

def firestore_headers():

    token = obtener_token_firebase()

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


# =========================================================
# CONVERTIR FIRESTORE VALUE -> PYTHON
# =========================================================

def firestore_value_to_python(value):

    if not isinstance(value, dict):
        return None

    if "stringValue" in value:
        return value["stringValue"]

    if "integerValue" in value:

        try:
            return int(value["integerValue"])
        except:
            return 0

    if "doubleValue" in value:

        try:
            return float(value["doubleValue"])
        except:
            return 0

    if "booleanValue" in value:
        return value["booleanValue"]

    if "nullValue" in value:
        return None

    if "timestampValue" in value:
        return value["timestampValue"]

    if "referenceValue" in value:
        return value["referenceValue"]

    if "bytesValue" in value:
        return value["bytesValue"]

    if "geoPointValue" in value:
        return value["geoPointValue"]

    if "arrayValue" in value:

        values = value["arrayValue"].get(
            "values",
            []
        )

        return [
            firestore_value_to_python(v)
            for v in values
        ]

    if "mapValue" in value:

        fields = value["mapValue"].get(
            "fields",
            {}
        )

        return firestore_fields_to_python(
            fields
        )

    return None


# =========================================================
# CONVERTIR FIRESTORE FIELDS -> PYTHON
# =========================================================

def firestore_fields_to_python(fields):

    resultado = {}

    if not fields:
        return resultado

    for nombre, valor in fields.items():

        resultado[nombre] = (
            firestore_value_to_python(valor)
        )

    return resultado


# =========================================================
# CONVERTIR PYTHON -> FIRESTORE VALUE
# =========================================================

def python_to_firestore_value(value):

    if value is None:

        return {
            "nullValue": None
        }

    if isinstance(value, bool):

        return {
            "booleanValue": value
        }

    if isinstance(value, int):

        return {
            "integerValue": str(value)
        }

    if isinstance(value, float):

        return {
            "doubleValue": value
        }

    if isinstance(value, str):

        return {
            "stringValue": value
        }

    if isinstance(value, list):

        return {
            "arrayValue": {
                "values": [
                    python_to_firestore_value(v)
                    for v in value
                ]
            }
        }

    if isinstance(value, dict):

        return {
            "mapValue": {
                "fields": {
                    k: python_to_firestore_value(v)
                    for k, v in value.items()
                }
            }
        }

    return {
        "stringValue": str(value)
    }


# =========================================================
# CONVERTIR PYTHON DICT -> FIRESTORE FIELDS
# =========================================================

def python_to_firestore_fields(data):

    return {
        key: python_to_firestore_value(value)
        for key, value in data.items()
    }


# =========================================================
# OBTENER DOCUMENTO FIRESTORE
# =========================================================

def obtener_documento(
    coleccion,
    documento_id
):

    try:

        url = (
            firestore_base_url()
            + "/"
            + quote(
                coleccion,
                safe=""
            )
            + "/"
            + quote(
                documento_id,
                safe=""
            )
        )

        print(
            f"🔎 FIRESTORE GET: {coleccion}/{documento_id}"
        )

        respuesta = requests.get(
            url,
            headers=firestore_headers(),
            timeout=10
        )

        print("========================================")
        print("🔥 FIRESTORE DEBUG")
        print(f"Proyecto: {firebase_project_id}")
        print(f"Colección: {coleccion}")
        print(f"Documento: {documento_id}")
        print(f"URL: {url}")
        print(f"HTTP: {respuesta.status_code}")
        print(f"Respuesta: {respuesta.text[:2000]}")
        print("========================================")

        # -------------------------------------------------
        # NO EXISTE
        # -------------------------------------------------

        if respuesta.status_code == 404:

            print(
                f"⚠️ Documento no existe: "
                f"{coleccion}/{documento_id}"
            )

            return None


        # -------------------------------------------------
        # ERROR
        # -------------------------------------------------

        if not respuesta.ok:

            print(
                "❌ Firestore GET ERROR:"
            )

            print(
                respuesta.status_code
            )

            print(
                respuesta.text[:1000]
            )

            return None


        documento = respuesta.json()

        return firestore_fields_to_python(
            documento.get(
                "fields",
                {}
            )
        )


    except requests.Timeout:

        print(
            "❌ FIRESTORE TIMEOUT"
        )

        return None


    except Exception as e:

        print(
            f"❌ ERROR obteniendo documento: {e}"
        )

        return None


# =========================================================
# LISTAR COLECCIÓN FIRESTORE
# =========================================================

def obtener_coleccion(
    coleccion
):

    documentos = []

    try:

        url = (
            firestore_base_url()
            + "/"
            + quote(
                coleccion,
                safe=""
            )
        )

        page_token = None


        while True:

            params = {
                "pageSize": 100
            }

            if page_token:

                params["pageToken"] = page_token


            print(
                f"📦 FIRESTORE LIST: {coleccion}"
            )


            respuesta = requests.get(
                url,
                headers=firestore_headers(),
                params=params,
                timeout=15
            )


            if not respuesta.ok:

                print(
                    "❌ FIRESTORE LIST ERROR:"
                )

                print(
                    respuesta.status_code
                )

                print(
                    respuesta.text[:1000]
                )

                break


            datos = respuesta.json()


            for documento in datos.get(
                "documents",
                []
            ):

                nombre_documento = documento.get(
                    "name",
                    ""
                )

                documento_id = (
                    nombre_documento.split("/")[-1]
                )


                campos = (
                    firestore_fields_to_python(
                        documento.get(
                            "fields",
                            {}
                        )
                    )
                )


                campos["_id"] = documento_id

                documentos.append(
                    campos
                )


            page_token = datos.get(
                "nextPageToken"
            )


            if not page_token:
                break


        print(
            f"✅ Firestore devolvió "
            f"{len(documentos)} documentos de {coleccion}"
        )

        return documentos


    except requests.Timeout:

        print(
            f"❌ TIMEOUT cargando {coleccion}"
        )

        return []


    except Exception as e:

        print(
            f"❌ ERROR cargando {coleccion}: {e}"
        )

        return []


# =========================================================
# CREAR / ACTUALIZAR DOCUMENTO
# =========================================================

def guardar_documento(
    coleccion,
    documento_id,
    datos
):

    try:

        url = (
            firestore_base_url()
            + "/"
            + quote(
                coleccion,
                safe=""
            )
            + "/"
            + quote(
                documento_id,
                safe=""
            )
        )


        cuerpo = {
            "fields": python_to_firestore_fields(
                datos
            )
        }


        print(
            f"💾 FIRESTORE SAVE: "
            f"{coleccion}/{documento_id}"
        )


        respuesta = requests.patch(
            url,
            headers=firestore_headers(),
            json=cuerpo,
            timeout=10
        )


        if not respuesta.ok:

            print(
                "❌ FIRESTORE SAVE ERROR:"
            )

            print(
                respuesta.status_code
            )

            print(
                respuesta.text[:1000]
            )

            return False


        print(
            "✅ Documento guardado correctamente"
        )

        return True


    except requests.Timeout:

        print(
            "❌ TIMEOUT guardando documento"
        )

        return False


    except Exception as e:

        print(
            f"❌ ERROR guardando documento: {e}"
        )

        return False


# =========================================================
# CLIENTE LOGUEADO
# =========================================================

def obtener_cliente_logueado():

    nit_usuario = request.cookies.get(
        "cliente_nit"
    )


    if not nit_usuario:

        return None


    return obtener_documento(
        "clientes",
        nit_usuario
    )


# =========================================================
# PRODUCTOS
# =========================================================

def obtener_productos():

    lista = []


    documentos = obtener_coleccion(
        "productos"
    )


    for producto in documentos:

        try:

            precio = int(
                producto.get(
                    "precio",
                    0
                )
            )

        except:

            precio = 0


        try:

            existencias = int(
                producto.get(
                    "existencias",
                    0
                )
            )

        except:

            existencias = 0


        lista.append({

            "id": producto.get(
                "_id",
                ""
            ),

            "nombre": producto.get(
                "nombre",
                "Medicamento sin nombre"
            ),

            "precio": precio,

            'imagen': (
              producto.get("imagen", "/placeholder.jpg")
             .replace("/static/", "/")
             .replace("/public/", "/")
            ),
            

            "existencias": existencias

        })


    lista.sort(
        key=lambda x: str(
            x["nombre"]
        ).lower()
    )


    return lista


# =========================================================
# INICIO
# =========================================================

@app.route("/")
def inicio():

    cliente = obtener_cliente_logueado()


    # -----------------------------------------------------
    # NO HAY SESIÓN
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
box-sizing:border-box;
width:100%;
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

.links{
display:flex;
justify-content:space-between;
margin-top:25px;
}

.links a{
text-decoration:none;
font-size:0.85rem;
font-weight:600;
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
"
>
ALIANZAS PHARMA
</h2>

<p
style="
color:#64748b;
font-size:0.85rem;
margin-bottom:25px;
font-weight:bold;
"
>
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

<div class="links">

<a
href="/registro-cliente"
style="color:#3498db;"
>
Crear Cuenta
</a>

<a
href="/recuperar-clave"
style="color:#e67e22;"
>
Olvidé mi clave
</a>

</div>

</div>

</body>

</html>
"""


    # -----------------------------------------------------
    # USUARIO LOGUEADO
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


    print("========================================")
    print("🔐 INTENTO DE LOGIN")
    print(f"NIT recibido: {nit}")
    print("========================================")


    # -----------------------------------------------------
    # DATOS VACÍOS
    # -----------------------------------------------------

    if not nit or not password:

        return """
<html>
<head>
<title>Datos incompletos</title>
</head>

<body
style="
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
margin:0;
"
>

<div
style="
background:white;
padding:40px;
border-radius:16px;
text-align:center;
box-shadow:0 10px 25px rgba(0,0,0,0.05);
"
>

<h2>⚠️ Datos incompletos</h2>

<p>
Debes ingresar el NIT y la contraseña.
</p>

<a
href="/"
style="
background:#3498db;
color:white;
padding:10px 20px;
border-radius:20px;
text-decoration:none;
font-weight:bold;
display:inline-block;
margin-top:15px;
"
>
Intentar de Nuevo
</a>

</div>

</body>
</html>
"""


    # -----------------------------------------------------
    # FIREBASE NO DISPONIBLE
    # -----------------------------------------------------

    if not firebase_credentials:

        print(
            "❌ LOGIN: Firebase no está disponible."
        )

        return """
<html>
<head>
<title>Error de conexión</title>
</head>

<body
style="
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
margin:0;
"
>

<div
style="
background:white;
padding:40px;
border-radius:16px;
text-align:center;
box-shadow:0 10px 25px rgba(0,0,0,0.05);
"
>

<h2>❌ Error de conexión</h2>

<p>
No fue posible conectar con Firebase.
</p>

<a
href="/"
style="
background:#3498db;
color:white;
padding:10px 20px;
border-radius:20px;
text-decoration:none;
font-weight:bold;
display:inline-block;
margin-top:15px;
"
>
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
            f"🔎 Buscando clientes/{nit}"
        )


        datos_cliente = obtener_documento(
            "clientes",
            nit
        )


        # -------------------------------------------------
        # NIT NO EXISTE
        # -------------------------------------------------

        if not datos_cliente:

            print(
                f"❌ El NIT {nit} NO existe."
            )

            return """
<html>
<head>
<title>Datos incorrectos</title>
</head>

<body
style="
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
margin:0;
"
>

<div
style="
background:white;
padding:40px;
border-radius:16px;
text-align:center;
box-shadow:0 10px 25px rgba(0,0,0,0.05);
"
>

<h2>❌ NIT no registrado</h2>

<p>
El NIT no está registrado en Alianzas Pharma.
</p>

<a
href="/"
style="
background:#3498db;
color:white;
padding:10px 20px;
border-radius:20px;
text-decoration:none;
font-weight:bold;
display:inline-block;
margin-top:15px;
"
>
Intentar de Nuevo
</a>

</div>

</body>
</html>
"""


        # -------------------------------------------------
        # CONTRASEÑA
        # -------------------------------------------------

        pass_db = str(
            datos_cliente.get(
                "password",
                ""
            )
        ).strip()


        print(
            "✅ Cliente encontrado en Firebase"
        )


        if pass_db != password:

            print(
                f"❌ Contraseña incorrecta para {nit}"
            )

            return """
<html>
<head>
<title>Datos incorrectos</title>
</head>

<body
style="
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
margin:0;
"
>

<div
style="
background:white;
padding:40px;
border-radius:16px;
text-align:center;
box-shadow:0 10px 25px rgba(0,0,0,0.05);
"
>

<h2>❌ Contraseña Incorrecta</h2>

<p>
La contraseña no coincide con la registrada en Firebase.
</p>

<a
href="/"
style="
background:#3498db;
color:white;
padding:10px 20px;
border-radius:20px;
text-decoration:none;
font-weight:bold;
display:inline-block;
margin-top:15px;
"
>
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
            f"✅ LOGIN CORRECTO: {nit}"
        )


        lista_productos = obtener_productos()


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
            samesite="Lax"
        )


        return resp


    except Exception as e:

        print(
            "❌ ERROR FIREBASE LOGIN:"
        )

        print(
            str(e)
        )


        return """
<html>
<head>
<title>Error de Firebase</title>
</head>

<body
style="
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
margin:0;
"
>

<div
style="
background:white;
padding:40px;
border-radius:16px;
text-align:center;
box-shadow:0 10px 25px rgba(0,0,0,0.05);
"
>

<h2>❌ Error de conexión con Firebase</h2>

<p>
No fue posible consultar la base de datos.
</p>

<a
href="/"
style="
background:#3498db;
color:white;
padding:10px 20px;
border-radius:20px;
text-decoration:none;
font-weight:bold;
display:inline-block;
margin-top:15px;
"
>
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


        if not nit or not nombre or not password:

            return """
            <h2>Faltan datos</h2>
            <a href="/registro-cliente">
            Volver
            </a>
            """


        datos = {

            "nit": nit,

            "nombre": nombre,

            "password": password

        }


        guardado = guardar_documento(
            "clientes",
            nit,
            datos
        )


        if guardado:

            return redirect(
                url_for("inicio")
            )


        return """
        <h2>Error registrando cliente</h2>
        <a href="/registro-cliente">
        Intentar nuevamente
        </a>
        """


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


# =========================================================
# VERCEL / FLASK
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )
