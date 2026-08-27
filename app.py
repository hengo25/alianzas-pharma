import os
import json
import uuid
import hashlib
import hmac
import zipfile
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, unquote
from io import BytesIO
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import requests
from concurrent.futures import ThreadPoolExecutor
from werkzeug.security import generate_password_hash, check_password_hash

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    make_response,
    send_from_directory,
    send_file,
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
# DIRECTORIO BASE
# =========================================================

base_dir = os.path.dirname(
    os.path.abspath(__file__)
)
APP_MODE = os.getenv(
    "APP_MODE",
    "cliente"
).strip().lower()

# =========================================================
# SERVIR IMÁGENES DESDE PUBLIC
# =========================================================
@app.route("/manifest.json")
def servir_manifest():

    manifest = {
        "name": "Alianzas Pharma",
        "short_name": "Alianzas Pharma",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#3498db",
        "icons": [
            {
                "src": "/public/icon-cliente-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/public/icon-cliente-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }

    respuesta = make_response(
        json.dumps(
            manifest,
            ensure_ascii=False
        )
    )

    respuesta.headers[
        "Content-Type"
    ] = "application/manifest+json"

    return respuesta


@app.route("/manifest-admin.json")
def servir_manifest_admin():

    manifest = {
        "id": "/admin-login",
        "name": "Alianzas Pharma Admin",
        "short_name": "AP Admin",
        "start_url": "/admin-login",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#3498db",
        "icons": [
            {
                "src": "/public/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/public/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }

    respuesta = make_response(
        json.dumps(
            manifest,
            ensure_ascii=False
        )
    )

    respuesta.headers[
        "Content-Type"
    ] = "application/manifest+json"

    return respuesta



@app.route("/imagenes/<path:nombre>")
def servir_imagen(nombre):

    """
    Esta ruta se mantiene solamente como compatibilidad
    con imágenes antiguas que todavía puedan estar
    usando /imagenes/...

    Las nuevas URLs de productos usarán directamente
    los archivos de public/.
    """

    carpeta_public = os.path.join(
        base_dir,
        "public"
    )

    print(
        "========================================"
    )

    print(
        "🖼️ SOLICITUD DE IMAGEN COMPATIBILIDAD"
    )

    print(
        f"Archivo: {nombre}"
    )

    print(
        f"Carpeta: {carpeta_public}"
    )

    print(
        "========================================"
    )

    try:

        return send_from_directory(
            carpeta_public,
            nombre
        )

    except Exception as e:

        print(
            "❌ ERROR SIRVIENDO IMAGEN:"
        )

        print(
            str(e)
        )

        return (
            "Imagen no encontrada",
            404
        )

# =========================================================
# CONFIGURACIÓN FIREBASE REST
# =========================================================

FIRESTORE_SCOPE = (
    "https://www.googleapis.com/auth/datastore"
)

firebase_credentials = None

firebase_project_id = None


# =========================================================
# CARGAR LLAVE FIREBASE
# =========================================================

print(
    "=============================================="
)

print(
    "🔐 CARGANDO CREDENCIALES FIREBASE"
)

print(
    "=============================================="
)


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

    print(
        "=============================================="
    )

    print(
        "✅ LLAVE FIREBASE CARGADA"
    )

    print(
        f"📁 Proyecto: {firebase_project_id}"
    )

    print(
        "=============================================="
    )

except Exception as e:

    firebase_credentials = None

    print(
        "=============================================="
    )

    print(
        "❌ ERROR CARGANDO FIREBASE"
    )

    print(
        str(e)
    )

    print(
        "=============================================="
    )


# =========================================================
# OBTENER TOKEN GOOGLE
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

        values = value[
            "arrayValue"
        ].get(
            "values",
            []
        )


        return [
            firestore_value_to_python(v)
            for v in values
        ]


    if "mapValue" in value:

        fields = value[
            "mapValue"
        ].get(
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
            firestore_value_to_python(
                valor
            )
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
            f"🔎 FIRESTORE GET: "
            f"{coleccion}/{documento_id}"
        )


        respuesta = requests.get(
            url,
            headers=firestore_headers(),
            timeout=10
        )


        print(
            "========================================"
        )

        print(
            "🔥 FIRESTORE DEBUG"
        )

        print(
            f"Proyecto: {firebase_project_id}"
        )

        print(
            f"Colección: {coleccion}"
        )

        print(
            f"Documento: {documento_id}"
        )

        print(
            f"HTTP: {respuesta.status_code}"
        )

        print(
            f"Respuesta: "
            f"{respuesta.text[:2000]}"
        )

        print(
            "========================================"
        )


        if respuesta.status_code == 404:

            print(
                f"⚠️ Documento no existe: "
                f"{coleccion}/{documento_id}"
            )

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

                params[
                    "pageToken"
                ] = page_token


            print(
                f"📦 FIRESTORE LIST: "
                f"{coleccion}"
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
            f"{len(documentos)} documentos "
            f"de {coleccion}"
        )


        return documentos


    except requests.Timeout:

        print(
            f"❌ TIMEOUT cargando {coleccion}"
        )

        return []


    except Exception as e:

        print(
            f"❌ ERROR cargando "
            f"{coleccion}: {e}"
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
            "fields":
                python_to_firestore_fields(
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
            "✅ Documento guardado "
            "correctamente"
        )


        return True


    except requests.Timeout:

        print(
            "❌ TIMEOUT guardando documento"
        )

        return False


    except Exception as e:

        print(
            f"❌ ERROR guardando "
            f"documento: {e}"
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

        imagen_original = str(
            producto.get(
                "imagen",
                "placeholder.jpg"
            )
        ).strip()

        # Normalizar barras
        imagen_original = (
            imagen_original
            .replace("\\", "/")
        )

        # Quitar rutas antiguas
        imagen_original = (
            imagen_original
            .replace("/static/", "")
            .replace("static/", "")
            .replace("/public/", "")
            .replace("public/", "")
            .lstrip("/")
        )

        # -------------------------------------------------
        # RUTA CORRECTA
        # -------------------------------------------------

        imagen = (
          "/public/"
          + quote(
               imagen_original,
                safe="/"
           )
       )

       
        # -------------------------------------------------
        # AGREGAR PRODUCTO
        # -------------------------------------------------

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

            "imagen": imagen,

            "existencias": existencias
        })

    # -----------------------------------------------------
    # ORDENAR
    # -----------------------------------------------------

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

    if APP_MODE == "admin":

        return redirect(
        url_for("admin_login")
    )

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

<title>
Ingreso - Alianzas Pharma
</title>

<link
    rel="icon"
    type="image/png"
    sizes="192x192"
    href="/public/icon-cliente-192.png?v=2"
>

<link
    rel="shortcut icon"
    type="image/png"
    href="/public/icon-cliente-192.png?v=2"
>



<link
    rel="apple-touch-icon"
    sizes="180x180"
    href="/public/apple-touch-icon.png"
>

<style>

body{

font-family:
'Segoe UI',
sans-serif;

background:
#f4f6f9;

display:
flex;

align-items:
center;

justify-content:
center;

height:
100vh;

margin:
0;

}

.box{

background:
white;

padding:
40px 30px;

border-radius:
16px;

box-shadow:
0 10px 25px
rgba(0,0,0,0.05);

text-align:
center;

width:
320px;

}

input{

box-sizing:
border-box;

width:
100%;

padding:
12px;

margin-bottom:
12px;

border:
1px solid #cbd5e1;

border-radius:
8px;

outline:
none;

font-size:
1rem;

}

.btn{

background:
#3498db;

color:
white;

border:
none;

padding:
12px;

border-radius:
25px;

font-weight:
bold;

cursor:
pointer;

width:
100%;

font-size:
1rem;

margin-top:
10px;

box-shadow:
0 4px 12px
rgba(52,152,219,0.2);

}

.btn:hover{

background:
#2980b9;

}

.links{

display:
flex;

justify-content:
space-between;

margin-top:
25px;

}

.links a{

text-decoration:
none;

font-size:
0.85rem;

font-weight:
600;

}

</style>

</head>

<body>

<div class="box">

<div
    style="
        text-align:center;
        margin-bottom:18px;
    "
>
    <img
        src="/public/logo.jpeg"
        alt="Alianzas Pharma"
        style="
            max-width:90px;
            max-height:90px;
            object-fit:contain;
        "
    >
</div>


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

<div style="position:relative;">

    <input
        type="password"
        id="password_cliente"
        name="password"
        placeholder="Contraseña secreta"
        required
        style="padding-right:48px;"
    >

    <button
        type="button"
        onclick="mostrarClaveCliente()"
        id="ojo_password_cliente"
        style="
            position:absolute;
            right:12px;
            top:50%;
            transform:translateY(-50%);
            border:none;
            background:transparent;
            cursor:pointer;
            font-size:20px;
            padding:0;
        "
        title="Mostrar contraseña"
    >
        👁️
    </button>

</div>

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

<script>

    function mostrarClaveCliente() {

        const campo =
            document.getElementById(
                "password_cliente"
            );

        const boton =
            document.getElementById(
                "ojo_password_cliente"
            );

        if (campo.type === "password") {

            campo.type = "text";
            boton.innerText = "🙈";
            boton.title = "Ocultar contraseña";

        } else {

            campo.type = "password";
            boton.innerText = "👁️";
            boton.title = "Mostrar contraseña";

        }

    }

</script>


</body>

</html>
"""


    # -----------------------------------------------------
    # USUARIO LOGUEADO
    # -----------------------------------------------------

    lista = obtener_productos()


    # -----------------------------------------------------
    # BANNER PRINCIPAL
    # -----------------------------------------------------

    banner = obtener_documento(
        "configuracion",
        "banner_principal"
    )


    # Si todavía no existe en Firebase,
    # usar contenido predeterminado.

    if not banner:

        banner = {

            "activo":
                True,

            "etiqueta":
                "✨ Novedades Alianzas Pharma",

            "titulo":
                "Promoción especial para nuestros afiliados",

            "mensaje":
                "Aprovecha nuestras novedades, productos destacados y promociones disponibles para tu droguería.",

            "imagen":
                "/public/logo.jpeg",

            "boton_texto":
                "Ver promoción →",

            "boton_link":
                ""

        }


    # -----------------------------------------------------
    # LISTA DE PROMOCIONES PARA EL CARRUSEL
    # -----------------------------------------------------

    banners = obtener_coleccion(
        "banners"
    )

    banners_activos = []


    # -----------------------------------------------------
    # FECHA ACTUAL DE COLOMBIA
    # -----------------------------------------------------

    zona_colombia = timezone(
        timedelta(
            hours=-5
        )
    )


    hoy_colombia = datetime.now(
        zona_colombia
    ).date()


    # -----------------------------------------------------
    # VERIFICAR SI UNA PROMOCIÓN ESTÁ VIGENTE
    # -----------------------------------------------------

    def promocion_esta_vigente(item):

        # -------------------------------------------------
        # DEBE ESTAR ACTIVADA
        # -------------------------------------------------

        if not item.get(
            "activo",
            False
        ):

            return False


        fecha_inicio = str(
            item.get(
                "fecha_inicio",
                ""
            )
        ).strip()


        fecha_fin = str(
            item.get(
                "fecha_fin",
                ""
            )
        ).strip()


        # -------------------------------------------------
        # CONVERTIR FECHA
        # ACEPTA:
        # 2026-08-24
        # 24/08/2026
        # -------------------------------------------------

        def convertir_fecha(valor):

            if not valor:

                return None


            formatos = [
                "%Y-%m-%d",
                "%d/%m/%Y"
            ]


            for formato in formatos:

                try:

                    return datetime.strptime(
                        valor,
                        formato
                    ).date()

                except ValueError:

                    continue


            return None


        # -------------------------------------------------
        # VALIDAR FECHA DE INICIO
        # -------------------------------------------------

        if fecha_inicio:

            inicio = convertir_fecha(
                fecha_inicio
            )


            if not inicio:

                return False


            if hoy_colombia < inicio:

                return False


        # -------------------------------------------------
        # VALIDAR FECHA FINAL
        # -------------------------------------------------

        if fecha_fin:

            fin = convertir_fecha(
                fecha_fin
            )


            if not fin:

                return False


            if hoy_colombia > fin:

                return False


        return True


    # -----------------------------------------------------
    # PROMOCIONES ACTIVAS Y DENTRO DE SU FECHA
    # -----------------------------------------------------

    for item in banners:

        if promocion_esta_vigente(
            item
        ):

            banners_activos.append(
                item
            )

    # -----------------------------------------------------
    # ORDENAR PROMOCIONES
    # -----------------------------------------------------

    banners_activos.sort(
        key=lambda item: int(
            item.get(
                "orden",
                99
            )
        )
    )


    # -----------------------------------------------------
    # MÁXIMO 3 PROMOCIONES
    # -----------------------------------------------------

    banners_activos = banners_activos[:3]


        # -----------------------------------------------------
    # COMPATIBILIDAD CON EL BANNER ANTIGUO
    # -----------------------------------------------------
    # Solo usar el banner antiguo si TODAVÍA NO EXISTE
    # ninguna promoción en la colección "banners".
    # Si ya existen promociones pero están desactivadas,
    # deben permanecer ocultas.
    # -----------------------------------------------------

    if not banners:

        if promocion_esta_vigente(
            banner
        ):

            banners_activos = [
                banner
            ]

    # -----------------------------------------------------
    # SECCIÓN INSTITUCIONAL - CONOCE ALIANZAS PHARMA
    # -----------------------------------------------------

    institucional = obtener_documento(
        "configuracion",
        "institucional"
    )


    if not institucional:

        institucional = {

            "activo":
                False,

            "titulo":
                "Conoce Alianzas Pharma",

            "subtitulo":
                "Más que un proveedor, un aliado para tu droguería",

            "texto":
                "Trabajamos para brindar atención personalizada, productos de calidad y soluciones para nuestras droguerías afiliadas.",

            "foto_1": "",
            "foto_2": "",
            "foto_3": "",
            "foto_4": "",
            "beneficio_1": "Atención personalizada",
            "beneficio_2": "Productos de calidad"

        }



    return render_template(
        "index.html",
        productos=lista,
        cliente=cliente,
        banner=banner,
        banners=banners_activos,
        institucional=institucional
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


    print(
        "========================================"
    )

    print(
        "🔐 INTENTO DE LOGIN"
    )

    print(
        f"NIT recibido: {nit}"
    )

    print(
        "========================================"
    )


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


    try:

        print(
            f"🔎 Buscando clientes/{nit}"
        )


        datos_cliente = obtener_documento(
            "clientes",
            nit
        )


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


        pass_db = str(
            datos_cliente.get(
                "password",
                ""
            )
        ).strip()


        password_hash_db = str(
            datos_cliente.get(
                "password_hash",
                ""
            )
        ).strip()


        print(
            "✅ Cliente encontrado en Firebase"
        )


        password_correcta = False


        # ---------------------------------------------
        # CLIENTE YA MIGRADO A HASH
        # ---------------------------------------------

        if password_hash_db:

            try:

                password_correcta = check_password_hash(
                    password_hash_db,
                    password
                )

            except Exception as e:

                print(
                    "❌ Error verificando hash:",
                    str(e)
                )

                password_correcta = False


        # ---------------------------------------------
        # CLIENTE ANTIGUO - CONTRASEÑA EN TEXTO PLANO
        # ---------------------------------------------

        else:

            password_correcta = hmac.compare_digest(
                pass_db,
                password
            )


            # Si la contraseña antigua es correcta,
            # migrarla automáticamente a hash
            if password_correcta:

                try:

                    nuevo_hash = generate_password_hash(
                        password
                    )


                    datos_cliente[
                        "password_hash"
                    ] = nuevo_hash


                    datos_cliente.pop(
                        "password",
                        None
                    )


                    migrado = guardar_documento(
                        "clientes",
                        nit,
                        datos_cliente
                    )


                    if migrado:

                        print(
                            f"🔐 CONTRASEÑA MIGRADA A HASH: {nit}"
                        )

                    else:

                        print(
                            f"⚠️ No se pudo guardar la migración de contraseña: {nit}"
                        )


                except Exception as e:

                    print(
                        "⚠️ Error migrando contraseña:",
                        str(e)
                    )


        if not password_correcta:

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


        print(
            f"✅ LOGIN CORRECTO: {nit}"
        )

        resp = make_response(
            redirect(
                url_for("inicio")
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
# RECUPERAR CONTRASEÑA
# =========================================================

@app.route(
    "/recuperar-clave",
    methods=["GET", "POST"]
)
def recuperar_clave():

    # -----------------------------------------------------
    # MOSTRAR FORMULARIO
    # -----------------------------------------------------

    if request.method == "GET":

        return render_template(
            "recuperar_clave.html"
        )


    # -----------------------------------------------------
    # RECIBIR DATOS
    # -----------------------------------------------------

    nit = request.form.get(
        "nit",
        ""
    ).strip()


    telefono = request.form.get(
        "telefono",
        ""
    ).strip()


    nueva_password = request.form.get(
        "nueva_password",
        ""
    ).strip()


    confirmar_password = request.form.get(
        "confirmar_password",
        ""
    ).strip()


    # -----------------------------------------------------
    # VALIDAR CAMPOS
    # -----------------------------------------------------

    if (
        not nit
        or not telefono
        or not nueva_password
        or not confirmar_password
    ):

        return render_template(
            "recuperar_clave.html",
            error="Debes completar todos los campos."
        )


    # -----------------------------------------------------
    # VALIDAR CONTRASEÑAS
    # -----------------------------------------------------

    if nueva_password != confirmar_password:

        return render_template(
            "recuperar_clave.html",
            error="Las contraseñas no coinciden."
        )


    if len(nueva_password) < 6:

        return render_template(
            "recuperar_clave.html",
            error="La nueva contraseña debe tener mínimo 6 caracteres."
        )


    # -----------------------------------------------------
    # BUSCAR DROGUERÍA
    # -----------------------------------------------------

    cliente = obtener_documento(
        "clientes",
        nit
    )


    if not cliente:

        return render_template(
            "recuperar_clave.html",
            error="Los datos ingresados no coinciden con nuestros registros."
        )


    # -----------------------------------------------------
    # NORMALIZAR TELÉFONOS
    # -----------------------------------------------------

    telefono_ingresado = "".join(
        caracter
        for caracter in telefono
        if caracter.isdigit()
    )


    telefono_guardado = "".join(
        caracter
        for caracter in str(
            cliente.get(
                "telefono",
                ""
            )
        )
        if caracter.isdigit()
    )


    # -----------------------------------------------------
    # VERIFICAR TELÉFONO
    # -----------------------------------------------------

    if (
        not telefono_guardado
        or telefono_ingresado != telefono_guardado
    ):

        return render_template(
            "recuperar_clave.html",
            error="Los datos ingresados no coinciden con nuestros registros."
        )


    # -----------------------------------------------------
    # CAMBIAR CONTRASEÑA
    # -----------------------------------------------------

    cliente[
         "password_hash"
     ] = generate_password_hash(
            nueva_password
    )

    cliente.pop(
            "password",
            None
        )

    guardado = guardar_documento(
        "clientes",
        nit,
        cliente
    )


    if not guardado:

        return render_template(
            "recuperar_clave.html",
            error="No fue posible actualizar la contraseña. Intenta nuevamente."
        )


    # -----------------------------------------------------
    # ÉXITO
    # -----------------------------------------------------

    return render_template(
        "recuperar_clave.html",
        exito="Contraseña actualizada correctamente. Ya puedes iniciar sesión."
    )

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


        direccion = request.form.get(
            "direccion",
            ""
        ).strip()


        telefono = request.form.get(
            "telefono",
            ""
        ).strip()


        password = request.form.get(
            "password",
            ""
        ).strip()
        


        if (
            not nit
            or not nombre
            or not direccion
            or not telefono
            or not password
        ):

            return """
            <h2>Faltan datos</h2>

            <a href="/registro-cliente">
            Volver
            </a>
            """


        datos = {

            "nit": nit,

            "nombre": nombre,

            "direccion": direccion,

            "telefono": telefono,

            "password_hash": generate_password_hash(password)

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


    # -----------------------------------------------------
    # NIT DEL CLIENTE
    # -----------------------------------------------------

    nit_cliente = str(
        cliente.get(
            "nit",
            request.cookies.get(
                "cliente_nit",
                ""
            )
        )
    ).strip()


    # -----------------------------------------------------
    # OBTENER PEDIDOS
    # -----------------------------------------------------

    todos_los_pedidos = obtener_coleccion(
        "pedidos"
    )


    pedidos_cliente = []


    # -----------------------------------------------------
    # FILTRAR
    # -----------------------------------------------------

    for pedido in todos_los_pedidos:

        datos_pedido_cliente = pedido.get(
            "cliente",
            {}
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


    # -----------------------------------------------------
    # ORDENAR
    # -----------------------------------------------------

    pedidos_cliente.sort(
        key=lambda x: str(
            x.get(
                "fecha",
                ""
            )
        ),
        reverse=True
    )


    # -----------------------------------------------------
    # TARJETAS
    # -----------------------------------------------------

    tarjetas = ""


    for pedido in pedidos_cliente:

        pedido_id = pedido.get(
            "_id",
            "Sin número"
        )


        estado = pedido.get(
            "estado",
            "Pendiente"
        )


        fecha = pedido.get(
            "fecha",
            ""
        )

        # -------------------------------------------------
        # FORMATEAR FECHA DEL PEDIDO - HORA COLOMBIA
        # -------------------------------------------------

        try:

            fecha_obj = datetime.fromisoformat(
                str(fecha).replace(
                    "Z",
                    "+00:00"
                )
            )

            hora_colombia = timezone(
                timedelta(
                    hours=-5
                )
            )

            fecha_colombia = fecha_obj.astimezone(
                hora_colombia
            )

            hora_mostrar = (
                fecha_colombia
                .strftime("%I:%M")
                .lstrip("0")
            )

            if fecha_colombia.hour < 12:
                periodo = "a. m."
            else:
                periodo = "p. m."

            fecha_mostrar = (
                fecha_colombia.strftime(
                    "%d/%m/%Y"
                )
                + " - "
                + hora_mostrar
                + " "
                + periodo
            )

        except:

            fecha_mostrar = str(fecha) 


        total = pedido.get(
            "total",
            0
        )


        articulos = pedido.get(
            "articulos",
            []
        )


        # -------------------------------------------------
        # DATOS DE ENTREGA Y ORIGEN
        # -------------------------------------------------

        fecha_entrega = str(
            pedido.get(
                "fecha_entrega",
                ""
            )
        ).strip()


        observaciones = str(
            pedido.get(
                "observaciones",
                ""
            )
        ).strip()


        creado_por = str(
            pedido.get(
                "creado_por",
                ""
            )
        ).strip().lower()


        # -------------------------------------------------
        # FORMATEAR FECHA DE ENTREGA
        # -------------------------------------------------

        fecha_entrega_mostrar = (
            fecha_entrega
        )


        if fecha_entrega:

            try:

                fecha_entrega_mostrar = (
                    datetime.strptime(
                        fecha_entrega,
                        "%Y-%m-%d"
                    ).strftime(
                        "%d/%m/%Y"
                    )
                )

            except:

                pass


        # -------------------------------------------------
        # ORIGEN
        # -------------------------------------------------

        if creado_por == "administrador":

            origen_pedido = (
                "Pedido tomado por Alianzas Pharma"
            )

        else:

            origen_pedido = (
                "Pedido realizado por la droguería"
            )

        # -------------------------------------------------
        # CAJA VISUAL DE ENTREGA
        # -------------------------------------------------

        entrega_html = ""


        if (
            fecha_entrega
            or observaciones
            or creado_por
        ):

            entrega_html = f"""
            <div
                style="
                    margin:15px 0;
                    padding:14px 16px;
                    background:#eef7ff;
                    border-left:4px solid #3498db;
                    border-radius:8px;
                    line-height:1.7;
                "
            >

                <strong>📦 Datos de entrega</strong>

                <br>

                {
                    "📅 Entrega solicitada: "
                    + fecha_entrega_mostrar
                    + "<br>"
                    if fecha_entrega
                    else ""
                }

                {
                    "📝 Observaciones: "
                    + observaciones
                    + "<br>"
                    if observaciones
                    else ""
                }

                🏷️ Origen: {origen_pedido}

            </div>
            """



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
                    * int(cantidad)
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
        # ESTADO
        # -------------------------------------------------

        estado_normalizado = str(
            estado
        ).strip().lower()


        if estado_normalizado == "cancelado":

            estado_html = """
                <span
                    class="estado cancelado"
                >
                    Cancelado
                </span>
            """

            cancelado_html = """
                <div class="pedido-cancelado">

                    <strong>
                        🚫 Este pedido fue cancelado.
                    </strong>

                    <p>
                        El pedido ya no será despachado
                        y los productos fueron devueltos
                        al inventario.
                    </p>

                </div>
            """


        else:

            estado_html = f"""
                <span class="estado">
                    {estado}
                </span>
            """


            cancelado_html = ""


        tarjetas += f"""
        <div class="pedido">

            <div class="pedido-header">

                <div>

                    <h2>
                        🧾 {pedido_id}
                    </h2>

                    <p>
                        Fecha:
                        {fecha_mostrar}
                    </p>

                </div>

                {estado_html}

            </div>

                {entrega_html}   

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


            <div class="acciones-pedido">

                {
                    f'''
                <form
                    method="POST"
                    action="/cancelar-pedido"
                    onsubmit="return confirm('¿Está seguro de cancelar este pedido? Las unidades volverán al inventario.');"
                >

                    <input
                       type="hidden"
                       name="pedido_id"
                       value="{pedido_id}"
                    >
                    <button
                        type="submit"
                        class="btn-cancelar"
                    >
                        🚫 Cancelar pedido
                    </button>
                </form>    
                    '''
                    if estado_normalizado == "pendiente"
                    else ""
                }


                {
                    f'''
                    <form
                       method="POST"
                       action="/eliminar-pedido-historial"
                       onsubmit="return confirm('¿Está seguro de eliminar este pedido del historial? Esta acción no se puede deshacer.');"
                    >

                     <input
                       type="hidden"
                       name="pedido_id"
                       value="{pedido_id}"
                    >
                    <button
                        type="submit"
                        class="btn-eliminar"
                    >
                        🗑️ Eliminar del historial
                    </button>
                    '''
                    if estado_normalizado != "pendiente"
                    else ""
                }

            </div>


            {cancelado_html}

        </div>
        """

        


    # -----------------------------------------------------
    # NO HAY PEDIDOS
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # PÁGINA
    # -----------------------------------------------------

    return f"""


   <script>

async function cancelarPedido(pedidoId) {{

    const confirmar = confirm(
        "⚠️ ¿Estás seguro de cancelar este pedido?\n\n" +
        "El pedido será cancelado y las unidades " +
        "volverán al inventario."
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
                    "Content-Type": "application/json"
                }},

                body: JSON.stringify({{
                    pedido_id: pedidoId
                }})
            }}
        );


        const resultado = await respuesta.json();


        if (resultado.status === "ok") {{

            alert(
                "✅ " + resultado.message
            );

            window.location.reload();

            return;
        }}


        alert(
            "❌ " +
            (
                resultado.message ||
                "No fue posible cancelar el pedido."
            )
        );


    }} catch (error) {{

        console.error(
            "Error cancelando pedido:",
            error
        );

        alert(
            "❌ Ocurrió un error al cancelar el pedido."
        );

    }}

}}

