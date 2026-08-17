import os
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore

# 🎯 FORZADO DE PROTOCOLO: Apaga gRPC y obliga a Firebase a usar HTTP REST puro para saltar el Firewall de Vercel
os.environ["GRPC_DNS_RESOLVER"] = "native"
os.environ["FIRESTORE_EMULATOR_HOST"] = ""

app = Flask(__name__)
CORS(app) 
main = app

db = None

try:
    # Buscamos el archivo físico real que acabas de arrastrar a GitHub
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ruta_llave = os.path.join(base_dir, "llave-firebase.json")
    
    # Si Vercel usa rutas absolutas en la nube, probamos la ruta por defecto de la tarea
    if not os.path.exists(ruta_llave):
        ruta_llave = "/var/task/llave-firebase.json"

    if os.path.exists(ruta_llave):
        with open(ruta_llave, 'r', encoding='utf-8') as f:
            datos_json = json.load(f)
            
        if "private_key" in datos_json:
            # Limpieza matemática automática de los enters de la clave de Google
            datos_json["private_key"] = datos_json["private_key"].replace("\\n", "\n")
            
        if not firebase_admin._apps:
            cred = credentials.Certificate(datos_json)
            firebase_app = firebase_admin.initialize_app(cred)
        else:
            firebase_app = firebase_admin._apps
            
        # 🔗 EL TIRO DE GRACIA: Forzamos al cliente a leer tu base de datos de producción real
        db = firestore.client(app=firebase_app, database="(default)")
        db._firestore_api_options = {"use_rest": True}
        print("🚀 ¡Conexión unificada con la base de datos activa de Firebase!")

    else:
        print("❌ Alerta: Archivo llave-firebase.json no detectado en el servidor")
except Exception as e:
    print(f"❌ Error crítico en motor Firebase: {e}")

def obtener_cliente_logueado():
    nit_usuario = request.cookies.get('cliente_nit')
    if not nit_usuario or not db: 
        return None
    try:
        doc = db.collection("clientes").document(nit_usuario).get()
        return doc.to_dict() if doc.exists else None
    except:
        return None

# --- RUTAS DE LA APLICACIÓN REAL ---

@app.route('/')
def inicio():
    cliente = obtener_cliente_logueado()
    if not cliente:
        return """<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Ingreso - Alianzas Pharma</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} input{width:92%;padding:12px;margin-bottom:12px;border:1px solid #cbd5e1;border-radius:8px;outline:none;font-size:1rem;} .btn{background:#3498db;color:white;border:none;padding:12px;border-radius:25px;font-weight:bold;cursor:pointer;width:100%;font-size:1rem;margin-top:10px;box-shadow:0 4px 12px rgba(52,152,219,0.2);} .btn:hover{background:#2980b9;}</style></head><body><div class="box"><h2 style="color:#2c3e50; margin:0 0 5px 0; font-size:1.4rem;">ALIANZAS PHARMA</h2><p style="color:#64748b; font-size:0.85rem; margin-bottom:25px; font-weight:bold;">Portal de Pedidos para Droguerías Afiliadas</p><form method="POST" action="/ingresar-portal"><input type="text" name="nit" placeholder="Escribe el NIT de la Droguería" required><input type="password" name="password" placeholder="Contraseña secreta" required><button type="submit" class="btn">Iniciar Sesión</button></form><div style="display:flex; justify-content:space-between; margin-top:25px;"><a href="/registro-cliente" style="color:#3498db; text-decoration:none; font-size:0.85rem; font-weight:600;">Crear Cuenta</a><a href="/recuperar-clave" style="color:#e67e22; text-decoration:none; font-size:0.85rem; font-weight:600;">Olvidé mi clave</a></div></div></body></html>"""

    lista = []
    if db:
        try:
            # 📁 CONSULTA REAL: Trae tu inventario comercial directo de tu Firebase
            productos_ref = db.collection("productos").stream()
            for doc in productos_ref:
                p = doc.to_dict()
                lista.append({
                    "id": doc.id, 
                    "nombre": p.get("nombre", "Medicamento sin nombre"), 
                    "precio": int(p.get("precio", 0)), 
                    "imagen": p.get("imagen", "/public/placeholder.jpg"), 
                    "existencias": int(p.get("existencias", 0))
                })
            lista.sort(key=lambda x: x["nombre"].lower())
        except Exception as e:
            print(f"⚠️ Alerta de inventario: {e}")
            lista = []

    return render_template('index.html', productos=lista, cliente=cliente)

