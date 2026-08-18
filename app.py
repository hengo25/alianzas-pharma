# app.py — Alianzas Pharma


import os
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    make_response,
    send_from_directory,
    jsonify
)

from flask_cors import CORS

from google.oauth2 import service_account
from google.auth.transport.requests import Request


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)
CORS(app)

main = app


# =========================================================
# RUTAS DE ARCHIVOS / IMÁGENES
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PUBLIC_DIR = os.path.join(
    BASE_DIR,
    "public"
)


@app.route("/imagenes/<path:nombre>")
def servir_imagen(nombre):

    """
    Sirve imágenes almacenadas dentro de /public.

    Ejemplo:

    public/acetaminofen.jpg

    se puede solicitar como:

    /imagenes/acetaminofen.jpg
    """

    try:

        return send_from_directory(
            PUBLIC_DIR,
            nombre
        )

    except Exception as e:

        print(
            "❌ ERROR SIRVIENDO IMAGEN:",
            nombre
        )

        print(
            str(e)
        )

        return "", 404


@app.route("/static/<path:nombre>")
def servir_static(nombre):

    """
    También permite servir archivos desde public
    utilizando rutas antiguas tipo /static/...
    """

    try:

        return send_from_directory(
            PUBLIC_DIR,
            nombre
        )

    except Exception as e:

        print(
            "❌ ERROR SIRVIENDO STATIC:",
            nombre
        )

        print(
            str(e)
        )

        return "", 404


# =========================================================
# FIREBASE REST
# =========================================================

FIRESTORE_SCOPE = (
    "https://www.googleapis.com/auth/datastore"
)

firebase_credentials = None
firebase_project_id = None


print("==============================================")
print("🔐 CARGANDO CREDENCIALES FIREBASE")
print("==============================================")


firebase_credentials_env = os.getenv(
    "FIREBASE_CREDENTIALS"
)


if not firebase_credentials_env:

    raise ValueError(
        "La variable FIREBASE_CREDENTIALS "
        "no está configurada"
    )


try:

    datos_firebase = json.loads(
        firebase_credentials_env
    )

except json.JSONDecodeError as e:

    raise ValueError(
        "FIREBASE_CREDENTIALS no contiene "
        f"un JSON válido: {e}"
    )


print(
    "✅ FIREBASE_CREDENTIALS encontrada"
)

print(
    f"📁 Proyecto: "
    f"{datos_firebase.get('project_id')}"
)


# =========================================================
# CORREGIR PRIVATE KEY
# =========================================================

if "private_key" in datos_firebase:

    datos_firebase["private_key"] = (
        datos_firebase["private_key"]
        .replace("\\n", "\n")
    )


firebase_project_id = (
    datos_firebase.get("project_id")
)


if not firebase_project_id:

    raise ValueError(
        "La llave Firebase no contiene project_id"
    )


# =========================================================
# CREAR CREDENCIALES
# =========================================================

try:

    firebase_credentials = (
        service_account
        .Credentials
        .from_service_account_info(
            datos_firebase,
            scopes=[FIRESTORE_SCOPE]
        )
    )

    print("==============================================")
    print("✅ LLAVE FIREBASE CARGADA")
    print(
        f"📁 Proyecto: "
        f"{firebase_project_id}"
    )
    print("==============================================")


except Exception as e:

    firebase_credentials = None

    print("==============================================")
    print("❌ ERROR CARGANDO FIREBASE")
    print(str(e))
    print("==============================================")


# =========================================================
# OBTENER TOKEN FIREBASE
# =========================================================

def obtener_token_firebase():

    if not firebase_credentials:

        raise RuntimeError(
            "Las credenciales de Firebase "
            "no están disponibles."
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
# URL BASE FIRESTORE
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

        "Authorization":
            f"Bearer {token}",

        "Content-Type":
            "application/json"

    }


# =========================================================
# FIRESTORE VALUE -> PYTHON
# =========================================================

def firestore_value_to_python(value):

    if not isinstance(value, dict):

        return None


    if "stringValue" in value:

        return value["stringValue"]


    if "integerValue" in value:

        try:

            return int(
                value["integerValue"]
            )

        except:

            return 0


    if "doubleValue" in value:

        try:

            return float(
                value["doubleValue"]
            )

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

        values = (
            value["arrayValue"]
            .get("values", [])
        )

        return [

            firestore_value_to_python(v)

            for v in values

        ]


    if "mapValue" in value:

        fields = (
            value["mapValue"]
            .get("fields", {})
        )

        return firestore_fields_to_python(
            fields
        )


    return None