<script>

async function cancelarPedido(pedidoId) {{

    const confirmar = confirm(
        "¿Estas seguro de cancelar este pedido? " +
        "El pedido sera cancelado y las unidades volveran al inventario."
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
                    "Content-Type": "application/json"
                }},

                body: JSON.stringify({{
                    pedido_id: pedidoId
                }})
            }}
        );

        const resultado = await respuesta.json();

        if (resultado.status === "ok") {{

            alert(
                "Pedido cancelado correctamente. " +
                "Las unidades fueron devueltas al inventario."
            );

            window.location.reload();

            return;
        }}

        alert(
            resultado.message ||
            "No fue posible cancelar el pedido."
        );

    }} catch (error) {{

        console.error(
            "Error cancelando pedido:",
            error
        );

        alert(
            "Ocurrio un error al cancelar el pedido."
        );

    }}

}}


async function eliminarPedido(pedidoId) {{

    const confirmar = confirm(
        "¿Estas seguro de eliminar este pedido del historial? " +
        "Esta accion no se puede deshacer."
    );

    if (!confirmar) {{
        return;
    }}

    try {{

        const respuesta = await fetch(
            "/eliminar-pedido-historial",
            {{
                method: "POST",

                headers: {{
                    "Content-Type": "application/json"
                }},

                body: JSON.stringify({{
                    pedido_id: pedidoId
                }})
            }}
        );

        const resultado = await respuesta.json();

        if (resultado.status === "ok") {{

            alert(
                "El pedido fue eliminado del historial."
            );

            window.location.reload();

            return;
        }}

        alert(
            resultado.message ||
            "No fue posible eliminar el pedido."
        );

    }} catch (error) {{

        console.error(
            "Error eliminando pedido:",
            error
        );

        alert(
            "Ocurrio un error al eliminar el pedido."
        );

    }}

}}

</script>

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

    margin:
        0 0 8px 0;

    font-size:
        28px;

}}


.encabezado p {{

    margin: 0;

    color:
        #64748b;

}}


.pedido {{

    background:
        white;

    border-radius:
        16px;

    padding:
        25px;

    margin-bottom:
        20px;

    box-shadow:
        0 10px 25px
        rgba(0,0,0,0.05);

}}


.pedido-header {{

    display:
        flex;

    justify-content:
        space-between;

    align-items:
        center;

    gap:
        20px;

    border-bottom:
        1px solid #e5e7eb;

    padding-bottom:
        15px;

    margin-bottom:
        15px;

}}


.pedido-header h2 {{

    margin:
        0 0 5px 0;

    font-size:
        20px;

}}


.pedido-header p {{

    margin:
        0;

    color:
        #64748b;

    font-size:
        14px;

}}


.estado {{

    background:
        #fff3cd;

    color:
        #856404;

    padding:
        8px 14px;

    border-radius:
        20px;

    font-weight:
        bold;

    font-size:
        14px;

}}


.estado.cancelado {{

    background:
        #ffe0e0;

    color:
        #b91c1c;

}}


.producto-pedido {{

    display:
        flex;

    justify-content:
        space-between;

    align-items:
        center;

    padding:
        12px 0;

    border-bottom:
        1px solid #f1f5f9;

}}


.producto-pedido strong {{

    color:
        #2c3e50;

}}


.producto-pedido span {{

    color:
        #64748b;

    font-size:
        14px;

}}


.pedido-total {{

    display:
        flex;

    justify-content:
        space-between;

    align-items:
        center;

    margin-top:
        18px;

    padding-top:
        15px;

    border-top:
        2px solid #e5e7eb;

    font-size:
        18px;

}}


.pedido-total strong {{

    color:
        #16a34a;

    font-size:
        22px;

}}


.pedido-cancelado {{

    background:
        #fff1f1;

    color:
        #b91c1c;

    padding:
        18px;

    border-radius:
        10px;

    margin-top:
        20px;

}}


.pedido-cancelado strong {{

    display:
        block;

    margin-bottom:
        8px;

}}


.pedido-cancelado p {{

    margin:
        0;

    font-size:
        14px;

}}

        .acciones-pedido {{
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 20px;
            flex-wrap: wrap;
        }}


        .acciones-pedido button {{
            border: none;
            padding: 10px 18px;
            border-radius: 8px;
            font-weight: bold;
            cursor: pointer;
            font-size: 14px;
        }}


        .btn-cancelar {{
            background: #e74c3c;
            color: white;
        }}


        .btn-cancelar:hover {{
            background: #c0392b;
        }}


        .btn-eliminar {{
            background: #64748b;
            color: white;
        }}


        .btn-eliminar:hover {{
            background: #475569;
        }}


.sin-pedidos {{

    background:
        white;

    text-align:
        center;

    padding:
        60px 30px;

    border-radius:
        16px;

    box-shadow:
        0 10px 25px
        rgba(0,0,0,0.05);

}}


.icono {{

    font-size:
        50px;

    margin-bottom:
        15px;

}}


.sin-pedidos h2 {{

    margin-bottom:
        8px;

}}


.sin-pedidos p {{

    color:
        #64748b;

}}