@app.route('/ingresar-portal', methods=['POST'])
def ingresar_portal():
    nit = request.form.get('nit', '').strip()
    password = request.form.get('password', '').strip()

    # =========================================================
    # VALIDACIÓN BÁSICA
    # =========================================================

    if not nit or not password:
        return """
        <html>
        <head>
            <title>Datos incompletos</title>
            <style>
                body {
                    font-family: sans-serif;
                    background: #f4f6f9;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                }

                .box {
                    background: white;
                    padding: 40px;
                    border-radius: 16px;
                    text-align: center;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.05);
                }

                a {
                    background: #3498db;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 20px;
                    text-decoration: none;
                    font-weight: bold;
                    display: inline-block;
                    margin-top: 15px;
                }
            </style>
        </head>

        <body>
            <div class="box">
                <h2>⚠️ Datos incompletos</h2>
                <p>Debes ingresar el NIT y la contraseña.</p>
                <a href="/">Intentar de Nuevo</a>
            </div>
        </body>
        </html>
        """

    # =========================================================
    # COMPROBAR QUE FIREBASE ESTÉ CONECTADO
    # =========================================================

    if not db:
        print("❌ LOGIN: Firebase no está conectado.")

        return """
        <html>
        <head>
            <title>Error de conexión</title>
            <style>
                body {
                    font-family: sans-serif;
                    background: #f4f6f9;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                }

                .box {
                    background: white;
                    padding: 40px;
                    border-radius: 16px;
                    text-align: center;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.05);
                }

                a {
                    background: #3498db;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 20px;
                    text-decoration: none;
                    font-weight: bold;
                    display: inline-block;
                    margin-top: 15px;
                }
            </style>
        </head>

        <body>
            <div class="box">
                <h2>❌ Error de conexión</h2>
                <p>No fue posible conectar con la base de datos.</p>
                <a href="/">Intentar de Nuevo</a>
            </div>
        </body>
        </html>
        """

    # =========================================================
    # BUSCAR CLIENTE REAL EN FIREBASE
    # =========================================================

    try:
        print(f"🔎 LOGIN: buscando NIT {nit} en Firebase...")

        doc = db.collection("clientes").document(nit).get()

        # -----------------------------------------------------
        # EL NIT NO EXISTE
        # -----------------------------------------------------

        if not doc.exists:
            print(f"❌ LOGIN: el NIT {nit} no existe en Firebase.")

            return """
            <html>
            <head>
                <title>Datos incorrectos</title>
                <style>
                    body {
                        font-family: sans-serif;
                        background: #f4f6f9;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                    }

                    .box {
                        background: white;
                        padding: 40px;
                        border-radius: 16px;
                        text-align: center;
                        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
                    }

                    a {
                        background: #3498db;
                        color: white;
                        padding: 10px 20px;
                        border-radius: 20px;
                        text-decoration: none;
                        font-weight: bold;
                        display: inline-block;
                        margin-top: 15px;
                    }
                </style>
            </head>

            <body>
                <div class="box">
                    <h2>❌ NIT no registrado</h2>
                    <p>El NIT no está registrado en Alianzas Pharma.</p>
                    <a href="/">Intentar de Nuevo</a>
                </div>
            </body>
            </html>
            """

        # -----------------------------------------------------
        # OBTENER DATOS DEL CLIENTE
        # -----------------------------------------------------

        datos_cliente = doc.to_dict()

        pass_db = str(
            datos_cliente.get('password', '')
        ).strip()

        # -----------------------------------------------------
        # COMPARAR CONTRASEÑA REAL DE FIREBASE
        # -----------------------------------------------------

        if pass_db != password:

            print(
                f"❌ LOGIN: contraseña incorrecta para NIT {nit}."
            )

            return """
            <html>
            <head>
                <title>Datos incorrectos</title>
                <style>
                    body {
                        font-family: sans-serif;
                        background: #f4f6f9;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                    }

                    .box {
                        background: white;
                        padding: 40px;
                        border-radius: 16px;
                        text-align: center;
                        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
                    }

                    a {
                        background: #3498db;
                        color: white;
                        padding: 10px 20px;
                        border-radius: 20px;
                        text-decoration: none;
                        font-weight: bold;
                        display: inline-block;
                        margin-top: 15px;
                    }
                </style>
            </head>

            <body>
                <div class="box">
                    <h2>❌ Contraseña Incorrecta</h2>
                    <p>La contraseña no coincide con la registrada en Firebase.</p>
                    <a href="/">Intentar de Nuevo</a>
                </div>
            </body>
            </html>
            """

        # =====================================================
        # LOGIN CORRECTO
        # =====================================================

        print(f"✅ LOGIN CORRECTO: NIT {nit}")

        lista_productos = []

        # -----------------------------------------------------
        # CARGAR PRODUCTOS REALES DE FIREBASE
        # -----------------------------------------------------

        try:
            productos_ref = db.collection("productos").stream()

            for d in productos_ref:
                p = d.to_dict()

                lista_productos.append({
                    "id": d.id,
                    "nombre": p.get(
                        "nombre",
                        "Medicamento sin nombre"
                    ),
                    "precio": int(
                        p.get("precio", 0)
                    ),
                    "imagen": p.get(
                        "imagen",
                        "/public/placeholder.jpg"
                    ),
                    "existencias": int(
                        p.get("existencias", 0)
                    )
                })

            lista_productos.sort(
                key=lambda x: x["nombre"].lower()
            )

            print(
                f"✅ PRODUCTOS: {len(lista_productos)} productos cargados."
            )

        except Exception as e:
            print(
                f"⚠️ PRODUCTOS: no se pudieron cargar: {e}"
            )

        # =====================================================
        # MOSTRAR LA TIENDA
        # =====================================================

        resp = make_response(
            render_template(
                'index.html',
                productos=lista_productos,
                cliente=datos_cliente
            )
        )

        # Guardamos el NIT REAL del cliente
        resp.set_cookie(
            'cliente_nit',
            nit,
            path='/',
            httponly=True,
            secure=True,
            samesite='None'
        )

        return resp

    # =========================================================
    # ERROR GENERAL DE FIREBASE
    # =========================================================

    except Exception as e:

        print(
            f"❌ LOGIN FIREBASE ERROR: {e}"
        )

        return """
        <html>
        <head>
            <title>Error de Firebase</title>
            <style>
                body {
                    font-family: sans-serif;
                    background: #f4f6f9;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                }

                .box {
                    background: white;
                    padding: 40px;
                    border-radius: 16px;
                    text-align: center;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.05);
                }

                a {
                    background: #3498db;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 20px;
                    text-decoration: none;
                    font-weight: bold;
                    display: inline-block;
                    margin-top: 15px;
                }
            </style>
        </head>

        <body>
            <div class="box">
                <h2>❌ Error de conexión con Firebase</h2>
                <p>No fue posible consultar la base de datos.</p>
                <a href="/">Intentar de Nuevo</a>
            </div>
        </body>
        </html>
        """

    # 🛡️ CARRILES FLEXIBLES DE VALIDACIÓN REAL PARA FIRESTORE
    if db:
        try:
            nit_limpio = nit.strip()
            password_limpio = password.strip()
            
            # Buscamos el documento por su nombre de cabecera
            doc = db.collection("clientes").document(nit_limpio).get()
            
            if doc.exists:
                datos_cliente = doc.to_dict()
                # Convertimos la contraseña guardada en Google a texto plano y limpio de espacios
                pass_db = str(datos_cliente.get('password', '')).strip()
                nombre_db = datos_cliente.get('nombre', 'Droguería Afiliada')
                
                # Validación matemática exacta inmune a formatos de números o texto
                if pass_db == password_limpio:
                    # Traemos tu inventario comercial real directamente de tu Firebase
                    lista_productos = []
                    try:
                        productos_ref = db.collection("productos").stream()
                        for d in productos_ref:
                            p = d.to_dict()
                            lista_productos.append({
                                "id": d.id, 
                                "nombre": p.get("nombre", "Medicamento sin nombre"), 
                                "precio": int(p.get("precio", 0)), 
                                "imagen": p.get("imagen", "/public/placeholder.jpg"), 
                                "existencias": int(p.get("existencias", 0))
                            })
                        lista_productos.sort(key=lambda x: x["nombre"].lower())
                    except:
                        pass
                        
                    resp = make_response(render_template('index.html', productos=lista_productos, cliente=datos_cliente))
                    resp.set_cookie('cliente_nit', nit_limpio, path='/', httponly=True, secure=True, samesite='None')
                    return resp
        except Exception as e:
            print(f"Error login Firebase: {e}")
        
    return """<html><head><title>Error</title><style>body{font-family:sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px;border-radius:16px;text-align:center;box-shadow:0 10px 25px rgba(0,0,0,0.05);}</style></head><body><div class="box"><h2>❌ Datos Incorrectos</h2><p>El NIT o la contraseña secreta no coinciden en tu Firebase de Alianzas Pharma.</p><a href="/" style="background:#3498db;color:white;padding:10px 20px;border-radius:20px;text-decoration:none;font-weight:bold;display:inline-block;margin-top:15px;">Intentar de Nuevo</a></div></body></html>"""


@app.route('/registro-cliente', methods=['GET', 'POST'])
def registro_cliente():
    if request.method == 'POST':
        nit = request.form.get('nit', '').strip()
        nombre = request.form.get('nombre', '').strip()
        password = request.form.get('password', '').strip()
        if db:
            try:
                db.collection("clientes").document(nit).set({
                    "nit": nit, "nombre": nombre, "password": password
                })
                return redirect(url_for('inicio'))
            except: pass
    return render_template('registro_cliente.html')

@app.route('/salir')
def salir():
    resp = make_response(redirect(url_for('inicio')))
    resp.set_cookie('cliente_nit', '', expires=0, path='/')
    return resp