# =========================================================
# FIRESTORE FIELDS -> PYTHON
# =========================================================

def firestore_fields_to_python(fields):

    resultado = {}

    if not fields:

        return resultado


    for nombre, valor in fields.items():

        resultado[nombre] = (
            firestore_value_to_python(
                valor
            )
        )


    return resultado


# =========================================================
# PYTHON -> FIRESTORE VALUE
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

                    k:
                    python_to_firestore_value(v)

                    for k, v in value.items()

                }

            }

        }


    return {
        "stringValue": str(value)
    }


# =========================================================
# PYTHON DICT -> FIRESTORE FIELDS
# =========================================================

def python_to_firestore_fields(data):

    return {

        key:
        python_to_firestore_value(value)

        for key, value in data.items()

    }


# =========================================================
# OBTENER DOCUMENTO
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


        respuesta = requests.get(
            url,
            headers=firestore_headers(),
            timeout=10
        )


        if respuesta.status_code == 404:

            return None


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
# LISTAR COLECCIÓN
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

                nombre_documento = (
                    documento.get(
                        "name",
                        ""
                    )
                )


                documento_id = (
                    nombre_documento
                    .split("/")[-1]
                )


                campos = (
                    firestore_fields_to_python(
                        documento.get(
                            "fields",
                            {}
                        )
                    )
                )


                campos["_id"] = (
                    documento_id
                )


                documentos.append(
                    campos
                )


            page_token = (
                datos.get(
                    "nextPageToken"
                )
            )


            if not page_token:

                break


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
# GUARDAR DOCUMENTO
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

            "fields":
            python_to_firestore_fields(
                datos
            )

        }


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
# ELIMINAR DOCUMENTO FIRESTORE
# =========================================================