.volver {{

    display:
        inline-block;

    margin-top:
        20px;

    background:
        #3498db;

    color:
        white;

    padding:
        12px 22px;

    border-radius:
        25px;

    text-decoration:
        none;

    font-weight:
        bold;

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

        # -------------------------------------------------
        # CLIENTE
        # -------------------------------------------------

        cliente = obtener_cliente_logueado()


        if not cliente:

            return jsonify({

                "status": "error",

                "message":
                    "La sesión del cliente "
                    "no es válida."

            }), 401


        datos = request.get_json(
            silent=True
        ) or {}


        pedido_id = str(
           datos.get(
                 "pedido_id",
                request.form.get(
                  "pedido_id",
                 ""
        )
    )
).strip()


        if not pedido_id:

            return jsonify({

                "status": "error",

                "message":
                    "No se recibió el número "
                    "del pedido."

            }), 400


        # -------------------------------------------------
        # BUSCAR PEDIDO
        # -------------------------------------------------

        pedido = obtener_documento(
            "pedidos",
            pedido_id
        )


        if not pedido:

            return jsonify({

                "status": "error",

                "message":
                    "El pedido no existe."

            }), 404


        # -------------------------------------------------
        # VERIFICAR CLIENTE
        # -------------------------------------------------

        datos_pedido_cliente = pedido.get(
            "cliente",
            {}
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

                "status": "error",

                "message":
                    "No tienes permiso "
                    "para cancelar este pedido."

            }), 403


        # -------------------------------------------------
        # VERIFICAR ESTADO
        # -------------------------------------------------

        estado_actual = str(
            pedido.get(
                "estado",
                "Pendiente"
            )
        ).strip()


        if estado_actual != "Pendiente":

            return jsonify({

                "status": "error",

                "message":
                    "Este pedido ya no puede "
                    "ser cancelado porque su "
                    f"estado es: {estado_actual}"

            }), 400


        # -------------------------------------------------
        # ARTÍCULOS
        # -------------------------------------------------

        articulos = pedido.get(
            "articulos",
            []
        )


        if not articulos:

            return jsonify({

                "status": "error",

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

                    "status": "error",

                    "message":
                        "El pedido contiene "
                        "un producto con "
                        "datos inválidos."

                }), 400


            producto = obtener_documento(
                "productos",
                producto_id
            )


            if not producto:

                return jsonify({

                    "status": "error",

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


            cantidad = item[
                "cantidad"
            ]


            existencias_antes = item[
                "existencias_antes"
            ]


            nuevas_existencias = (
                existencias_antes
                + cantidad
            )


            producto[
                "existencias"
            ] = nuevas_existencias


            guardado = guardar_documento(
                "productos",
                item["id"],
                producto
            )


            if not guardado:

                # -----------------------------------------
                # REVERTIR
                # -----------------------------------------

                for anterior in (
                    productos_actualizados
                ):

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
                    existencias_antes

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

            

            # ---------------------------------------------
            # REVERTIR INVENTARIO
            # ---------------------------------------------

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


        # -------------------------------------------------
        # ÉXITO
        # -------------------------------------------------

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



          # Si vino desde el formulario de Mis Pedidos
        if request.form.get("pedido_id"):

             return redirect(
                url_for("mis_pedidos")
            )


        # Si vino mediante JSON


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
            "========================================"
        )

        print(
            "❌ ERROR CANCELANDO PEDIDO"
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
                "Error cancelando el pedido: "
                + str(e)

        }), 500

# =========================================================
# ELIMINAR PEDIDO DEL HISTORIAL
# =========================================================

@app.route(
    "/eliminar-pedido-historial",
    methods=["POST"]
)
def eliminar_pedido_historial():

    try:

        # -------------------------------------------------
        # VERIFICAR CLIENTE LOGUEADO
        # -------------------------------------------------

        cliente = obtener_cliente_logueado()

        if not cliente:

            return redirect(
                url_for("inicio")
            )


        # -------------------------------------------------
        # RECIBIR ID DEL PEDIDO
        # -------------------------------------------------

        pedido_id = str(
            request.form.get(
                "pedido_id",
                ""
            )
        ).strip()


        if not pedido_id:

            return redirect(
                url_for("mis_pedidos")
            )


        # -------------------------------------------------
        # BUSCAR PEDIDO
        # -------------------------------------------------

        pedido = obtener_documento(
            "pedidos",
            pedido_id
        )


        if not pedido:

            return redirect(
                url_for("mis_pedidos")
            )


        # -------------------------------------------------
        # COMPROBAR QUE EL PEDIDO SEA DEL CLIENTE
        # -------------------------------------------------

        nit_cliente = str(
            cliente.get(
                "nit",
                request.cookies.get(
                    "cliente_nit",
                    ""
                )
            )
        ).strip()


        datos_pedido_cliente = pedido.get(
            "cliente",
            {}
        )


        nit_pedido = str(
            datos_pedido_cliente.get(
                "nit",
                ""
            )
        ).strip()


        if nit_cliente != nit_pedido:

            return redirect(
                url_for("mis_pedidos")
            )


        # -------------------------------------------------
        # SOLO BORRAR PEDIDOS CANCELADOS
        # -------------------------------------------------

        estado = str(
            pedido.get(
                "estado",
                ""
            )
        ).strip().lower()


        if estado != "cancelado":

            return redirect(
                url_for("mis_pedidos")
            )


        # -------------------------------------------------
        # URL DEL DOCUMENTO EN FIRESTORE
        # -------------------------------------------------

        url = (
            firestore_base_url()
            + "/"
            + quote(
                "pedidos",
                safe=""
            )
            + "/"
            + quote(
                pedido_id,
                safe=""
            )
        )


        # -------------------------------------------------
        # ELIMINAR DOCUMENTO
        # -------------------------------------------------

        respuesta = requests.delete(
            url,
            headers=firestore_headers(),
            timeout=10
        )


        print(
            "========================================"
        )

        print(
            "🗑️ ELIMINAR PEDIDO DEL HISTORIAL"
        )

        print(
            f"Pedido: {pedido_id}"
        )

        print(
            f"HTTP: {respuesta.status_code}"
        )

        print(
            "========================================"
        )


        if not respuesta.ok:

            print(
                "❌ No fue posible eliminar el pedido"
            )

            print(
                respuesta.text[:1000]
            )


        # -------------------------------------------------
        # VOLVER A MIS PEDIDOS
        # -------------------------------------------------

        return redirect(
            url_for("mis_pedidos")
        )


    except Exception as e:

        print(
            "========================================"
        )

        print(
            "❌ ERROR ELIMINANDO PEDIDO"
        )

        print(
            str(e)
        )

        print(
            "========================================"
        )


        return redirect(
            url_for("mis_pedidos")
        )




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
        # VERIFICAR CLIENTE
        # -------------------------------------------------

        cliente = obtener_cliente_logueado()


        if not cliente:

            return jsonify({

                "status":
                    "error",

                "message":
                    "La sesión del cliente "
                    "no es válida."

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


        fecha_entrega = str(
            datos.get(
                "fecha_entrega",
                ""
            )
        ).strip()


        observaciones = str(
            datos.get(
                "observaciones",
                ""
            )
        ).strip()
        
            
            

        


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
                            articulo.get(
                                "nombre",
                                "Producto"
                            )
                        )

                }), 400


            try:

                precio = int(
                    articulo.get(
                        "precio",
                        producto.get(
                            "precio",
                            0
                        )
                    )
                )

            except:

                precio = 0


            subtotal = (
                precio * cantidad
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


            existencias_actuales = int(
                producto.get(
                    "existencias",
                    0
                )
            )


            producto[
                "existencias"
            ] = (
                existencias_actuales
                - cantidad
            )


            guardado = guardar_documento(
                "productos",
                producto_id,
                producto
            )


            if not guardado:

                # -----------------------------------------
                # REVERTIR LO DESCONTADO
                # -----------------------------------------

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
                        "todo el inventario."

                }), 500


            productos_descontados.append({

                "id":
                    producto_id,

                "producto":
                    producto,

                "existencias_antes":
                    existencias_actuales

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
            + uuid.uuid4()
            .hex[:12]
            .upper()
        )


        # -------------------------------------------------
        # GUARDAR PEDIDO
        # -------------------------------------------------

        pedido = {

            "cliente":
                datos_cliente,

            "articulos":
                articulos,

            "total":
                total,

            "estado":
                "Pendiente",

            "fecha":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "fecha_entrega":
                fecha_entrega,

            "observaciones":
                observaciones,

            "creado_por":
                "cliente"

        }


        guardado = guardar_documento(
            "pedidos",
            pedido_id,
            pedido
        )


        if not guardado:

            # ---------------------------------------------
            # REVERTIR INVENTARIO
            # ---------------------------------------------

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


        # -------------------------------------------------
        # LOG
        # -------------------------------------------------

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
# ADMINISTRADOR - ETAPA 1
# LOGIN + VISUALIZAR PRODUCTOS
# =========================================================

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    ""
).strip()


# =========================================================
# TOKEN DE SESIÓN ADMIN
# =========================================================

def token_sesion_admin():

    if not ADMIN_PASSWORD:
        return ""

    return hashlib.sha256(
        ADMIN_PASSWORD.encode("utf-8")
    ).hexdigest()


# =========================================================
# VERIFICAR SESIÓN ADMIN
# =========================================================

def verificar_sesion_admin():

    token_actual = request.cookies.get(
        "admin_sesion",
        ""
    )

    token_esperado = token_sesion_admin()

    if not token_actual or not token_esperado:
        return False

    return hmac.compare_digest(
        token_actual,
        token_esperado
    )

# =========================================================
# DESCARGAR RESPALDO DE FIRESTORE
# =========================================================





@app.route("/admin/respaldo")
def descargar_respaldo():

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    colecciones = [
        "clientes",
        "productos",
        "pedidos",
        "banners",
        "configuracion"
    ]


    memoria_zip = BytesIO()


    with zipfile.ZipFile(
        memoria_zip,
        "w",
        zipfile.ZIP_DEFLATED
    ) as archivo_zip:

        for coleccion in colecciones:

            datos = obtener_coleccion(
                coleccion
            )


            contenido_json = json.dumps(
                datos,
                ensure_ascii=False,
                indent=2
            )


            archivo_zip.writestr(
                f"{coleccion}.json",
                contenido_json
            )


    memoria_zip.seek(0)


    zona_colombia = timezone(
        timedelta(hours=-5)
    )


    fecha_respaldo = datetime.now(
        zona_colombia
    ).strftime(
        "%Y-%m-%d_%H-%M"
    )


    return send_file(
        memoria_zip,
        mimetype="application/zip",
        as_attachment=True,
        download_name=(
            "Respaldo_Alianzas_Pharma_"
            + fecha_respaldo
            + ".zip"
        )
    )


# =========================================================
# LOGIN ADMINISTRADOR
# =========================================================

@app.route("/admin-acceso")
def admin_acceso():

    return redirect(
        url_for("admin_login")
    )


@app.route(
    "/login",
    methods=["GET", "POST"]
)
@app.route(
    "/admin-login",
    methods=["GET", "POST"]
)
def admin_login():

    # -----------------------------------------------------
    # VERIFICAR VARIABLE DE ENTORNO
    # -----------------------------------------------------

    if not ADMIN_PASSWORD:

        return """
        <html>

        <body
            style="
            font-family:sans-serif;
            text-align:center;
            padding:50px;
            "
        >

            <h2>
                ⚠️ Administrador no configurado
            </h2>

            <p>
                Falta configurar ADMIN_PASSWORD
                en Vercel.
            </p>

        </body>

        </html>
        """, 500


    # -----------------------------------------------------
    # RECIBIR CONTRASEÑA
    # -----------------------------------------------------

    if request.method == "POST":

        password = str(
            request.form.get(
                "password",
                ""
            )
        )


        if hmac.compare_digest(
            password,
            ADMIN_PASSWORD
        ):

            respuesta = make_response(
                redirect(
                    url_for(
                        "administrador"
                    )
                )
            )


            respuesta.set_cookie(
                "admin_sesion",
                token_sesion_admin(),
                max_age=60 * 60 * 8,
                path="/",
                httponly=True,
                secure=True,
                samesite="Lax"
            )


            return respuesta


        return """
        <html>

        <body
            style="
            font-family:sans-serif;
            text-align:center;
            padding:50px;
            "
        >

            <h2>
                ❌ Contraseña incorrecta
            </h2>

            <a href="/login">
                Volver
            </a>

        </body>

        </html>
        """, 401


    # -----------------------------------------------------
    # PANTALLA LOGIN
    # -----------------------------------------------------

    return """
    <!DOCTYPE html>

    <html lang="es">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            Administrador - Alianzas Pharma
        </title>

        <link
            rel="icon"
            type="image/jpeg"
            href="/public/logo.jpeg"
        >

        <link
            rel="manifest"
            href="/manifest.json"
        >

        
        <link
            rel="apple-touch-icon"
            sizes="180x180"
            href="/public/apple-touch-icon.png"
        >

    </head>


    <body
        style="
        font-family:'Segoe UI',sans-serif;
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
            padding:35px;
            border-radius:14px;
            box-shadow:0 8px 25px rgba(0,0,0,0.08);
            text-align:center;
            width:320px;
            "
        >


            <img
                src="/public/logo.jpeg"
                style="
                max-height:75px;
                margin-bottom:10px;
                border-radius:8px;
                "
            >


            <h2
                style="
                color:#2c3e50;
                "
            >
                Administrador 🔐
            </h2>


            <form
                method="POST"
                action="/login"
            >

            <div style="position:relative;">

    <input
        type="password"
        id="password_admin"
        name="password"
        placeholder="Contraseña de administrador"
        required
        style="
            box-sizing:border-box;
            width:100%;
            padding:12px;
            padding-right:48px;
            border:1px solid #cbd5e1;
            border-radius:8px;
            margin-bottom:15px;
        "
    >

    <button
        type="button"
        id="ojo_password_admin"
        onclick="mostrarClaveAdmin()"
        style="
            position:absolute;
            right:12px;
            top:12px;
            border:none;
            background:transparent;
            cursor:pointer;
            font-size:20px;
            padding:0;
        "
        title="Mostrar contraseña"
    >
        👁️
    </button>

</div>
                


                <button
                    type="submit"
                    style="
                    width:100%;
                    background:#3498db;
                    color:white;
                    border:none;
                    padding:12px;
                    border-radius:8px;
                    font-weight:bold;
                    cursor:pointer;
                    "
                >

                    Entrar al Panel

                </button>


            </form>


        </div>

<script>

    function mostrarClaveAdmin() {

        const campo =
            document.getElementById(
                "password_admin"
            );

        const boton =
            document.getElementById(
                "ojo_password_admin"
            );

        if (campo.type === "password") {

            campo.type = "text";
            boton.innerText = "🙈";
            boton.title = "Ocultar contraseña";

        } else {

            campo.type = "password";
            boton.innerText = "👁️";
            boton.title = "Mostrar contraseña";

        }

    }

</script>
        
    </body>

    </html>
    """


# =========================================================
# PANEL ADMINISTRADOR
# =========================================================

@app.route(
    "/admin",
    methods=["GET", "POST"]
)
def administrador():

    # -----------------------------------------------------
    # PROTEGER ADMIN
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for(
                "admin_login"
            )
        )


    # -----------------------------------------------------
    # TODAVÍA NO ACTIVAMOS CREAR PRODUCTOS
    # -----------------------------------------------------

    if request.method == "POST":

        return """
        <html>

        <body
            style="
            font-family:sans-serif;
            text-align:center;
            padding:50px;
            "
        >

            <h2>
                ℹ️ Esta función se habilitará
                en el siguiente paso.
            </h2>

            <a href="/admin">
                Volver al administrador
            </a>

        </body>

        </html>
        """


    # -----------------------------------------------------
    # CARGAR PRODUCTOS ACTUALES
    # -----------------------------------------------------

    productos = obtener_productos()


    # -----------------------------------------------------
    # MOSTRAR ADMIN.HTML EXISTENTE
    # -----------------------------------------------------

    return render_template(
        "admin.html",
        productos=productos
    )


# =========================================================
# SALIR DEL ADMINISTRADOR
# =========================================================

@app.route("/admin-salir")
def admin_salir():

    respuesta = make_response(
        redirect(
            url_for(
                "admin_login"
            )
        )
    )


    respuesta.set_cookie(
        "admin_sesion",
        "",
        expires=0,
        path="/"
    )


    return respuesta

# =========================================================
# ADMIN - ACTUALIZAR EXISTENCIAS +1 / -1
# =========================================================

# =========================================================
# ADMIN - ACTUALIZAR PRODUCTO
# +1 / -1 / EDITAR DATOS
# =========================================================

@app.route(
    "/actualizar-stock/<producto_id>",
    methods=["POST"]
)
def actualizar_stock_admin(producto_id):

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # BUSCAR PRODUCTO ACTUAL
    # -----------------------------------------------------

    producto = obtener_documento(
        "productos",
        producto_id
    )


    if not producto:

        return redirect(
            url_for("administrador")
        )




    # =====================================================
    # CASO 1: BOTONES +1 / -1
    # =====================================================

    cantidad_cambio = request.form.get(
        "cantidad_cambio"
    )


    if cantidad_cambio is not None:

        try:

            cantidad_cambio = int(
                cantidad_cambio
            )

        except:

            return redirect(
                url_for("administrador")
            )


        # Solo permitir +1 o -1
        if cantidad_cambio not in (-1, 1):

            return redirect(
                url_for("administrador")
            )


        try:

            existencias_actuales = int(
                producto.get(
                    "existencias",
                    0
                )
            )

        except:

            existencias_actuales = 0


        nuevas_existencias = (
            existencias_actuales
            + cantidad_cambio
        )


        if nuevas_existencias < 0:

            nuevas_existencias = 0


        producto["existencias"] = (
            nuevas_existencias
        )


        guardado = guardar_documento(
            "productos",
            producto_id,
            producto
        )


        if not guardado:

            print(
                "❌ Error actualizando existencias: "
                + producto_id
            )


        return redirect(
            url_for("administrador")
        )


    # =====================================================
    # CASO 2: EDITAR NOMBRE, PRECIO Y EXISTENCIAS
    # =====================================================

    nombre = str(
        request.form.get(
            "nombre",
            ""
        )
    ).strip()


    precio_form = str(
        request.form.get(
            "precio",
            ""
        )
    ).strip()


    existencias_form = str(
        request.form.get(
            "existencias",
            ""
        )
    ).strip()


    # -----------------------------------------------------
    # VALIDAR CAMPOS
    # -----------------------------------------------------

    if (
        not nombre
        or not precio_form
        or not existencias_form
    ):

        return redirect(
            url_for("administrador")
        )


    try:

        precio = int(
            precio_form
        )

        existencias = int(
            existencias_form
        )

    except:

        return redirect(
            url_for("administrador")
        )


    # -----------------------------------------------------
    # NO PERMITIR VALORES NEGATIVOS
    # -----------------------------------------------------

    if precio < 0:

        precio = 0


    if existencias < 0:

        existencias = 0


    # -----------------------------------------------------
    # ACTUALIZAR SOLO LOS DATOS NECESARIOS
    # -----------------------------------------------------

    producto["nombre"] = nombre

    producto["precio"] = precio

    producto["existencias"] = existencias


    # IMPORTANTE:
    # NO MODIFICAMOS producto["imagen"]
    # La fotografía actual permanece igual.


    # -----------------------------------------------------
    # GUARDAR EN FIREBASE
    # -----------------------------------------------------

    guardado = guardar_documento(
        "productos",
        producto_id,
        producto
    )


    if not guardado:

        print(
            "❌ Error editando producto: "
            + producto_id
        )


    # -----------------------------------------------------
    # VOLVER AL ADMINISTRADOR
    # -----------------------------------------------------

    return redirect(
        url_for("administrador")
    )


    # -----------------------------------------------------
    # RECIBIR CAMBIO
    # -----------------------------------------------------

    cantidad_cambio = request.form.get(
        "cantidad_cambio"
    )


    # Por ahora esta ruta solamente manejará +1 y -1
    if cantidad_cambio is None:

        return redirect(
            url_for("administrador")
        )


    try:

        cantidad_cambio = int(
            cantidad_cambio
        )

    except:

        return redirect(
            url_for("administrador")
        )


    # -----------------------------------------------------
    # SOLO PERMITIR +1 O -1
    # -----------------------------------------------------

    if cantidad_cambio not in (-1, 1):

        return redirect(
            url_for("administrador")
        )


    # -----------------------------------------------------
    # BUSCAR PRODUCTO
    # -----------------------------------------------------

    producto = obtener_documento(
        "productos",
        producto_id
    )


    if not producto:

        return redirect(
            url_for("administrador")
        )


    # -----------------------------------------------------
    # EXISTENCIAS ACTUALES
    # -----------------------------------------------------

    try:

        existencias_actuales = int(
            producto.get(
                "existencias",
                0
            )
        )

    except:

        existencias_actuales = 0


    # -----------------------------------------------------
    # CALCULAR NUEVA EXISTENCIA
    # -----------------------------------------------------

    nuevas_existencias = (
        existencias_actuales
        + cantidad_cambio
    )


    # Nunca permitir cantidades negativas
    if nuevas_existencias < 0:

        nuevas_existencias = 0


    # -----------------------------------------------------
    # GUARDAR EN FIREBASE
    # -----------------------------------------------------

    producto["existencias"] = (
        nuevas_existencias
    )


    guardado = guardar_documento(
        "productos",
        producto_id,
        producto
    )


    if not guardado:

        print(
            "❌ No fue posible actualizar "
            f"existencias de {producto_id}"
        )


    # -----------------------------------------------------
    # VOLVER AL ADMIN
    # -----------------------------------------------------

    return redirect(
        url_for("administrador")
    )

# =========================================================
# ADMIN - ELIMINAR PRODUCTO
# =========================================================

@app.route(
    "/eliminar/<producto_id>",
    methods=["POST"]
)
def eliminar_producto_admin(producto_id):

    # Verificar administrador
    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # Buscar producto
    producto = obtener_documento(
        "productos",
        producto_id
    )


    if not producto:

        return redirect(
            url_for("administrador")
        )


    # URL DEL PRODUCTO EN FIRESTORE
    url = (
        firestore_base_url()
        + "/"
        + quote(
            "productos",
            safe=""
        )
        + "/"
        + quote(
            producto_id,
            safe=""
        )
    )


    try:

        respuesta = requests.delete(
            url,
            headers=firestore_headers(),
            timeout=10
        )


        if not respuesta.ok:

            print(
                "❌ ERROR ELIMINANDO PRODUCTO:"
            )

            print(
                respuesta.status_code
            )

            print(
                respuesta.text[:1000]
            )


            return redirect(
                url_for("administrador")
            )


        print(
            "✅ PRODUCTO ELIMINADO: "
            + producto_id
        )


    except Exception as e:

        print(
            "❌ ERROR ELIMINANDO PRODUCTO:"
        )

        print(
            str(e)
        )


    return redirect(
        url_for("administrador")
    )

# =========================================================
# ADMIN - VER PEDIDOS
# =========================================================

@app.route(
    "/ver-pedidos"
)
def ver_pedidos_admin():

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # OBTENER PEDIDOS DE FIREBASE
    # -----------------------------------------------------

    pedidos = obtener_coleccion(
        "pedidos"
    )


    # -----------------------------------------------------
    # PREPARAR ID PARA LA PLANTILLA
    # -----------------------------------------------------

    for pedido in pedidos:

        pedido["id"] = pedido.get(
            "_id",
            ""
        )


    # -----------------------------------------------------
    # MOSTRAR LOS MÁS NUEVOS PRIMERO
    # -----------------------------------------------------

    pedidos.sort(
        key=lambda x: str(
            x.get(
                "fecha",
                ""
            )
        ),
        reverse=True
    )


    # -----------------------------------------------------
    # MOSTRAR PÁGINA
    # -----------------------------------------------------

    return render_template(
        "pedidos.html",
        pedidos=pedidos
    )


# =========================================================
# ADMIN - DESPACHAR PEDIDO
# =========================================================

@app.route(
    "/cambiar-estado/<pedido_id>"
)
def cambiar_estado_pedido_admin(pedido_id):

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # BUSCAR PEDIDO
    # -----------------------------------------------------

    pedido = obtener_documento(
        "pedidos",
        pedido_id
    )


    if not pedido:

        return redirect(
            url_for("ver_pedidos_admin")
        )


    # -----------------------------------------------------
    # VERIFICAR ESTADO ACTUAL
    # -----------------------------------------------------

    estado_actual = str(
        pedido.get(
            "estado",
            "Pendiente"
        )
    ).strip()


    # Solamente se puede despachar un pedido pendiente
    if estado_actual.lower() != "pendiente":

        return redirect(
            url_for("ver_pedidos_admin")
        )


    # -----------------------------------------------------
    # CAMBIAR ESTADO
    # -----------------------------------------------------

    pedido["estado"] = "Despachado"


    # -----------------------------------------------------
    # GUARDAR EN FIREBASE
    # -----------------------------------------------------

    guardado = guardar_documento(
        "pedidos",
        pedido_id,
        pedido
    )


    if not guardado:

        print(
            "❌ ERROR CAMBIANDO ESTADO DEL PEDIDO: "
            + pedido_id
        )


        return redirect(
            url_for("ver_pedidos_admin")
        )


    print(
        "✅ PEDIDO DESPACHADO: "
        + pedido_id
    )


    # -----------------------------------------------------
    # VOLVER A VER PEDIDOS
    # -----------------------------------------------------

    return redirect(
        url_for("ver_pedidos_admin")
    )


# =========================================================
# ADMIN - DESCARGAR PEDIDO EN PDF
# =========================================================

@app.route(
    "/descargar-pdf/<pedido_id>"
)
def descargar_pdf_pedido(pedido_id):

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # BUSCAR PEDIDO
    # -----------------------------------------------------

    pedido = obtener_documento(
        "pedidos",
        pedido_id
    )


    if not pedido:

        return redirect(
            url_for("ver_pedidos_admin")
        )


    # -----------------------------------------------------
    # DATOS DEL PEDIDO
    # -----------------------------------------------------

    cliente = pedido.get(
        "cliente",
        {}
    )

    articulos = pedido.get(
        "articulos",
        []
    )

    total = pedido.get(
        "total",
        0
    )

    estado = pedido.get(
        "estado",
        ""
    )

    fecha = pedido.get(
        "fecha",
        ""
    )
    # -----------------------------------------------------
# FECHA Y HORA DE COLOMBIA
# -----------------------------------------------------

    try:

        fecha_obj = datetime.fromisoformat(
            str(fecha).replace(
                "Z",
                "+00:00"
            )
        )

        hora_colombia = timezone(
            timedelta(
                hours=-5
            )
        )

        fecha_colombia = (
            fecha_obj.astimezone(
                hora_colombia
            )
        )

        hora_pdf = (
            fecha_colombia
            .strftime("%I:%M")
            .lstrip("0")
        )

        if fecha_colombia.hour < 12:

            periodo = "a. m."

        else:

            periodo = "p. m."


        fecha_pdf = (
            fecha_colombia.strftime(
                "%d/%m/%Y"
            )
            + " - "
            + hora_pdf
            + " "
            + periodo
        )

    except Exception:

            fecha_pdf = str(fecha)

    # -----------------------------------------------------
    # CREAR PDF
    # -----------------------------------------------------

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=letter
    )

    ancho, alto = letter


    # -----------------------------------------------------
    # LOGO ALIANZAS PHARMA
    # -----------------------------------------------------
    
    try:

        logo_url = (
             request.host_url.rstrip("/")
             + "/public/logo.jpeg"
        )

        respuesta_logo = requests.get(
            logo_url,
            timeout=10
        )

        if respuesta_logo.ok:

            logo_imagen = ImageReader(
                BytesIO(
                    respuesta_logo.content
                )
            )

            pdf.drawImage(
                logo_imagen,
                50,
                alto - 105,
                width=95,
                height=60,
                preserveAspectRatio=True,
                mask="auto"
            )

        else:

            print(
            "⚠️ No se pudo descargar el logo:",
            respuesta_logo.status_code
            )

    except Exception as e:

        print(
        "⚠️ Error cargando logo en PDF:",
        str(e)
    )
    


    # -----------------------------------------------------
    # ENCABEZADO
    # -----------------------------------------------------

    pdf.setFont(
        "Helvetica-Bold",
        18
    )

    pdf.drawString(
        180,
        alto - 60,
        "ALIANZAS PHARMA"
    )


    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        180,
        alto - 82,
        "ORDEN DE PEDIDO"
    )


    pdf.line(
        50,
        alto - 115,
        ancho - 50,
        alto - 115
    )


    # -----------------------------------------------------
    # INFORMACIÓN DEL PEDIDO
    # -----------------------------------------------------

    y = alto - 145

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        50,
        y,
        "PEDIDO:"
    )

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        110,
        y,
        str(pedido_id)
    )


    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        350,
        y,
        "ESTADO:"
    )

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        405,
        y,
        str(estado)
    )


    y -= 20


    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        50,
        y,
        "FECHA:"
    )

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        110,
        y,
        str(fecha_pdf)
    )


    # -----------------------------------------------------
    # DATOS DE LA DROGUERÍA
    # -----------------------------------------------------

    y -= 40

    pdf.setFont(
        "Helvetica-Bold",
        12
    )

    pdf.drawString(
        50,
        y,
        "DATOS DE LA DROGUERIA"
    )

    y -= 22


    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        50,
        y,
        "Nombre: "
        + str(
            cliente.get(
                "nombre",
                ""
            )
        )
    )

    y -= 18


    pdf.drawString(
        50,
        y,
        "NIT: "
        + str(
            cliente.get(
                "nit",
                ""
            )
        )
    )

    y -= 18


    pdf.drawString(
        50,
        y,
        "Telefono: "
        + str(
            cliente.get(
                "telefono",
                ""
            )
        )
    )

    y -= 18


    direccion = str(
        cliente.get(
            "direccion",
            ""
        )
    )


    pdf.drawString(
        50,
        y,
        "Direccion: "
        + direccion[:80]
    )


    if len(direccion) > 80:

        y -= 16

        pdf.drawString(
            105,
            y,
            direccion[80:160]
        )

    # -----------------------------------------------------
    # ENTREGA SOLICITADA
    # -----------------------------------------------------

    fecha_entrega = str(
        pedido.get(
            "fecha_entrega",
            ""
        )
    ).strip()


    observaciones = str(
        pedido.get(
            "observaciones",
            ""
        )
    ).strip()


    creado_por = str(
        pedido.get(
            "creado_por",
            ""
        )
    ).strip().lower()


    # -----------------------------------------------------
    # FORMATEAR FECHA DE ENTREGA
    # -----------------------------------------------------

    if fecha_entrega:

        try:

            fecha_entrega_obj = datetime.strptime(
                fecha_entrega,
                "%Y-%m-%d"
            )

            fecha_entrega_pdf = (
                fecha_entrega_obj.strftime(
                    "%d/%m/%Y"
                )
            )

        except:

            fecha_entrega_pdf = fecha_entrega

    else:

        fecha_entrega_pdf = "No especificada"


    # -----------------------------------------------------
    # ORIGEN DEL PEDIDO
    # -----------------------------------------------------

    if creado_por == "administrador":

        origen_pdf = (
            "Pedido tomado por Alianzas Pharma"
        )

    else:

        origen_pdf = (
            "Pedido realizado por la drogueria"
        )


    # -----------------------------------------------------
    # DIBUJAR DATOS DE ENTREGA
    # -----------------------------------------------------

    y -= 32

    pdf.setFont(
        "Helvetica-Bold",
        11
    )

    pdf.drawString(
        50,
        y,
        "ENTREGA SOLICITADA"
    )


    y -= 20

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        50,
        y,
        "Fecha: "
        + fecha_entrega_pdf
    )


    y -= 18

    if observaciones:

        pdf.drawString(
            50,
            y,
            "Observaciones: "
            + observaciones[:60]
        )

        if len(observaciones) > 60:

            y -= 16

            pdf.drawString(
                120,
                y,
                observaciones[60:120]
            )

    else:

        pdf.drawString(
            50,
            y,
            "Observaciones: Sin observaciones"
        )


    y -= 18

    pdf.drawString(
        50,
        y,
        "Origen: "
        + origen_pdf
    )



    # -----------------------------------------------------
    # PRODUCTOS
    # -----------------------------------------------------

    y -= 40

    pdf.setFont(
        "Helvetica-Bold",
        12
    )

    pdf.drawString(
        50,
        y,
        "PRODUCTOS"
    )

    y -= 25


    # Encabezados de tabla

    pdf.setFont(
        "Helvetica-Bold",
        9
    )

    pdf.drawString(
        50,
        y,
        "Producto"
    )

    pdf.drawString(
        340,
        y,
        "Cant."
    )

    pdf.drawString(
        390,
        y,
        "Precio"
    )

    pdf.drawString(
        475,
        y,
        "Subtotal"
    )


    y -= 8


    pdf.line(
        50,
        y,
        ancho - 50,
        y
    )


    y -= 18


    # -----------------------------------------------------
    # FILAS DE PRODUCTOS
    # -----------------------------------------------------

    pdf.setFont(
        "Helvetica",
        8
    )


    for articulo in articulos:

        nombre = str(
            articulo.get(
                "nombre",
                articulo.get(
                    "producto",
                    "Producto"
                )
            )
        )


        try:

            cantidad = int(
                articulo.get(
                    "cantidad",
                    0
                )
            )

        except:

            cantidad = 0


        try:

            precio = int(
                articulo.get(
                    "precio",
                    0
                )
            )

        except:

            precio = 0


        subtotal = (
            cantidad
            * precio
        )


        # -------------------------------------------------
        # NOMBRE DEL PRODUCTO EN VARIAS LÍNEAS
        # -------------------------------------------------

        palabras = str(nombre).split()

        lineas_nombre = []

        linea_actual = ""

        ancho_maximo_nombre = 270


        for palabra in palabras:

            if linea_actual:

                prueba = (
                    linea_actual
                    + " "
                    + palabra
                )

            else:

                prueba = palabra


            ancho_prueba = pdf.stringWidth(
                prueba,
                "Helvetica",
                10
            )


            if ancho_prueba <= ancho_maximo_nombre:

                linea_actual = prueba

            else:

                if linea_actual:

                    lineas_nombre.append(
                        linea_actual
                    )

                linea_actual = palabra


        if linea_actual:

            lineas_nombre.append(
                linea_actual
            )


        if not lineas_nombre:

            lineas_nombre = [
                str(nombre)
            ]


        # -------------------------------------------------
        # PRIMERA LÍNEA DEL PRODUCTO
        # -------------------------------------------------

        pdf.drawString(
            50,
            y,
            lineas_nombre[0]
        )


        pdf.drawRightString(
            370,
            y,
            str(cantidad)
        )


        pdf.drawRightString(
            455,
            y,
            f"${precio:,.0f}"
        )


        pdf.drawRightString(
            ancho - 50,
            y,
            f"${subtotal:,.0f}"
        )


        # -------------------------------------------------
        # LÍNEAS ADICIONALES DEL NOMBRE
        # -------------------------------------------------

        if len(lineas_nombre) > 1:

            for linea_extra in lineas_nombre[1:]:

                y -= 14

                pdf.drawString(
                    50,
                    y,
                    linea_extra
                )


        # -------------------------------------------------
        # ESPACIO PARA EL SIGUIENTE PRODUCTO
        # -------------------------------------------------

        y -= 20


        # Nueva página si hay muchos productos
        if y < 100:

            pdf.showPage()

            y = alto - 60

            pdf.setFont(
                "Helvetica",
                8
            )


    # -----------------------------------------------------
    # TOTAL
    # -----------------------------------------------------

    y -= 10


    pdf.line(
        350,
        y,
        ancho - 50,
        y
    )


    y -= 25


    pdf.setFont(
        "Helvetica-Bold",
        14
    )


    pdf.drawRightString(
        ancho - 50,
        y,
        f"TOTAL: ${int(total):,.0f}"
    )


    # -----------------------------------------------------
    # PIE DE PÁGINA
    # -----------------------------------------------------

    pdf.setFont(
        "Helvetica",
        8
    )


    pdf.drawCentredString(
        ancho / 2,
        35,
        "Alianzas Pharma - Portal de Pedidos"
    )


    # -----------------------------------------------------
    # FINALIZAR PDF
    # -----------------------------------------------------

    pdf.save()

    buffer.seek(0)


    respuesta = make_response(
        buffer.getvalue()
    )


    respuesta.headers[
        "Content-Type"
    ] = "application/pdf"


    # -----------------------------------------------------
    # NOMBRE DEL ARCHIVO
    # -----------------------------------------------------

    nombre_drogueria = str(
        cliente.get(
            "nombre",
            "DROGUERIA"
        )
    ).strip()


    nombre_drogueria_archivo = (
        nombre_drogueria
        .replace(" ", "_")
        .replace("/", "-")
    )


    respuesta.headers[
        "Content-Disposition"
    ] = (
        f'attachment; filename="pedido_{nombre_drogueria_archivo}_{pedido_id}.pdf"'
    )


    return respuesta