def eliminar_documento(
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


        respuesta = requests.delete(
            url,
            headers=firestore_headers(),
            timeout=10
        )


        if respuesta.status_code == 404:

            return False


        if not respuesta.ok:

            print(
                "❌ FIRESTORE DELETE ERROR:"
            )

            print(
                respuesta.status_code
            )

            print(
                respuesta.text[:1000]
            )

            return False


        return True


    except Exception as e:

        print(
            f"❌ ERROR eliminando documento: {e}"
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
# NORMALIZAR IMAGEN
# =========================================================

def normalizar_imagen(
    imagen
):

    if not imagen:

        imagen = "placeholder.jpg"


    imagen = str(
        imagen
    ).strip()


    # Si Firebase ya tiene una URL completa,
    # se conserva.

    if (
        imagen.startswith("http://")
        or
        imagen.startswith("https://")
    ):

        return imagen


    imagen = (
        imagen
        .replace("\\", "/")
    )


    # Quitar rutas antiguas.

    imagen = (
        imagen
        .replace("/static/", "")
        .replace("/public/", "")
        .replace("/imagenes/", "")
    )


    imagen = imagen.lstrip("/")


    # Mantener subcarpetas si existen.

    return (
        "/imagenes/"
        + quote(
            imagen,
            safe="/"
        )
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

        # -------------------------------------------------
        # PRECIO
        # -------------------------------------------------

        try:

            precio = int(
                producto.get(
                    "precio",
                    0
                )
            )

        except:

            precio = 0


        # -------------------------------------------------
        # EXISTENCIAS
        # -------------------------------------------------

        try:

            existencias = int(
                producto.get(
                    "existencias",
                    0
                )
            )

        except:

            existencias = 0


        # -------------------------------------------------
        # IMAGEN
        # -------------------------------------------------

        imagen = normalizar_imagen(
            producto.get(
                "imagen",
                "placeholder.jpg"
            )
        )


        # -------------------------------------------------
        # PRODUCTO
        # -------------------------------------------------

        lista.append({

            "id":
                producto.get(
                    "_id",
                    ""
                ),

            "nombre":
                producto.get(
                    "nombre",
                    "Medicamento sin nombre"
                ),

            "precio":
                precio,

            "imagen":
                imagen,

            "existencias":
                existencias

        })


    lista.sort(

        key=lambda x:
        str(
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


    if not nit or not password:

        return """
<html>
<body
style="
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
"
>

<div
style="
background:white;
padding:40px;
border-radius:16px;
text-align:center;
"
>

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


    if not firebase_credentials:

        return """
<html>
<body
style="
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
"
>

<div
style="
background:white;
padding:40px;
border-radius:16px;
text-align:center;
"
>

<h2>❌ Error de conexión</h2>

<p>
No fue posible conectar con Firebase.
</p>

<a href="/">
Intentar de Nuevo
</a>

</div>

</body>
</html>
"""


    try:

        datos_cliente = obtener_documento(
            "clientes",
            nit
        )


        if not datos_cliente:

            return """
<html>
<body
style="
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
"
>

<div
style="
background:white;
padding:40px;
border-radius:16px;
text-align:center;
"
>

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


        pass_db = str(
            datos_cliente.get(
                "password",
                ""
            )
        ).strip()


        if pass_db != password:

            return """
<html>
<body
style="
font-family:sans-serif;
background:#f4f6f9;
display:flex;
align-items:center;
justify-content:center;
height:100vh;
"
>

<div
style="
background:white;
padding:40px;
border-radius:16px;
text-align:center;
"
>

<h2>❌ Contraseña Incorrecta</h2>

<p>
La contraseña no coincide.
</p>

<a href="/">
Intentar de Nuevo
</a>

</div>

</body>
</html>
"""


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
            "❌ ERROR FIREBASE LOGIN:",
            str(e)
        )


        return """
<html>
<body>

<h2>❌ Error de conexión con Firebase</h2>

<a href="/">
Intentar de Nuevo
</a>

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

            "nit":
                nit,

            "nombre":
                nombre,

            "password":
                password

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
@app.route("/logout-cliente")
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
# MIS PEDIDOS
# =========================================================

@app.route("/mis_pedidos")
@app.route("/mis-pedidos")
def mis_pedidos():

    cliente = obtener_cliente_logueado()


    if not cliente:

        return redirect(
            url_for("inicio")
        )


    nit_cliente = str(
        cliente.get(
            "nit",
            request.cookies.get(
                "cliente_nit",
                ""
            )
        )
    ).strip()


    todos_los_pedidos = (
        obtener_coleccion(
            "pedidos"
        )
    )


    pedidos_cliente = []


    for pedido in todos_los_pedidos:

        datos_pedido_cliente = (
            pedido.get(
                "cliente",
                {}
            )
        )


        nit_pedido = str(
            datos_pedido_cliente.get(
                "nit",
                ""
            )
        ).strip()


        if nit_pedido == nit_cliente:

            pedidos_cliente.append(
                pedido
            )


    pedidos_cliente.sort(

        key=lambda x:
        str(
            x.get(
                "fecha",
                ""
            )
        ),

        reverse=True

    )


    tarjetas = ""


    for pedido in pedidos_cliente:

        pedido_id = pedido.get(
            "_id",
            "Sin número"
        )


        estado = str(
            pedido.get(
                "estado",
                "Pendiente"
            )
        )


        fecha = pedido.get(
            "fecha",
            ""
        )


        total = pedido.get(
            "total",
            0
        )


        articulos = pedido.get(
            "articulos",
            []
        )


        productos_html = ""


        for articulo in articulos:

            nombre = articulo.get(
                "nombre",
                articulo.get(
                    "producto",
                    "Producto"
                )
            )


            cantidad = articulo.get(
                "cantidad",
                0
            )


            precio = articulo.get(
                "precio",
                0
            )


            try:

                subtotal = (
                    int(precio)
                    *
                    int(cantidad)
                )

            except:

                subtotal = 0


            productos_html += f"""
                <div class="producto-pedido">

                    <div>

                        <strong>
                            {nombre}
                        </strong>

                        <br>

                        <span>
                            Cantidad: {cantidad}
                        </span>

                    </div>

                    <strong>
                        ${subtotal:,.0f}
                    </strong>

                </div>
            """


        # -------------------------------------------------
        # ESTADO VISUAL
        # -------------------------------------------------

        if estado == "Cancelado":

            estado_html = """
            <span class="estado cancelado">
                Cancelado
            </span>
            """

            accion_html = f"""
            <div class="pedido-cancelado">

                <div class="cancelado-titulo">
                    🚫 Este pedido fue cancelado.
                </div>

                <div class="cancelado-texto">
                    El pedido ya no será despachado
                    y los productos fueron devueltos
                    al inventario.
                </div>

            </div>

            <button
                class="btn-eliminar"
                onclick="eliminarPedido('{pedido_id}')"
            >
                🗑️ Eliminar pedido
            </button>
            """

        else:

            estado_html = """
            <span class="estado pendiente">
                Pendiente
            </span>
            """

            accion_html = f"""
            <button
                class="btn-cancelar"
                onclick="cancelarPedido('{pedido_id}')"
            >
                🚫 Cancelar pedido
            </button>
            """


        tarjetas += f"""
        <div class="pedido">

            <div class="pedido-header">

                <div>

                    <h2>
                        🧾 {pedido_id}
                    </h2>

                    <p>
                        Fecha: {fecha}
                    </p>

                </div>

                {estado_html}

            </div>


            <div class="productos">

                {productos_html}

            </div>


            <div class="pedido-total">

                <span>
                    Total del pedido
                </span>

                <strong>
                    ${int(total):,.0f}
                </strong>

            </div>


            {accion_html}

        </div>
        """


    if not tarjetas:

        tarjetas = """
        <div class="sin-pedidos">

            <div class="icono">
                📦
            </div>

            <h2>
                Todavía no tienes pedidos
            </h2>

            <p>
                Cuando realices tu primer pedido,
                aparecerá aquí.
            </p>

        </div>
        """


    return f"""
<!DOCTYPE html>

<html lang="es">

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width, initial-scale=1.0"
>

<title>
Mis Pedidos - Alianzas Pharma
</title>


<style>

* {{
    box-sizing: border-box;
}}


body {{

    font-family:
        'Segoe UI',
        Arial,
        sans-serif;

    background:
        #f4f6f9;

    margin: 0;

    padding: 30px;

    color: #2c3e50;

}}


.contenedor {{

    max-width: 1000px;

    margin: auto;

}}


.encabezado {{

    background: white;

    padding: 25px 30px;

    border-radius: 16px;

    box-shadow:
        0 10px 25px
        rgba(0,0,0,0.05);

    margin-bottom: 25px;

}}


.encabezado h1 {{

    margin: 0 0 8px 0;

    font-size: 28px;

}}


.encabezado p {{

    margin: 0;

    color: #64748b;

}}


.pedido {{

    background: white;

    border-radius: 16px;

    padding: 25px;

    margin-bottom: 20px;

    box-shadow:
        0 10px 25px
        rgba(0,0,0,0.05);

}}


.pedido-header {{

    display: flex;

    justify-content:
        space-between;

    align-items:
        center;

    gap: 20px;

    border-bottom:
        1px solid #e5e7eb;

    padding-bottom: 15px;

    margin-bottom: 15px;

}}


.pedido-header h2 {{

    margin: 0 0 5px 0;

    font-size: 20px;

}}


.pedido-header p {{

    margin: 0;

    color: #64748b;

    font-size: 14px;

}}


.estado {{

    padding: 8px 14px;

    border-radius: 20px;

    font-weight: bold;

    font-size: 14px;

}}


.estado.pendiente {{

    background:
        #fff3cd;

    color:
        #856404;

}}


.estado.cancelado {{

    background:
        #fee2e2;

    color:
        #b91c1c;

}}


.producto-pedido {{

    display: flex;

    justify-content:
        space-between;

    align-items:
        center;

    padding: 12px 0;

    border-bottom:
        1px solid #f1f5f9;

}}


.producto-pedido strong {{

    color: #2c3e50;

}}


.producto-pedido span {{

    color: #64748b;

    font-size: 14px;

}}


.pedido-total {{

    display: flex;

    justify-content:
        space-between;

    align-items:
        center;

    margin-top: 18px;

    padding-top: 15px;

    border-top:
        2px solid #e5e7eb;

    font-size: 18px;

}}


.pedido-total strong {{

    color: #16a34a;

    font-size: 22px;

}}


.pedido-cancelado {{

    margin-top: 20px;

    padding: 18px;

    border-radius: 10px;

    background:
        #fff1f2;

    border:
        1px solid #fecdd3;

}}


.cancelado-titulo {{

    color:
        #b91c1c;

    font-weight:
        bold;

    margin-bottom:
        8px;

}}


.cancelado-texto {{

    color:
        #dc2626;

    font-size:
        14px;

}}


.btn-cancelar,
.btn-eliminar {{

    border: none;

    border-radius: 9px;

    padding: 12px 18px;

    margin-top: 18px;

    font-weight: bold;

    cursor: pointer;

    font-size: 14px;

}}


.btn-cancelar {{

    background:
        #fee2e2;

    color:
        #b91c1c;

}}


.btn-cancelar:hover {{

    background:
        #fecaca;

}}


.btn-eliminar {{

    background:
        #64748b;

    color:
        white;

}}


.btn-eliminar:hover {{

    background:
        #475569;

}}


.sin-pedidos {{

    background: white;

    text-align: center;

    padding: 60px 30px;

    border-radius: 16px;

    box-shadow:
        0 10px 25px
        rgba(0,0,0,0.05);

}}


.icono {{

    font-size: 50px;

    margin-bottom: 15px;

}}


.sin-pedidos h2 {{

    margin-bottom: 8px;

}}


.sin-pedidos p {{

    color: #64748b;

}}


.volver {{

    display: inline-block;

    margin-top: 20px;

    background:
        #3498db;

    color: white;

    padding: 12px 22px;

    border-radius: 25px;

    text-decoration: none;

    font-weight: bold;

}}


.volver:hover {{

    background:
        #2980b9;

}}

</style>

</head>


<body>


<div class="contenedor">


    <div class="encabezado">

        <h1>
            📜 Mis Pedidos
        </h1>

        <p>

            Pedidos realizados por

            <strong>
                {cliente.get("nombre", "")}
            </strong>

            — NIT:

            <strong>
                {nit_cliente}
            </strong>

        </p>

    </div>


    {tarjetas}


    <a
        href="/"
        class="volver"
    >
        ← Volver al catálogo
    </a>


</div>


<script>

async function cancelarPedido(pedidoId) {{

    const confirmar = confirm(
        "¿Estás seguro de cancelar este pedido?\\n\\n"
        + "El pedido ya no será despachado y "
        + "los productos serán devueltos al inventario."
    );


    if (!confirmar) {{

        return;

    }}


    try {{

        const respuesta = await fetch(
            "/cancelar-pedido",
            {{

                method: "POST",

                headers: {{

                    "Content-Type":
                        "application/json"

                }},

                body: JSON.stringify({{

                    pedido_id:
                        pedidoId

                }})

            }}
        );


        const datos =
            await respuesta.json();


        if (datos.status === "ok") {{

            alert(
                datos.message
            );

            location.reload();

        }} else {{

            alert(
                datos.message
                ||
                "No fue posible cancelar el pedido."
            );

        }}

    }} catch (error) {{

        console.error(error);

        alert(
            "Ocurrió un error al cancelar el pedido."
        );

    }}

}}


async function eliminarPedido(pedidoId) {{

    const confirmar = confirm(
        "¿Quieres eliminar definitivamente este pedido de tu historial?\\n\\n"
        + "Esta acción no se puede deshacer."
    );


    if (!confirmar) {{

        return;

    }}


    try {{

        const respuesta = await fetch(
            "/eliminar-pedido",
            {{

                method: "POST",

                headers: {{

                    "Content-Type":
                        "application/json"

                }},

                body: JSON.stringify({{

                    pedido_id:
                        pedidoId

                }})

            }}
        );


        const datos =
            await respuesta.json();


        if (datos.status === "ok") {{

            alert(
                datos.message
            );

            location.reload();

        }} else {{

            alert(
                datos.message
                ||
                "No fue posible eliminar el pedido."
            );

        }}

    }} catch (error) {{

        console.error(error);

        alert(
            "Ocurrió un error al eliminar el pedido."
        );

    }}

}}

</script>


</body>

</html>
"""


# =========================================================
# CANCELAR PEDIDO
# =========================================================

@app.route(
    "/cancelar-pedido",
    methods=["POST"]
)
def cancelar_pedido():

    try:

        cliente = (
            obtener_cliente_logueado()
        )


        if not cliente:

            return jsonify({

                "status":
                    "error",

                "message":
                    "La sesión del cliente no es válida."

            }), 401


        datos = request.get_json(
            silent=True
        ) or {}


        pedido_id = str(
            datos.get(
                "pedido_id",
                ""
            )
        ).strip()


        if not pedido_id:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No se recibió el número del pedido."

            }), 400


        pedido = obtener_documento(
            "pedidos",
            pedido_id
        )


        if not pedido:

            return jsonify({

                "status":
                    "error",

                "message":
                    "El pedido no existe."

            }), 404


        # -------------------------------------------------
        # VERIFICAR CLIENTE
        # -------------------------------------------------

        datos_pedido_cliente = (
            pedido.get(
                "cliente",
                {}
            )
        )


        nit_cliente = str(
            cliente.get(
                "nit",
                request.cookies.get(
                    "cliente_nit",
                    ""
                )
            )
        ).strip()


        nit_pedido = str(
            datos_pedido_cliente.get(
                "nit",
                ""
            )
        ).strip()


        if nit_pedido != nit_cliente:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No tienes permiso para cancelar este pedido."

            }), 403


        # -------------------------------------------------
        # SOLO PENDIENTE
        # -------------------------------------------------

        estado_actual = str(
            pedido.get(
                "estado",
                "Pendiente"
            )
        ).strip()


        if estado_actual != "Pendiente":

            return jsonify({

                "status":
                    "error",

                "message":
                    "Este pedido ya no puede ser cancelado "
                    f"porque su estado es: {estado_actual}"

            }), 400


        articulos = pedido.get(
            "articulos",
            []
        )


        if not articulos:

            return jsonify({

                "status":
                    "error",

                "message":
                    "El pedido no contiene productos."

            }), 400


        # -------------------------------------------------
        # VALIDAR PRODUCTOS
        # -------------------------------------------------

        productos_a_restaurar = []


        for articulo in articulos:

            producto_id = str(
                articulo.get(
                    "id",
                    ""
                )
            ).strip()


            try:

                cantidad = int(
                    articulo.get(
                        "cantidad",
                        0
                    )
                )

            except:

                cantidad = 0


            if not producto_id or cantidad <= 0:

                return jsonify({

                    "status":
                        "error",

                    "message":
                        "El pedido contiene un producto "
                        "con datos inválidos."

                }), 400


            producto = obtener_documento(
                "productos",
                producto_id
            )


            if not producto:

                return jsonify({

                    "status":
                        "error",

                    "message":
                        "No se encontró el producto "
                        "para restaurar el inventario: "
                        + producto_id

                }), 500


            try:

                existencias_actuales = int(
                    producto.get(
                        "existencias",
                        0
                    )
                )

            except:

                existencias_actuales = 0


            productos_a_restaurar.append({

                "id":
                    producto_id,

                "producto":
                    producto,

                "cantidad":
                    cantidad,

                "existencias_antes":
                    existencias_actuales

            })


        # -------------------------------------------------
        # RESTAURAR INVENTARIO
        # -------------------------------------------------

        productos_actualizados = []


        for item in productos_a_restaurar:

            producto = item[
                "producto"
            ]


            nuevas_existencias = (
                item["existencias_antes"]
                +
                item["cantidad"]
            )


            producto["existencias"] = (
                nuevas_existencias
            )


            guardado = guardar_documento(
                "productos",
                item["id"],
                producto
            )


            if not guardado:

                # Revertir productos anteriores

                for anterior in productos_actualizados:

                    producto_anterior = (
                        anterior["producto"]
                    )


                    producto_anterior[
                        "existencias"
                    ] = anterior[
                        "existencias_antes"
                    ]


                    guardar_documento(
                        "productos",
                        anterior["id"],
                        producto_anterior
                    )


                return jsonify({

                    "status":
                        "error",

                    "message":
                        "No fue posible restaurar "
                        "todo el inventario. "
                        "El pedido permanece Pendiente."

                }), 500


            productos_actualizados.append({

                "id":
                    item["id"],

                "producto":
                    producto,

                "existencias_antes":
                    item["existencias_antes"]

            })


        # -------------------------------------------------
        # CANCELAR PEDIDO
        # -------------------------------------------------

        pedido["estado"] = "Cancelado"


        guardado_pedido = guardar_documento(
            "pedidos",
            pedido_id,
            pedido
        )


        if not guardado_pedido:

            # Revertir inventario

            for anterior in productos_actualizados:

                producto_anterior = (
                    anterior["producto"]
                )


                producto_anterior[
                    "existencias"
                ] = anterior[
                    "existencias_antes"
                ]


                guardar_documento(
                    "productos",
                    anterior["id"],
                    producto_anterior
                )


            return jsonify({

                "status":
                    "error",

                "message":
                    "No fue posible cancelar "
                    "el pedido. No se realizaron "
                    "cambios definitivos."

            }), 500


        print(
            "========================================"
        )

        print(
            "🚫 PEDIDO CANCELADO"
        )

        print(
            f"🧾 Pedido: {pedido_id}"
        )

        print(
            f"👤 Cliente: {nit_cliente}"
        )

        print(
            "📦 Inventario restaurado"
        )

        print(
            "========================================"
        )


        return jsonify({

            "status":
                "ok",

            "message":
                "Pedido cancelado correctamente. "
                "El pedido ya no será despachado "
                "y el inventario fue restaurado.",

            "pedido_id":
                pedido_id

        })


    except Exception as e:

        print(
            "❌ ERROR CANCELANDO PEDIDO:",
            str(e)
        )


        return jsonify({

            "status":
                "error",

            "message":
                "Error cancelando el pedido: "
                + str(e)

        }), 500


# =========================================================
# ELIMINAR PEDIDO CANCELADO
# =========================================================

@app.route(
    "/eliminar-pedido",
    methods=["POST"]
)
def eliminar_pedido():

    try:

        cliente = (
            obtener_cliente_logueado()
        )


        if not cliente:

            return jsonify({

                "status":
                    "error",

                "message":
                    "La sesión del cliente no es válida."

            }), 401


        datos = request.get_json(
            silent=True
        ) or {}


        pedido_id = str(
            datos.get(
                "pedido_id",
                ""
            )
        ).strip()


        if not pedido_id:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No se recibió el número del pedido."

            }), 400


        pedido = obtener_documento(
            "pedidos",
            pedido_id
        )


        if not pedido:

            return jsonify({

                "status":
                    "error",

                "message":
                    "El pedido no existe."

            }), 404


        # -------------------------------------------------
        # VERIFICAR CLIENTE
        # -------------------------------------------------

        datos_cliente_pedido = (
            pedido.get(
                "cliente",
                {}
            )
        )


        nit_cliente = str(
            cliente.get(
                "nit",
                request.cookies.get(
                    "cliente_nit",
                    ""
                )
            )
        ).strip()


        nit_pedido = str(
            datos_cliente_pedido.get(
                "nit",
                ""
            )
        ).strip()


        if nit_pedido != nit_cliente:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No tienes permiso para eliminar este pedido."

            }), 403


        # -------------------------------------------------
        # SOLO PERMITIR ELIMINAR CANCELADOS
        # -------------------------------------------------

        estado = str(
            pedido.get(
                "estado",
                ""
            )
        ).strip()


        if estado != "Cancelado":

            return jsonify({

                "status":
                    "error",

                "message":
                    "Solo puedes eliminar pedidos que estén cancelados."

            }), 400


        # -------------------------------------------------
        # ELIMINAR
        # -------------------------------------------------

        eliminado = eliminar_documento(
            "pedidos",
            pedido_id
        )


        if not eliminado:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No fue posible eliminar el pedido."

            }), 500


        print(
            "========================================"
        )

        print(
            "🗑️ PEDIDO ELIMINADO"
        )

        print(
            f"🧾 Pedido: {pedido_id}"
        )

        print(
            f"👤 Cliente: {nit_cliente}"
        )

        print(
            "========================================"
        )


        return jsonify({

            "status":
                "ok",

            "message":
                "El pedido fue eliminado de tu historial.",

            "pedido_id":
                pedido_id

        })


    except Exception as e:

        print(
            "❌ ERROR ELIMINANDO PEDIDO:",
            str(e)
        )


        return jsonify({

            "status":
                "error",

            "message":
                "Error eliminando el pedido: "
                + str(e)

        }), 500


# =========================================================
# HACER PEDIDO
# =========================================================

@app.route(
    "/hacer-pedido",
    methods=["POST"]
)
def hacer_pedido():

    try:

        # -------------------------------------------------
        # CLIENTE
        # -------------------------------------------------

        cliente = (
            obtener_cliente_logueado()
        )


        if not cliente:

            return jsonify({

                "status":
                    "error",

                "message":
                    "La sesión del cliente no es válida."

            }), 401


        # -------------------------------------------------
        # DATOS DEL CARRITO
        # -------------------------------------------------

        datos = request.get_json(
            silent=True
        ) or {}


        articulos = datos.get(
            "articulos",
            []
        )


        if not articulos:

            return jsonify({

                "status":
                    "error",

                "message":
                    "El carrito está vacío."

            }), 400


        # -------------------------------------------------
        # VALIDAR PRODUCTOS
        # -------------------------------------------------

        productos_validos = []

        articulos_guardar = []

        total = 0


        for articulo in articulos:

            producto_id = str(
                articulo.get(
                    "id",
                    ""
                )
            ).strip()


            try:

                cantidad = int(
                    articulo.get(
                        "cantidad",
                        0
                    )
                )

            except:

                cantidad = 0


            if not producto_id or cantidad <= 0:

                return jsonify({

                    "status":
                        "error",

                    "message":
                        "Producto o cantidad inválida."

                }), 400


            producto = obtener_documento(
                "productos",
                producto_id
            )


            if not producto:

                return jsonify({

                    "status":
                        "error",

                    "message":
                        "El producto no existe: "
                        + str(
                            articulo.get(
                                "nombre",
                                producto_id
                            )
                        )

                }), 400


            try:

                existencias = int(
                    producto.get(
                        "existencias",
                        0
                    )
                )

            except:

                existencias = 0


            if existencias < cantidad:

                return jsonify({

                    "status":
                        "error",

                    "message":
                        "Inventario insuficiente para: "
                        + str(
                            producto.get(
                                "nombre",
                                "Producto"
                            )
                        )

                }), 400


            # -------------------------------------------------
            # USAR PRECIO DE FIREBASE
            # -------------------------------------------------

            try:

                precio = int(
                    producto.get(
                        "precio",
                        0
                    )
                )

            except:

                precio = 0


            subtotal = (
                precio
                *
                cantidad
            )


            total += subtotal


            productos_validos.append({

                "id":
                    producto_id,

                "producto":
                    producto,

                "cantidad":
                    cantidad

            })


            # Guardamos un artículo limpio.
            # Esto garantiza que el ID quede dentro
            # del pedido para poder restaurar inventario.

            articulos_guardar.append({

                "id":
                    producto_id,

                "nombre":
                    producto.get(
                        "nombre",
                        "Producto"
                    ),

                "cantidad":
                    cantidad,

                "precio":
                    precio

            })


        # -------------------------------------------------
        # DESCONTAR INVENTARIO
        # -------------------------------------------------

        productos_descontados = []


        for item in productos_validos:

            producto_id = item[
                "id"
            ]


            producto = item[
                "producto"
            ]


            cantidad = item[
                "cantidad"
            ]


            existencias_antes = int(
                producto.get(
                    "existencias",
                    0
                )
            )


            producto[
                "existencias"
            ] = (
                existencias_antes
                -
                cantidad
            )


            guardado = guardar_documento(
                "productos",
                producto_id,
                producto
            )


            if not guardado:

                # Revertir los productos ya descontados.

                for anterior in productos_descontados:

                    producto_anterior = (
                        anterior["producto"]
                    )


                    producto_anterior[
                        "existencias"
                    ] = anterior[
                        "existencias_antes"
                    ]


                    guardar_documento(
                        "productos",
                        anterior["id"],
                        producto_anterior
                    )


                return jsonify({

                    "status":
                        "error",

                    "message":
                        "No fue posible actualizar "
                        "el inventario."

                }), 500


            productos_descontados.append({

                "id":
                    producto_id,

                "producto":
                    producto,

                "existencias_antes":
                    existencias_antes

            })


        # -------------------------------------------------
        # DATOS DEL CLIENTE
        # -------------------------------------------------

        datos_cliente = {

            "nombre":
                cliente.get(
                    "nombre",
                    ""
                ),

            "nit":
                cliente.get(
                    "nit",
                    request.cookies.get(
                        "cliente_nit",
                        ""
                    )
                ),

            "telefono":
                cliente.get(
                    "telefono",
                    ""
                ),

            "direccion":
                cliente.get(
                    "direccion",
                    ""
                )

        }


        # -------------------------------------------------
        # ID PEDIDO
        # -------------------------------------------------

        pedido_id = (
            "PED-"
            +
            uuid.uuid4()
            .hex[:12]
            .upper()
        )


        # -------------------------------------------------
        # PEDIDO
        # -------------------------------------------------

        pedido = {

            "cliente":
                datos_cliente,

            "articulos":
                articulos_guardar,

            "total":
                total,

            "estado":
                "Pendiente",

            "fecha":
                datetime.now(
                    timezone.utc
                ).isoformat()

        }


        # -------------------------------------------------
        # GUARDAR PEDIDO
        # -------------------------------------------------

        guardado = guardar_documento(
            "pedidos",
            pedido_id,
            pedido
        )


        if not guardado:

            # Si el pedido NO se pudo guardar,
            # devolvemos el inventario.

            for anterior in productos_descontados:

                producto_anterior = (
                    anterior["producto"]
                )


                producto_anterior[
                    "existencias"
                ] = anterior[
                    "existencias_antes"
                ]


                guardar_documento(
                    "productos",
                    anterior["id"],
                    producto_anterior
                )


            return jsonify({

                "status":
                    "error",

                "message":
                    "No fue posible guardar "
                    "el pedido. El inventario "
                    "fue restaurado."

            }), 500


        print(
            "========================================"
        )

        print(
            "✅ PEDIDO GUARDADO CORRECTAMENTE"
        )

        print(
            f"🧾 Pedido: {pedido_id}"
        )

        print(
            f"👤 Cliente: "
            f"{datos_cliente.get('nombre')}"
        )

        print(
            f"💰 Total: ${total}"
        )

        print(
            "📦 Inventario actualizado"
        )

        print(
            "========================================"
        )


        return jsonify({

            "status":
                "ok",

            "message":
                "Pedido guardado correctamente.",

            "pedido_id":
                pedido_id,

            "total":
                total

        })


    except Exception as e:

        print(
            "========================================"
        )

        print(
            "❌ ERROR HACIENDO PEDIDO"
        )

        print(
            str(e)
        )

        print(
            "========================================"
        )


        return jsonify({

            "status":
                "error",

            "message":
                "Error procesando el pedido: "
                + str(e)

        }), 500


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