# =========================================================
# ADMIN - DESCARGAR PORTAFOLIO DE PRODUCTOS PDF
# =========================================================

@app.route(
    "/admin/portafolio-pdf"
)
def descargar_portafolio_pdf():

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # OBTENER PRODUCTOS ACTUALES
    # -----------------------------------------------------

    productos = obtener_productos()

        # -----------------------------------------------------
    # MOSTRAR SOLO PRODUCTOS CON EXISTENCIAS
    # -----------------------------------------------------

    productos_disponibles = []

    for producto in productos:

        try:

            existencias = int(
                producto.get(
                    "existencias",
                    0
                )
            )

        except:

            existencias = 0


        if existencias > 0:

            productos_disponibles.append(
                producto
            )


    productos = productos_disponibles

    
     
    productos.sort(
        key=lambda p: str(
            p.get(
                "nombre",
                ""
            )
        ).lower()
    )


    # -----------------------------------------------------
    # CREAR PDF EN MEMORIA
    # -----------------------------------------------------

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=letter
    )

    ancho, alto = letter


    # -----------------------------------------------------
    # FECHA ACTUAL DE COLOMBIA
    # -----------------------------------------------------

    zona_colombia = timezone(
        timedelta(
            hours=-5
        )
    )

    ahora_colombia = datetime.now(
        zona_colombia
    )

    fecha_actualizacion = ahora_colombia.strftime(
        "%d/%m/%Y - %I:%M %p"
    )


    # -----------------------------------------------------
    # FUNCIÓN PARA DIVIDIR TEXTOS LARGOS
    # -----------------------------------------------------

    def dividir_texto(
        texto,
        ancho_maximo,
        fuente="Helvetica-Bold",
        tamano=9
    ):

        palabras = str(
            texto
        ).split()

        lineas = []

        linea = ""


        for palabra in palabras:

            if linea:

                prueba = (
                    linea
                    + " "
                    + palabra
                )

            else:

                prueba = palabra


            if pdf.stringWidth(
                prueba,
                fuente,
                tamano
            ) <= ancho_maximo:

                linea = prueba

            else:

                if linea:

                    lineas.append(
                        linea
                    )

                linea = palabra


        if linea:

            lineas.append(
                linea
            )


        return lineas


    # -----------------------------------------------------
    # ENCABEZADO DE CADA PÁGINA
    # -----------------------------------------------------

    def dibujar_encabezado():

        try:

            logo_url = (
                request.host_url.rstrip("/")
                + "/public/logo.jpeg"
            )

            respuesta_logo = requests.get(
                logo_url,
                timeout=8
            )


            if respuesta_logo.ok:

                logo = ImageReader(
                    BytesIO(
                        respuesta_logo.content
                    )
                )

                pdf.drawImage(
                    logo,
                    40,
                    alto - 95,
                    width=80,
                    height=55,
                    preserveAspectRatio=True,
                    mask="auto"
                )


        except Exception as e:

            print(
                "⚠️ Error cargando logo en portafolio:",
                str(e)
            )


        pdf.setFont(
            "Helvetica-Bold",
            20
        )

        pdf.drawString(
            140,
            alto - 55,
            "ALIANZAS PHARMA"
        )


        pdf.setFont(
            "Helvetica-Bold",
            13
        )

        pdf.drawString(
            140,
            alto - 77,
            "PORTAFOLIO DE PRODUCTOS"
        )


        pdf.setFont(
            "Helvetica",
            8
        )

        pdf.drawRightString(
            ancho - 40,
            alto - 55,
            "Actualizado:"
        )

        pdf.drawRightString(
            ancho - 40,
            alto - 68,
            fecha_actualizacion
        )


        pdf.line(
            40,
            alto - 105,
            ancho - 40,
            alto - 105
        )


    # -----------------------------------------------------
    # PIE DE PÁGINA
    # -----------------------------------------------------

    def dibujar_pie():

        pdf.line(
            40,
            48,
            ancho - 40,
            48
        )


        pdf.setFont(
            "Helvetica",
            8
        )

        pdf.drawString(
            40,
            34,
            "Consulta disponibilidad al momento de realizar tu pedido."
        )


        pdf.drawRightString(
            ancho - 40,
            34,
            "Página "
            + str(
                pdf.getPageNumber()
            )
        )


 
    # -----------------------------------------------------
    # PREPARAR IMÁGENES DEL PORTAFOLIO
    # -----------------------------------------------------

    base_url = (
        "https://alianzas-pharma-v3.vercel.app"
    )

    def preparar_url_imagen(valor):

        imagen = str(
            valor or ""
        ).strip()


        if not imagen:

            return ""


        cloud_name = os.environ.get(
            "CLOUDINARY_CLOUD_NAME",
            ""
        ).strip()


        # ---------------------------------------------
        # COMPATIBILIDAD CON IMÁGENES ANTIGUAS
        # ---------------------------------------------

        if imagen.startswith("/static/"):

            imagen = (
                "/public/"
                + imagen[len("/static/"):]
            )


        elif imagen.startswith("static/"):

            imagen = (
                "/public/"
                + imagen[len("static/"):]
            )


        # ---------------------------------------------
        # CONVERTIR RUTA LOCAL EN URL COMPLETA
        # ---------------------------------------------

        if not imagen.lower().startswith(
            ("http://", "https://")
        ):

            if not imagen.startswith("/"):

                imagen = "/" + imagen


            imagen = (
                base_url
                + imagen
            )


        # ---------------------------------------------
        # SI YA ES CLOUDINARY:
        # PEDIR VERSIÓN PEQUEÑA OPTIMIZADA
        # ---------------------------------------------

        if (
            "res.cloudinary.com/" in imagen
            and "/image/upload/" in imagen
        ):

            return imagen.replace(
                "/image/upload/",
                "/image/upload/c_limit,w_180,q_auto,f_jpg/",
                1
            )


        # ---------------------------------------------
        # IMAGEN LOCAL O EXTERNA:
        # PASARLA POR CLOUDINARY FETCH
        # ---------------------------------------------

        if cloud_name:

            imagen_codificada = quote(
                imagen,
                safe=""
            )


            return (
                "https://res.cloudinary.com/"
                + cloud_name
                + "/image/fetch/"
                + "c_limit,w_180,q_auto,f_jpg/"
                + imagen_codificada
            )


        # Si faltara Cloudinary,
        # conservar URL original
        return imagen

    def leer_imagen_local(
        ruta_web
    ):

        ruta_relativa = ruta_web.lstrip("/")

        print(
            "📁 PORTAFOLIO RUTAS:",
            "root_path=",
            app.root_path,
            "cwd=",
            os.getcwd(),
            "imagen=",
            ruta_relativa
        )


        candidatos = [

            os.path.join(
                app.root_path,
                ruta_relativa
            )

        ]


        # Compatibilidad adicional
        # entre carpetas public y static

        if ruta_relativa.startswith(
            "public/"
        ):

            candidatos.append(
                os.path.join(
                    app.root_path,
                    "static",
                    ruta_relativa[
                        len("public/"):
                    ]
                )
            )


        elif ruta_relativa.startswith(
            "static/"
        ):

            candidatos.append(
                os.path.join(
                    app.root_path,
                    "public",
                    ruta_relativa[
                        len("static/"):
                    ]
                )
            )


        for ruta_archivo in candidatos:

            try:

                if os.path.isfile(
                    ruta_archivo
                ):

                    with open(
                        ruta_archivo,
                        "rb"
                    ) as archivo:

                        return archivo.read()


            except Exception as e:

                print(
                    "⚠️ Error leyendo imagen local:",
                    str(e)
                )


        return None


    def descargar_imagen_externa(
        imagen_url
    ):

        try:

            respuesta = requests.get(
                imagen_url,
                timeout=8
            )
            


            if respuesta.ok:

                return respuesta.content


        except Exception as e:

            print(
                "⚠️ Error descargando imagen externa:",
                str(e)
            )


        return None


    # -----------------------------------------------------
    # CARGAR IMÁGENES LOCALES DIRECTAMENTE DEL DISCO
    # -----------------------------------------------------

    imagenes_portafolio = {}

    urls_externas = []


    for producto in productos:

        imagen_original = str(
            producto.get(
                "imagen",
                ""
            ) or ""
        ).strip()

        if not imagen_original:
            continue

        imagen = preparar_url_imagen(
            imagen_original
        )

        if not imagen:
            continue

        # Evitar procesar imágenes repetidas
        if imagen in imagenes_portafolio:
            continue

        # ---------------------------------------------
        # IMAGEN LOCAL DEL PROYECTO
        # Leerla directamente del disco
        # ---------------------------------------------
        if not imagen_original.lower().startswith(
            ("http://", "https://")
        ):

            nombre_imagen = (
                imagen_original
                .replace("\\", "/")
                .replace("/static/", "")
                .replace("static/", "")
                .replace("/public/", "")
                .replace("public/", "")
                .lstrip("/")
            )

            for _ in range(3):

                nombre_decodificado = unquote(
                nombre_imagen
            )

            if nombre_decodificado == nombre_imagen:
                break

            nombre_imagen = nombre_decodificado

            imagen = (
                "https://alianzas-pharma-v3.vercel.app/public/"
                + quote(
                    nombre_imagen,
                    safe="/"
                )
             )

            urls_externas.append(
                 imagen
             )
        
        else:

            urls_externas.append(
                imagen
            )

    # -----------------------------------------------------
    # DESCARGAR SOLO LAS IMÁGENES EXTERNAS EN PARALELO
    # -----------------------------------------------------

    urls_externas = list(
        dict.fromkeys(
            urls_externas
        )
    )


    if urls_externas:

        with ThreadPoolExecutor(
            max_workers=16
        ) as executor:

            resultados = executor.map(
                descargar_imagen_externa,
                urls_externas
            )


            for imagen_url, contenido in zip(
                urls_externas,
                resultados
            ):

                imagenes_portafolio[
                    imagen_url
                ] = contenido

    # -----------------------------------------------------
    # MEDIDAS DE LAS TARJETAS
    # -----------------------------------------------------

    margen_izquierdo = 40

    espacio_columnas = 14

    ancho_tarjeta = (
        (
            ancho
            - 80
            - espacio_columnas
        )
        / 2
    )

    alto_tarjeta = 125

    inicio_y = alto - 130

    columna = 0

    y = inicio_y


    # -----------------------------------------------------
    # DIBUJAR PRIMER ENCABEZADO
    # -----------------------------------------------------

    dibujar_encabezado()


    # -----------------------------------------------------
    # SI NO HAY PRODUCTOS
    # -----------------------------------------------------

    if not productos:

        pdf.setFont(
            "Helvetica",
            12
        )

        pdf.drawCentredString(
            ancho / 2,
            alto / 2,
            "No hay productos disponibles."
        )

    # -----------------------------------------------------
    # PRODUCTOS
    # -----------------------------------------------------

    for producto in productos:

        # -------------------------------------------------
        # NUEVA PÁGINA
        # -------------------------------------------------

        if (
            columna == 0
            and y - alto_tarjeta < 65
        ):

            dibujar_pie()

            pdf.showPage()

            dibujar_encabezado()

            y = inicio_y


        if columna == 0:

            x = margen_izquierdo

        else:

            x = (
                margen_izquierdo
                + ancho_tarjeta
                + espacio_columnas
            )


        # -------------------------------------------------
        # TARJETA
        # -------------------------------------------------

        pdf.setLineWidth(
            0.5
        )

        pdf.roundRect(
            x,
            y - alto_tarjeta,
            ancho_tarjeta,
            alto_tarjeta,
            8,
            stroke=1,
            fill=0
        )


        # -------------------------------------------------
        # FOTO DEL PRODUCTO
        # -------------------------------------------------

        imagen_original = str(
            producto.get(
                "imagen",
                ""
            ) or ""
        ).strip()


        imagen_url = ""


        if imagen_original:

            if not imagen_original.lower().startswith(
                ("http://", "https://")
            ):

                nombre_imagen = (
                    imagen_original
                    .replace("\\", "/")
                    .replace("/static/", "")
                    .replace("static/", "")
                    .replace("/public/", "")
                    .replace("public/", "")
                    .lstrip("/")
                )


                for _ in range(3):

                    nombre_decodificado = unquote(
                        nombre_imagen
                    )

                    if (
                        nombre_decodificado
                        == nombre_imagen
                    ):
                        break

                    nombre_imagen = (
                        nombre_decodificado
                    )


                imagen_url = (
                    "https://alianzas-pharma-v3.vercel.app/public/"
                    + quote(
                        nombre_imagen,
                        safe="/"
                    )
                )

            else:

                imagen_url = preparar_url_imagen(
                    imagen_original
                )


        contenido_imagen = (
            imagenes_portafolio.get(
                imagen_url
            )
        )


        print(
            "🔎 PDF PRODUCTO:",
            producto.get(
                "nombre",
                ""
            ),
            "| URL:",
            imagen_url,
            "| CARGADA:",
            bool(
                contenido_imagen
            )
        )


        if contenido_imagen:

            try:

                imagen_producto = ImageReader(
                    BytesIO(
                        contenido_imagen
                    )
                )

                pdf.drawImage(
                    imagen_producto,
                    x + 10,
                    y - 102,
                    width=72,
                    height=82,
                    preserveAspectRatio=True,
                    mask="auto"
                )

            except Exception as e:

                print(
                    "⚠️ Imagen no cargada en portafolio:",
                    str(e)
                )


        # -------------------------------------------------
        # NOMBRE
        # -------------------------------------------------

        nombre = str(
            producto.get(
                "nombre",
                "Producto"
            )
        ).strip()


        lineas_nombre = dividir_texto(
            nombre,
            ancho_tarjeta - 105,
            "Helvetica-Bold",
            9
        )


        texto_x = x + 92

        texto_y = y - 28


        pdf.setFont(
            "Helvetica-Bold",
            9
        )


        for linea in lineas_nombre[:4]:

            pdf.drawString(
                texto_x,
                texto_y,
                linea
            )

            texto_y -= 12


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


        precio_texto = (
            f"${precio:,.0f}"
            .replace(
                ",",
                "."
            )
        )


        pdf.setFont(
            "Helvetica-Bold",
            11
        )

        pdf.drawString(
            texto_x,
            y - 102,
            precio_texto
        )


        # -------------------------------------------------
        # SIGUIENTE TARJETA
        # -------------------------------------------------

        if columna == 0:

            columna = 1

        else:

            columna = 0

            y -= (
                alto_tarjeta
                + 14
            )
 
    # Si terminó en columna derecha,
    # bajar para cerrar correctamente
    if columna == 1:

        y -= (
            alto_tarjeta
            + 14
        )


    # -----------------------------------------------------
    # PIE FINAL
    # -----------------------------------------------------

    dibujar_pie()


    # -----------------------------------------------------
    # FINALIZAR PDF
    # -----------------------------------------------------

    pdf.save()

    buffer.seek(0)


    respuesta = make_response(
        buffer.getvalue()
    )


    respuesta.headers[
        "Content-Type"
    ] = "application/pdf"


    nombre_fecha = ahora_colombia.strftime(
        "%Y-%m-%d"
    )


    respuesta.headers[
        "Content-Disposition"
    ] = (
        'attachment; filename="'
        + "Portafolio_Alianzas_Pharma_"
        + nombre_fecha
        + '.pdf"'
    )


    return respuesta


# =========================================================
# ADMIN - BORRAR PEDIDO
# =========================================================

@app.route(
    "/eliminar-pedido/<pedido_id>",
    methods=["POST"]
)
def eliminar_pedido_admin(pedido_id):

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # BUSCAR PEDIDO
    # -----------------------------------------------------

    pedido = obtener_documento(
        "pedidos",
        pedido_id
    )


    if not pedido:

        return redirect(
            url_for("ver_pedidos_admin")
        )


    # -----------------------------------------------------
    # VERIFICAR ESTADO
    # -----------------------------------------------------

    estado = str(
        pedido.get(
            "estado",
            "Pendiente"
        )
    ).strip().lower()


    # No borrar pedidos pendientes
    if estado == "pendiente":

        return """
        <!DOCTYPE html>
        <html lang="es">

        <head>
            <meta charset="UTF-8">
            <title>Pedido no eliminado</title>
        </head>

        <body
            style="
            font-family:'Segoe UI',sans-serif;
            background:#f4f6f9;
            display:flex;
            align-items:center;
            justify-content:center;
            min-height:100vh;
            margin:0;
            "
        >

            <div
                style="
                background:white;
                padding:35px;
                border-radius:16px;
                text-align:center;
                max-width:480px;
                box-shadow:0 10px 25px rgba(0,0,0,0.08);
                "
            >

                <h2>
                    ⚠️ Pedido pendiente
                </h2>

                <p>
                    Este pedido todavía está pendiente
                    y no se puede borrar.
                </p>

                <p>
                    Primero debe ser despachado
                    o cancelado.
                </p>

                <a
                    href="/ver-pedidos"
                    style="
                    display:inline-block;
                    margin-top:15px;
                    background:#3498db;
                    color:white;
                    padding:10px 20px;
                    border-radius:8px;
                    text-decoration:none;
                    font-weight:bold;
                    "
                >
                    Volver a pedidos
                </a>

            </div>

        </body>
        </html>
        """


    # -----------------------------------------------------
    # URL DEL PEDIDO EN FIRESTORE
    # -----------------------------------------------------

    url = (
        firestore_base_url()
        + "/"
        + quote(
            "pedidos",
            safe=""
        )
        + "/"
        + quote(
            pedido_id,
            safe=""
        )
    )


    # -----------------------------------------------------
    # ELIMINAR
    # -----------------------------------------------------

    try:

        respuesta = requests.delete(
            url,
            headers=firestore_headers(),
            timeout=10
        )


        if not respuesta.ok:

            print(
                "❌ ERROR BORRANDO PEDIDO:"
            )

            print(
                respuesta.status_code
            )

            print(
                respuesta.text[:1000]
            )


            return redirect(
                url_for("ver_pedidos_admin")
            )


        print(
            "✅ PEDIDO BORRADO: "
            + pedido_id
        )


    except Exception as e:

        print(
            "❌ ERROR BORRANDO PEDIDO:"
        )

        print(
            str(e)
        )


    return redirect(
        url_for("ver_pedidos_admin")
    )

# =========================================================
# ADMIN - CONTADOR DE PEDIDOS PENDIENTES
# =========================================================

@app.route(
    "/api/conteo-pendientes"
)
def conteo_pedidos_pendientes():

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return jsonify({
            "conteo": 0,
            "pedidos": []
        }), 401


    # -----------------------------------------------------
    # OBTENER PEDIDOS
    # -----------------------------------------------------

    pedidos = obtener_coleccion(
        "pedidos"
    )


    pendientes = []


    # -----------------------------------------------------
    # CONTAR PENDIENTES
    # -----------------------------------------------------

    for pedido in pedidos:

        estado = str(
            pedido.get(
                "estado",
                ""
            )
        ).strip().lower()


        if estado == "pendiente":

            pedido_id = str(
                pedido.get(
                    "_id",
                    ""
                )
            ).strip()


            if pedido_id:

                pendientes.append(
                    pedido_id
                )


    # -----------------------------------------------------
    # RESPUESTA
    # -----------------------------------------------------

    return jsonify({

        "conteo":
            len(pendientes),

        "pedidos":
            pendientes

    })


# =========================================================
# ADMIN - VER DROGUERÍAS
# =========================================================

@app.route(
    "/ver-clientes"
)
def ver_clientes_admin():

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # OBTENER CLIENTES DE FIREBASE
    # -----------------------------------------------------

    clientes = obtener_coleccion(
        "clientes"
    )


    # -----------------------------------------------------
    # ASEGURAR NIT
    # -----------------------------------------------------

    for cliente in clientes:

        if not cliente.get("nit"):

            cliente["nit"] = cliente.get(
                "_id",
                ""
            )


    # -----------------------------------------------------
    # ORDENAR POR NOMBRE
    # -----------------------------------------------------

    clientes.sort(
        key=lambda x: str(
            x.get(
                "nombre",
                ""
            )
        ).lower()
    )


    # -----------------------------------------------------
    # MOSTRAR PÁGINA
    # -----------------------------------------------------

    return render_template(
        "clientes.html",
        clientes=clientes
    )

    # =========================================================
    # ADMIN - EDITAR DROGUERÍA
    # =========================================================

@app.route(
    "/editar-cliente/<cliente_id>",
    methods=["GET", "POST"]
)
def editar_cliente_admin(cliente_id):

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # BUSCAR CLIENTE
    # -----------------------------------------------------

    cliente = obtener_documento(
        "clientes",
        cliente_id
    )


    if not cliente:

        return """
        <h2>Droguería no encontrada</h2>

        <a href="/ver-clientes">
            Volver
        </a>
        """, 404


    # -----------------------------------------------------
    # GUARDAR CAMBIOS
    # -----------------------------------------------------

    if request.method == "POST":

        nombre = request.form.get(
            "nombre",
            ""
        ).strip()


        direccion = request.form.get(
            "direccion",
            ""
        ).strip()


        telefono = request.form.get(
            "telefono",
            ""
        ).strip()


        if (
            not nombre
            or not direccion
            or not telefono
        ):

            return """
            <h2>Faltan datos</h2>

            <a href="/ver-clientes">
                Volver
            </a>
            """, 400


        # ---------------------------------------------
        # ACTUALIZAR SOLO ESTOS DATOS
        # ---------------------------------------------

        cliente["nombre"] = nombre

        cliente["direccion"] = direccion

        cliente["telefono"] = telefono


        # Asegurar que conserve su NIT
        if not cliente.get("nit"):

            cliente["nit"] = cliente_id


        # La contraseña que ya existe en cliente
        # permanece intacta.

        guardado = guardar_documento(
            "clientes",
            cliente_id,
            cliente
        )


        if guardado:

            return redirect(
                url_for(
                    "ver_clientes_admin"
                )
            )


        return """
        <h2>Error guardando los cambios</h2>

        <a href="/ver-clientes">
            Volver
        </a>
        """, 500


    # -----------------------------------------------------
    # MOSTRAR FORMULARIO
    # -----------------------------------------------------

    cliente_vista = dict(
        cliente
    )

    cliente_vista["_id"] = (
        cliente_id
    )


    return render_template(
        "editar_cliente.html",
        cliente=cliente_vista
    )


# =========================================================
# ADMIN - ELIMINAR DROGUERÍA
# =========================================================

@app.route(
    "/eliminar-cliente/<cliente_id>",
    methods=["POST"]
)
def eliminar_cliente_admin(cliente_id):

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # BUSCAR DROGUERÍA
    # -----------------------------------------------------

    cliente = obtener_documento(
        "clientes",
        cliente_id
    )


    if not cliente:

        return redirect(
            url_for(
                "ver_clientes_admin"
            )
        )


    nit_cliente = str(
        cliente.get(
            "nit",
            cliente_id
        )
    ).strip()


    # -----------------------------------------------------
    # COMPROBAR PEDIDOS PENDIENTES
    # -----------------------------------------------------

    pedidos = obtener_coleccion(
        "pedidos"
    )


    for pedido in pedidos:

        datos_cliente = pedido.get(
            "cliente",
            {}
        )


        nit_pedido = str(
            datos_cliente.get(
                "nit",
                ""
            )
        ).strip()


        estado = str(
            pedido.get(
                "estado",
                ""
            )
        ).strip().lower()


        if (
            nit_pedido == nit_cliente
            and estado == "pendiente"
        ):

            return """
            <script>

                alert(
                    "⚠️ No se puede eliminar esta droguería porque tiene pedidos pendientes."
                );

                window.location.href =
                    "/ver-clientes";

            </script>
            """


    # -----------------------------------------------------
    # URL DEL DOCUMENTO EN FIREBASE
    # -----------------------------------------------------

    url = (
        firestore_base_url()
        + "/"
        + quote(
            "clientes",
            safe=""
        )
        + "/"
        + quote(
            cliente_id,
            safe=""
        )
    )


    # -----------------------------------------------------
    # ELIMINAR DROGUERÍA
    # -----------------------------------------------------

    respuesta = requests.delete(
        url,
        headers=firestore_headers(),
        timeout=10
    )


    if not respuesta.ok:

        print(
            "❌ Error eliminando droguería:"
        )

        print(
            respuesta.text[:1000]
        )

        return """
        <script>

            alert(
                "❌ No fue posible eliminar la droguería."
            );

            window.location.href =
                "/ver-clientes";

        </script>
        """, 500


    # -----------------------------------------------------
    # VOLVER A LA LISTA
    # -----------------------------------------------------

    return redirect(
        url_for(
            "ver_clientes_admin"
        )
    )

# =========================================================
# ADMIN - CREAR PEDIDO PARA DROGUERÍA
# =========================================================

@app.route(
    "/crear-pedido-admin"
)
def crear_pedido_admin():

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # OBTENER DROGUERÍAS
    # -----------------------------------------------------

    clientes = obtener_coleccion(
        "clientes"
    )


    for cliente in clientes:

        if not cliente.get("nit"):

            cliente["nit"] = cliente.get(
                "_id",
                ""
            )


    clientes.sort(
        key=lambda x: str(
            x.get(
                "nombre",
                ""
            )
        ).lower()
    )


    # -----------------------------------------------------
    # MOSTRAR PANTALLA
    # -----------------------------------------------------

    return render_template(
        "crear_pedido_admin.html",
        clientes=clientes
    )


# =========================================================
# ADMIN - ARMAR PEDIDO PARA DROGUERÍA
# =========================================================

@app.route(
    "/crear-pedido-admin/<cliente_id>"
)
def armar_pedido_admin(cliente_id):

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # BUSCAR DROGUERÍA
    # -----------------------------------------------------

    cliente = obtener_documento(
        "clientes",
        cliente_id
    )


    if not cliente:

        return """
        <script>

            alert(
                "No fue posible encontrar la droguería."
            );

            window.location.href =
                "/crear-pedido-admin";

        </script>
        """, 404


    cliente["_id"] = cliente_id


    if not cliente.get("nit"):

        cliente["nit"] = cliente_id


    # -----------------------------------------------------
    # CARGAR PRODUCTOS
    # -----------------------------------------------------

    productos = obtener_productos()


    # -----------------------------------------------------
    # MOSTRAR CATÁLOGO PARA EL PEDIDO
    # -----------------------------------------------------

    return render_template(
        "crear_pedido_admin_productos.html",
        cliente=cliente,
        productos=productos
    )

# =========================================================
# ADMIN - GUARDAR PEDIDO PARA DROGUERÍA
# =========================================================

@app.route(
    "/guardar-pedido-admin/<cliente_id>",
    methods=["POST"]
)
def guardar_pedido_admin(cliente_id):

    try:

        # -------------------------------------------------
        # VERIFICAR ADMINISTRADOR
        # -------------------------------------------------

        if not verificar_sesion_admin():

            return jsonify({
                "status": "error",
                "message": "La sesión de administrador no es válida."
            }), 401


        # -------------------------------------------------
        # BUSCAR DROGUERÍA
        # -------------------------------------------------

        cliente = obtener_documento(
            "clientes",
            cliente_id
        )


        if not cliente:

            return jsonify({
                "status": "error",
                "message": "No fue posible encontrar la droguería."
            }), 404


        # -------------------------------------------------
        # RECIBIR DATOS
        # -------------------------------------------------

        datos = request.get_json(
            silent=True
        ) or {}


        articulos = datos.get(
            "articulos",
            []
        )


        fecha_entrega = str(
            datos.get(
                "fecha_entrega",
                ""
            )
        ).strip()


        observaciones = str(
            datos.get(
                "observaciones",
                ""
            )
        ).strip()


        if not articulos:

            return jsonify({
                "status": "error",
                "message": "Debe seleccionar al menos un producto."
            }), 400


        # -------------------------------------------------
        # VALIDAR PRODUCTOS
        # -------------------------------------------------

        productos_validos = []

        articulos_guardados = []

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


            if (
                not producto_id
                or cantidad <= 0
            ):

                return jsonify({
                    "status": "error",
                    "message": "Producto o cantidad inválida."
                }), 400


            producto = obtener_documento(
                "productos",
                producto_id
            )


            if not producto:

                return jsonify({
                    "status": "error",
                    "message": "Uno de los productos ya no existe."
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
                    "status": "error",
                    "message":
                        "Inventario insuficiente para: "
                        + str(
                            producto.get(
                                "nombre",
                                "Producto"
                            )
                        )
                }), 400


            try:

                precio = int(
                    producto.get(
                        "precio",
                        0
                    )
                )

            except:

                precio = 0


            total += (
                precio * cantidad
            )


            productos_validos.append({

                "id":
                    producto_id,

                "producto":
                    producto,

                "cantidad":
                    cantidad

            })


            articulos_guardados.append({

                "id":
                    producto_id,

                "nombre":
                    producto.get(
                        "nombre",
                        ""
                    ),

                "precio":
                    precio,

                "cantidad":
                    cantidad

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
                - cantidad
            )


            guardado = guardar_documento(
                "productos",
                producto_id,
                producto
            )


            if not guardado:

                for anterior in productos_descontados:

                    producto_anterior = anterior[
                        "producto"
                    ]

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
                    "status": "error",
                    "message":
                        "No fue posible actualizar el inventario."
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
        # DATOS DE LA DROGUERÍA
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
                    cliente_id
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
        # CREAR ID
        # -------------------------------------------------

        pedido_id = (
            "PED-"
            + uuid.uuid4()
            .hex[:12]
            .upper()
        )


        # -------------------------------------------------
        # CREAR PEDIDO
        # -------------------------------------------------

        pedido = {

            "cliente":
                datos_cliente,

            "articulos":
                articulos_guardados,

            "total":
                total,

            "estado":
                "Pendiente",

            "fecha":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "fecha_entrega":
                fecha_entrega,

            "observaciones":
                observaciones,

            "creado_por":
                "administrador"

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

            # ---------------------------------------------
            # RESTAURAR INVENTARIO
            # ---------------------------------------------

            for anterior in productos_descontados:

                producto_anterior = anterior[
                    "producto"
                ]

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
                "status": "error",
                "message":
                    "No fue posible guardar el pedido. "
                    "El inventario fue restaurado."
            }), 500


        # -------------------------------------------------
        # ÉXITO
        # -------------------------------------------------

        return jsonify({

            "status":
                "ok",

            "message":
                "Pedido creado correctamente.",

            "pedido_id":
                pedido_id,

            "total":
                total

        })


    except Exception as e:

        print(
            "❌ ERROR CREANDO PEDIDO DESDE ADMIN:",
            str(e)
        )


        return jsonify({

            "status":
                "error",

            "message":
                "Error procesando el pedido: "
                + str(e)

        }), 500


# =========================================================
# ADMIN - CANCELAR PEDIDO Y RESTAURAR INVENTARIO
# =========================================================

@app.route(
    "/cancelar-pedido-admin/<pedido_id>",
    methods=["POST"]
)
def cancelar_pedido_admin(pedido_id):

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # BUSCAR PEDIDO
    # -----------------------------------------------------

    pedido = obtener_documento(
        "pedidos",
        pedido_id
    )


    if not pedido:

        return """
        <script>
            alert("❌ El pedido no existe.");
            window.location.href = "/ver-pedidos";
        </script>
        """, 404


    # -----------------------------------------------------
    # SOLO SE PUEDE CANCELAR SI ESTÁ PENDIENTE
    # -----------------------------------------------------

    estado = str(
        pedido.get(
            "estado",
            ""
        )
    ).strip().lower()


    if estado != "pendiente":

        return """
        <script>
            alert("⚠️ Solo se pueden cancelar pedidos pendientes.");
            window.location.href = "/ver-pedidos";
        </script>
        """


    # -----------------------------------------------------
    # OBTENER ARTÍCULOS
    # -----------------------------------------------------

    articulos = pedido.get(
        "articulos",
        []
    )


    if not articulos:

        return """
        <script>
            alert("❌ El pedido no contiene productos.");
            window.location.href = "/ver-pedidos";
        </script>
        """, 400


    # -----------------------------------------------------
    # PREPARAR PRODUCTOS PARA RESTAURAR
    # -----------------------------------------------------

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


        if (
            not producto_id
            or cantidad <= 0
        ):

            return """
            <script>
                alert("❌ El pedido contiene datos de productos inválidos.");
                window.location.href = "/ver-pedidos";
            </script>
            """, 400


        producto = obtener_documento(
            "productos",
            producto_id
        )


        if not producto:

            return """
            <script>
                alert("❌ No se encontró uno de los productos para restaurar el inventario.");
                window.location.href = "/ver-pedidos";
            </script>
            """, 500


        try:

            existencias_antes = int(
                producto.get(
                    "existencias",
                    0
                )
            )

        except:

            existencias_antes = 0


        productos_a_restaurar.append({

            "id":
                producto_id,

            "producto":
                producto,

            "cantidad":
                cantidad,

            "existencias_antes":
                existencias_antes

        })


    # -----------------------------------------------------
    # RESTAURAR INVENTARIO
    # -----------------------------------------------------

    productos_actualizados = []


    for item in productos_a_restaurar:

        producto = item[
            "producto"
        ]

        existencias_antes = item[
            "existencias_antes"
        ]

        cantidad = item[
            "cantidad"
        ]


        producto[
            "existencias"
        ] = (
            existencias_antes
            + cantidad
        )


        guardado = guardar_documento(
            "productos",
            item["id"],
            producto
        )


        if not guardado:

            # ---------------------------------------------
            # REVERTIR PRODUCTOS YA ACTUALIZADOS
            # ---------------------------------------------

            for anterior in productos_actualizados:

                producto_anterior = anterior[
                    "producto"
                ]

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


            return """
            <script>
                alert("❌ No fue posible restaurar todo el inventario. El pedido continúa pendiente.");
                window.location.href = "/ver-pedidos";
            </script>
            """, 500


        productos_actualizados.append({

            "id":
                item["id"],

            "producto":
                producto,

            "existencias_antes":
                existencias_antes

        })


    # -----------------------------------------------------
    # CAMBIAR PEDIDO A CANCELADO
    # -----------------------------------------------------

    pedido[
        "estado"
    ] = "Cancelado"

    pedido[
        "cancelado_por"
    ] = "administrador"

    pedido[
        "fecha_cancelacion"
    ] = datetime.now(
        timezone.utc
    ).isoformat()


    guardado_pedido = guardar_documento(
        "pedidos",
        pedido_id,
        pedido
    )


    # -----------------------------------------------------
    # SI FALLA EL PEDIDO, REVERTIR INVENTARIO
    # -----------------------------------------------------

    if not guardado_pedido:

        for anterior in productos_actualizados:

            producto_anterior = anterior[
                "producto"
            ]

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


        return """
        <script>
            alert("❌ No fue posible cancelar el pedido. El inventario fue devuelto a su estado anterior.");
            window.location.href = "/ver-pedidos";
        </script>
        """, 500


    # -----------------------------------------------------
    # ÉXITO
    # -----------------------------------------------------

    return redirect(
        url_for(
            "ver_pedidos_admin"
        )
    )


# =========================================================
# ADMIN - CAMBIAR NIT DE DROGUERÍA
# =========================================================

@app.route(
    "/cambiar-nit/<cliente_id>",
    methods=["GET", "POST"]
)
def cambiar_nit_admin(cliente_id):

    # -----------------------------------------------------
    # VERIFICAR ADMINISTRADOR
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # BUSCAR CLIENTE ACTUAL
    # -----------------------------------------------------

    cliente = obtener_documento(
        "clientes",
        cliente_id
    )


    if not cliente:

        return """
        <script>
            alert("❌ La droguería no existe.");
            window.location.href = "/ver-clientes";
        </script>
        """, 404


    # -----------------------------------------------------
    # MOSTRAR FORMULARIO
    # -----------------------------------------------------

    if request.method == "GET":

        cliente_mostrar = dict(
            cliente
        )

        cliente_mostrar[
            "_id"
        ] = cliente_id

        return render_template(
            "cambiar_nit.html",
            cliente=cliente_mostrar
        )


    # -----------------------------------------------------
    # RECIBIR NUEVO NIT
    # -----------------------------------------------------

    nuevo_nit = request.form.get(
        "nuevo_nit",
        ""
    ).strip()


    confirmar_nit = request.form.get(
        "confirmar_nit",
        ""
    ).strip()


    if (
        not nuevo_nit
        or not confirmar_nit
    ):

        return render_template(
            "cambiar_nit.html",
            cliente={
                **cliente,
                "_id": cliente_id
            },
            error="Debes completar los dos campos."
        )


    if nuevo_nit != confirmar_nit:

        return render_template(
            "cambiar_nit.html",
            cliente={
                **cliente,
                "_id": cliente_id
            },
            error="Los NIT ingresados no coinciden."
        )


    nit_anterior = str(
        cliente.get(
            "nit",
            cliente_id
        )
    ).strip()


    if nuevo_nit == nit_anterior:

        return render_template(
            "cambiar_nit.html",
            cliente={
                **cliente,
                "_id": cliente_id
            },
            error="El nuevo NIT es igual al NIT actual."
        )


    # -----------------------------------------------------
    # COMPROBAR QUE EL NUEVO NIT NO EXISTA
    # -----------------------------------------------------

    cliente_existente = obtener_documento(
        "clientes",
        nuevo_nit
    )


    if cliente_existente:

        return render_template(
            "cambiar_nit.html",
            cliente={
                **cliente,
                "_id": cliente_id
            },
            error="Ya existe una droguería registrada con ese NIT."
        )


    # -----------------------------------------------------
    # CREAR DOCUMENTO CON NUEVO NIT
    # -----------------------------------------------------

    cliente_nuevo = dict(
        cliente
    )

    cliente_nuevo.pop(
        "_id",
        None
    )

    cliente_nuevo[
        "nit"
    ] = nuevo_nit


    creado = guardar_documento(
        "clientes",
        nuevo_nit,
        cliente_nuevo
    )


    if not creado:

        return render_template(
            "cambiar_nit.html",
            cliente={
                **cliente,
                "_id": cliente_id
            },
            error="No fue posible crear el nuevo NIT."
        )


    # -----------------------------------------------------
    # ACTUALIZAR NIT EN TODOS LOS PEDIDOS
    # -----------------------------------------------------

    pedidos = obtener_coleccion(
        "pedidos"
    )


    pedidos_actualizados = []


    for pedido in pedidos:

        datos_cliente = pedido.get(
            "cliente",
            {}
        )


        nit_pedido = str(
            datos_cliente.get(
                "nit",
                ""
            )
        ).strip()


        if nit_pedido != nit_anterior:

            continue


        pedido_id = pedido.get(
            "_id",
            ""
        )


        pedido_original = dict(
            pedido
        )

        pedido.pop(
            "_id",
            None
        )


        datos_cliente_nuevo = dict(
            datos_cliente
        )

        datos_cliente_nuevo[
            "nit"
        ] = nuevo_nit

        pedido[
            "cliente"
        ] = datos_cliente_nuevo


        actualizado = guardar_documento(
            "pedidos",
            pedido_id,
            pedido
        )


        if not actualizado:

            # ---------------------------------------------
            # REVERTIR PEDIDOS YA MODIFICADOS
            # ---------------------------------------------

            for anterior in pedidos_actualizados:

                pedido_revertir = dict(
                    anterior["pedido"]
                )

                pedido_revertir.pop(
                    "_id",
                    None
                )

                guardar_documento(
                    "pedidos",
                    anterior["id"],
                    pedido_revertir
                )


            # ---------------------------------------------
            # BORRAR CLIENTE NUEVO
            # ---------------------------------------------

            url_nuevo = (
                firestore_base_url()
                + "/"
                + quote(
                    "clientes",
                    safe=""
                )
                + "/"
                + quote(
                    nuevo_nit,
                    safe=""
                )
            )


            requests.delete(
                url_nuevo,
                headers=firestore_headers(),
                timeout=10
            )


            return render_template(
                "cambiar_nit.html",
                cliente={
                    **cliente,
                    "_id": cliente_id
                },
                error="No fue posible actualizar todos los pedidos. No se realizó el cambio de NIT."
            )


        pedidos_actualizados.append({
            "id":
                pedido_id,
            "pedido":
                pedido_original
        })


    # -----------------------------------------------------
    # ELIMINAR DOCUMENTO DEL NIT ANTERIOR
    # -----------------------------------------------------

    url_anterior = (
        firestore_base_url()
        + "/"
        + quote(
            "clientes",
            safe=""
        )
        + "/"
        + quote(
            cliente_id,
            safe=""
        )
    )


    respuesta = requests.delete(
        url_anterior,
        headers=firestore_headers(),
        timeout=10
    )


    if not respuesta.ok:

        return """
        <script>
            alert("⚠️ El nuevo NIT fue creado, pero no fue posible eliminar el NIT anterior. No realice más cambios y revise Firebase.");
            window.location.href = "/ver-clientes";
        </script>
        """, 500


    # -----------------------------------------------------
    # ÉXITO
    # -----------------------------------------------------

    return """
    <script>
        alert("✅ NIT actualizado correctamente. Los pedidos también fueron migrados al nuevo NIT.");
        window.location.href = "/ver-clientes";
    </script>
    """

# =========================================================
# SUBIR IMAGEN A CLOUDINARY
# =========================================================

def subir_imagen_cloudinary(archivo):

    cloud_name = os.environ.get(
        "CLOUDINARY_CLOUD_NAME",
        ""
    ).strip()

    api_key = os.environ.get(
        "CLOUDINARY_API_KEY",
        ""
    ).strip()

    api_secret = os.environ.get(
        "CLOUDINARY_API_SECRET",
        ""
    ).strip()


    # -----------------------------------------------------
    # VERIFICAR CONFIGURACIÓN
    # -----------------------------------------------------

    if (
        not cloud_name
        or not api_key
        or not api_secret
    ):

        return (
            None,
            "Cloudinary no está configurado correctamente."
        )


    if (
        not archivo
        or not archivo.filename
    ):

        return (
            None,
            "No se seleccionó ninguna imagen."
        )


    # -----------------------------------------------------
    # VALIDAR TIPO DE ARCHIVO
    # -----------------------------------------------------

    tipos_permitidos = [
        "image/jpeg",
        "image/png",
        "image/webp"
    ]


    if archivo.mimetype not in tipos_permitidos:

        return (
            None,
            "La imagen debe ser JPG, PNG o WEBP."
        )


    # -----------------------------------------------------
    # LEER ARCHIVO
    # -----------------------------------------------------

    contenido = archivo.read()


    # Máximo 3 MB

    if len(contenido) > 3 * 1024 * 1024:

        return (
            None,
            "La imagen no puede superar los 3 MB."
        )


    # -----------------------------------------------------
    # CREAR FIRMA CLOUDINARY
    # -----------------------------------------------------

    timestamp = int(
        datetime.now(
            timezone.utc
        ).timestamp()
    )


    carpeta = (
        "alianzas_pharma/banners"
    )


    public_id = (
        "banner_"
        + uuid.uuid4().hex[:12]
    )


    texto_firma = (
        "folder="
        + carpeta
        + "&public_id="
        + public_id
        + "&timestamp="
        + str(timestamp)
        + api_secret
    )


    firma = hashlib.sha1(
        texto_firma.encode(
            "utf-8"
        )
    ).hexdigest()


    # -----------------------------------------------------
    # SUBIR A CLOUDINARY
    # -----------------------------------------------------

    url = (
        "https://api.cloudinary.com/v1_1/"
        + cloud_name
        + "/image/upload"
    )


    try:

        respuesta = requests.post(

            url,

            data={
                "api_key":
                    api_key,

                "timestamp":
                    timestamp,

                "signature":
                    firma,

                "folder":
                    carpeta,

                "public_id":
                    public_id
            },

            files={
                "file": (
                    archivo.filename,
                    contenido,
                    archivo.mimetype
                )
            },

            timeout=30

        )


        if not respuesta.ok:

            print(
                "❌ ERROR CLOUDINARY:",
                respuesta.status_code,
                respuesta.text
            )

            return (
                None,
                "No fue posible subir la imagen."
            )


        datos = respuesta.json()


        imagen_url = datos.get(
            "secure_url",
            ""
        )


        if not imagen_url:

            return (
                None,
                "Cloudinary no devolvió la URL de la imagen."
            )


        return (
            imagen_url,
            None
        )


    except Exception as e:

        print(
            "❌ ERROR SUBIENDO IMAGEN A CLOUDINARY:",
            e
        )

        return (
            None,
            "Ocurrió un error al subir la imagen."
        )



# =========================================================
# ADMIN - GESTIONAR BANNER PRINCIPAL
# =========================================================

@app.route(
    "/admin/banner",
    methods=["GET", "POST"]
)
def gestionar_banner():

    # -----------------------------------------------------
    # VERIFICAR SESIÓN ADMIN
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )

    # -----------------------------------------------------
    # PRODUCTOS DISPONIBLES PARA RELACIONAR PROMOCIÓN
    # -----------------------------------------------------

    lista_productos = obtener_productos()

    # -----------------------------------------------------
    # IDENTIFICAR PROMOCIÓN 1, 2 O 3
    # -----------------------------------------------------

    if request.method == "POST":

        promo_num = request.form.get(
            "promo_num",
            "1"
        ).strip()

    else:

        promo_num = request.args.get(
            "promo",
            "1"
        ).strip()


    if promo_num not in [
        "1",
        "2",
        "3"
    ]:

        promo_num = "1"


    promo_orden = int(
        promo_num
    )


    promo_id = (
        "promocion_"
        + promo_num
    )


        # -----------------------------------------------------
    # ESTADO DE LAS 3 PROMOCIONES
    # -----------------------------------------------------

    zona_colombia = timezone(
        timedelta(
            hours=-5
        )
    )

    hoy_colombia = datetime.now(
        zona_colombia
    ).date()


    def calcular_estado_promocion(datos):

        if not datos:

            return "sin_configurar"


        if not datos.get(
            "activo",
            False
        ):

            return "desactivada"


        fecha_inicio = str(
            datos.get(
                "fecha_inicio",
                ""
            )
        ).strip()


        fecha_fin = str(
            datos.get(
                "fecha_fin",
                ""
            )
        ).strip()


        def convertir_fecha(valor):

            if not valor:

                return None


            for formato in [
                "%Y-%m-%d",
                "%d/%m/%Y"
            ]:

                try:

                    return datetime.strptime(
                        valor,
                        formato
                    ).date()

                except ValueError:

                    continue


            return None


        inicio = convertir_fecha(
            fecha_inicio
        )

        fin = convertir_fecha(
            fecha_fin
        )


        if (
            inicio
            and hoy_colombia < inicio
        ):

            return "programada"


        if (
            fin
            and hoy_colombia > fin
        ):

            return "vencida"


        return "activa"


    estados_promociones = {}


    for numero in [
        "1",
        "2",
        "3"
    ]:

        datos_promocion = obtener_documento(
            "banners",
            "promocion_" + numero
        )


        estados_promociones[
            numero
        ] = calcular_estado_promocion(
            datos_promocion
        )


    # -----------------------------------------------------
    # VALORES PREDETERMINADOS
    # -----------------------------------------------------

    banner_default = {

        "activo":
            True,

        "etiqueta":
            "✨ Novedades Alianzas Pharma",

        "titulo":
            "Nueva promoción",

        "mensaje":
            "Escribe aquí la información de esta promoción.",

        "imagen":
            "/public/logo.jpeg",

        "boton_texto":
            "Ver promoción →",

        "boton_link":
             "",

        "fecha_inicio":
            "",

        "fecha_fin":
            "",

        "orden":
            promo_orden
    }


    # -----------------------------------------------------
    # MOSTRAR FORMULARIO
    # -----------------------------------------------------

    if request.method == "GET":

        banner = obtener_documento(
            "banners",
            promo_id
        )


        # -------------------------------------------------
        # PROMOCIÓN 1:
        # SI AÚN NO EXISTE, USAR EL BANNER ANTIGUO
        # -------------------------------------------------

        if (
            not banner
            and promo_num == "1"
        ):

            banner = obtener_documento(
                "configuracion",
                "banner_principal"
            )


        if not banner:

            banner = dict(
                banner_default
            )


        banner[
            "orden"
        ] = promo_orden


        return render_template(
            "gestionar_banner.html",
            banner=banner,
            promo_num=promo_num,
            productos=lista_productos,
            estados_promociones=estados_promociones,
            exito=request.args.get(
                "exito",
                ""
            )
        )


    # -----------------------------------------------------
    # RECIBIR DATOS DEL FORMULARIO
    # -----------------------------------------------------

    fecha_inicio = request.form.get(
        "fecha_inicio",
        ""
    ).strip()


    fecha_fin = request.form.get(
        "fecha_fin",
        ""
    ).strip()

    # -----------------------------------------------------
    # VALIDAR FECHAS DE LA PROMOCIÓN
    # -----------------------------------------------------

    if (
        fecha_inicio
        and fecha_fin
    ):

        try:

            inicio_validar = datetime.strptime(
                fecha_inicio,
                "%Y-%m-%d"
            ).date()


            fin_validar = datetime.strptime(
                fecha_fin,
                "%Y-%m-%d"
            ).date()


            if fin_validar < inicio_validar:

                return render_template(
                    "gestionar_banner.html",
                    banner={
                        "activo":
                            request.form.get(
                                "activo"
                            ) == "on",

                        "etiqueta":
                            etiqueta,

                        "titulo":
                            titulo,

                        "mensaje":
                            mensaje,

                        "fecha_inicio":
                            fecha_inicio,

                        "fecha_fin":
                            fecha_fin,

                        "imagen":
                            request.form.get(
                                "imagen",
                                ""
                            ).strip(),

                        "boton_texto":
                            request.form.get(
                                "boton_texto",
                                ""
                            ).strip(),

                        "boton_link":
                            request.form.get(
                                "boton_link",
                                ""
                            ).strip(),

                        "orden":
                            promo_orden
                    },
                    promo_num=promo_num,
                    productos=lista_productos,
                    error="La fecha de finalización no puede ser anterior a la fecha de inicio."
                )


        except ValueError:

            return render_template(
                "gestionar_banner.html",
                banner={
                    "activo":
                        request.form.get(
                            "activo"
                        ) == "on",

                    "etiqueta":
                        etiqueta,

                    "titulo":
                        titulo,

                    "mensaje":
                        mensaje,

                    "fecha_inicio":
                        fecha_inicio,

                    "fecha_fin":
                        fecha_fin,

                    "imagen":
                        request.form.get(
                            "imagen",
                            ""
                        ).strip(),

                    "boton_texto":
                        request.form.get(
                            "boton_texto",
                            ""
                        ).strip(),

                    "boton_link":
                        request.form.get(
                            "boton_link",
                            ""
                        ).strip(),

                    "orden":
                        promo_orden
                },
                promo_num=promo_num,
                productos=lista_productos,
                error="Las fechas ingresadas no son válidas."
            )


    etiqueta = request.form.get(
        "etiqueta",
        ""
    ).strip()


    titulo = request.form.get(
        "titulo",
        ""
    ).strip()


    mensaje = request.form.get(
        "mensaje",
        ""
    ).strip()


    imagen = request.form.get(
        "imagen",
        ""
    ).strip()


    # -----------------------------------------------------
    # IMAGEN SUBIDA DESDE EL COMPUTADOR
    # -----------------------------------------------------

    imagen_archivo = request.files.get(
        "imagen_archivo"
    )


    if (
        imagen_archivo
        and imagen_archivo.filename
    ):

        imagen_cloudinary, error_imagen = (
            subir_imagen_cloudinary(
                imagen_archivo
            )
        )


        if error_imagen:

            return render_template(
                "gestionar_banner.html",
                banner={
                    "activo":
                        request.form.get(
                            "activo"
                        ) == "on",

                    "etiqueta":
                        etiqueta,

                    "titulo":
                        titulo,

                    "mensaje":
                        mensaje,

                    "fecha_inicio":
                      fecha_inicio,

                    "fecha_fin":
                        fecha_fin,

                    "imagen":
                        imagen,

                    "boton_texto":
                        request.form.get(
                            "boton_texto",
                            ""
                        ).strip(),

                    "boton_link":
                        request.form.get(
                            "boton_link",
                            ""
                        ).strip(),

                    "orden":
                        promo_orden
                },
                promo_num=promo_num,
                error=error_imagen
            )


        imagen = imagen_cloudinary


    boton_texto = request.form.get(
        "boton_texto",
        ""
    ).strip()


    boton_link = request.form.get(
        "boton_link",
        ""
    ).strip()


    activo = (
        request.form.get(
            "activo"
        )
        == "on"
    )


    # -----------------------------------------------------
    # VALIDACIÓN
    # -----------------------------------------------------

    if not titulo:

        return render_template(
            "gestionar_banner.html",
            banner={
                "activo":
                    activo,

                "etiqueta":
                    etiqueta,

                "titulo":
                    titulo,

                "mensaje":
                    mensaje,

                "imagen":
                    imagen,

                "boton_texto":
                    boton_texto,

                "boton_link":
                    boton_link,

                "orden":
                    promo_orden
            },
            promo_num=promo_num,
            error="El título de la promoción es obligatorio."
        )


    if not imagen:

        imagen = "/public/logo.jpeg"


    # -----------------------------------------------------
    # DATOS DE LA PROMOCIÓN
    # -----------------------------------------------------

    banner = {

        "activo":
            activo,

        "etiqueta":
            etiqueta,

        "titulo":
            titulo,

        "mensaje":
            mensaje,

        "fecha_inicio":
            fecha_inicio,

        "fecha_fin":
            fecha_fin,

        "imagen":
            imagen,

        "boton_texto":
            boton_texto,

        "boton_link":
            boton_link,

        "orden":
            promo_orden

    }


    # -----------------------------------------------------
    # GUARDAR PROMOCIÓN EN FIRESTORE
    # -----------------------------------------------------

    guardado = guardar_documento(
        "banners",
        promo_id,
        banner
    )


    if not guardado:

        return render_template(
            "gestionar_banner.html",
            banner=banner,
            promo_num=promo_num,
            error="No fue posible guardar la promoción."
        )


    # -----------------------------------------------------
    # MANTENER COMPATIBILIDAD CON EL BANNER ANTERIOR
    # SOLO PARA PROMOCIÓN 1
    # -----------------------------------------------------

    if promo_num == "1":

        banner_principal = dict(
            banner
        )

        banner_principal.pop(
            "orden",
            None
        )


        guardar_documento(
            "configuracion",
            "banner_principal",
            banner_principal
        )


    # -----------------------------------------------------
    # ÉXITO
    # -----------------------------------------------------

    return redirect(
        url_for(
            "gestionar_banner",
            promo=promo_num,
            exito="1"
        )
    )



# =========================================================
# ADMIN - SECCIÓN INSTITUCIONAL
# =========================================================

@app.route(
    "/admin/institucional",
    methods=["GET", "POST"]
)
def gestionar_institucional():

    # -----------------------------------------------------
    # VERIFICAR SESIÓN ADMIN
    # -----------------------------------------------------

    if not verificar_sesion_admin():

        return redirect(
            url_for("admin_login")
        )


    # -----------------------------------------------------
    # VALORES PREDETERMINADOS
    # -----------------------------------------------------

    institucional_default = {

        "activo":
            False,

        "titulo":
            "Conoce Alianzas Pharma",

        "subtitulo":
            "Más que un proveedor, un aliado para tu droguería",

        "texto":
            "Trabajamos para brindar atención personalizada, productos de calidad y soluciones para nuestras droguerías afiliadas.",

        "foto_1":
            "",

        "foto_2":
            "",

        "foto_3":
            "",

        "foto_4":
            ""

    }


    # -----------------------------------------------------
    # MOSTRAR FORMULARIO
    # -----------------------------------------------------

    if request.method == "GET":

        institucional = obtener_documento(
            "configuracion",
            "institucional"
        )


        if not institucional:

            institucional = institucional_default


        return render_template(
            "gestionar_institucional.html",
            institucional=institucional,
            exito=request.args.get(
                "exito",
                ""
            )
        )


    # -----------------------------------------------------
    # RECIBIR DATOS
    # -----------------------------------------------------

    activo = (
        request.form.get(
            "activo"
        )
        == "on"
    )


    titulo = request.form.get(
        "titulo",
        ""
    ).strip()


    subtitulo = request.form.get(
        "subtitulo",
        ""
    ).strip()


    texto = request.form.get(
        "texto",
        ""
    ).strip()

    beneficio_1 = request.form.get(
            "beneficio_1",
            "Atención personalizada"
     ).strip()


    beneficio_2 = request.form.get(
            "beneficio_2",
            "Productos de calidad"
        ).strip()


    # -----------------------------------------------------
    # CONSERVAR FOTOS ACTUALES
    # -----------------------------------------------------

    fotos = {}


    for numero in range(
        1,
        5
    ):

        campo = (
            "foto_"
            + str(numero)
        )


        fotos[
            campo
        ] = request.form.get(
            campo,
            ""
        ).strip()


    # -----------------------------------------------------
    # SUBIR / QUITAR FOTOS
    # -----------------------------------------------------

    for numero in range(
        1,
        5
    ):

        campo = (
            "foto_"
            + str(numero)
        )


        campo_archivo = (
            campo
            + "_archivo"
        )


        campo_eliminar = (
            "eliminar_"
            + campo
        )


        archivo = request.files.get(
            campo_archivo
        )


        eliminar = (
            request.form.get(
                campo_eliminar
            )
            == "on"
        )


        # ---------------------------------------------
        # NUEVA FOTO SELECCIONADA
        # ---------------------------------------------

        if (
            archivo
            and archivo.filename
        ):

            foto_url, error_foto = (
                subir_imagen_cloudinary(
                    archivo
                )
            )


            if error_foto:

                institucional = {

                    "activo":
                        activo,

                    "titulo":
                        titulo,

                    "subtitulo":
                        subtitulo,

                    "texto":
                        texto,

                    **fotos

                }


                return render_template(
                    "gestionar_institucional.html",
                    institucional=institucional,
                    error=(
                        "Foto "
                        + str(numero)
                        + ": "
                        + error_foto
                    )
                )


            fotos[
                campo
            ] = foto_url


        # ---------------------------------------------
        # QUITAR FOTO
        # ---------------------------------------------

        elif eliminar:

            fotos[
                campo
            ] = ""


    # -----------------------------------------------------
    # VALIDAR
    # -----------------------------------------------------

    if not titulo:

        institucional = {

            "activo":
                activo,

            "titulo":
                titulo,

            "subtitulo":
                subtitulo,

            "texto":
                texto,

            **fotos

        }


        return render_template(
            "gestionar_institucional.html",
            institucional=institucional,
            error="El título de la sección es obligatorio."
        )


    # -----------------------------------------------------
    # GUARDAR EN FIRESTORE
    # -----------------------------------------------------

    institucional = {

        "activo":
            activo,

        "titulo":
            titulo,

        "subtitulo":
            subtitulo,

        "texto":
            texto,

        "beneficio_1": 
            beneficio_1,
       "beneficio_2":
            beneficio_2,

        "foto_1":
            fotos.get(
                "foto_1",
                ""
            ),

        "foto_2":
            fotos.get(
                "foto_2",
                ""
            ),

        "foto_3":
            fotos.get(
                "foto_3",
                ""
            ),

        "foto_4":
            fotos.get(
                "foto_4",
                ""
            )
            

    }


    guardado = guardar_documento(
        "configuracion",
        "institucional",
        institucional
    )


    if not guardado:

        return render_template(
            "gestionar_institucional.html",
            institucional=institucional,
            error="No fue posible guardar la sección institucional."
        )


    # -----------------------------------------------------
    # ÉXITO
    # -----------------------------------------------------

    return redirect(
        url_for(
            "gestionar_institucional",
            exito="1"
        )
    )


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
