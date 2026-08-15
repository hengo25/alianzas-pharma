import os
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
CORS(app) 
main = app

CLAVE_ADMIN = "henry123"

# 🎯 ENLACE INDESTRUCTIBLE VERCEL: Conexión nativa por variable de entorno sin colisiones de archivos
config_firebase_env = os.environ.get("FIREBASE_CREDENTIALS")

if config_firebase_env:
    try:
        credenciales_directas = json.loads(config_firebase_env)
        if not firebase_admin._apps:
            # Limpieza matemática automática incorporada de saltos de línea de la llave
            if "private_key" in credenciales_directas:
                credenciales_directas["private_key"] = credenciales_directas["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(credenciales_directas)
            firebase_admin.initialize_app(cred)
        print("🚀 ¡Conexión Nativa Establecida con Firebase Cloud con Éxito!")
    except Exception as e:
        print(f"❌ Error al procesar JSON de Firebase: {e}")
else:
    # Plan B automático integrado para entorno local de desarrollo
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ruta_llave = os.path.join(base_dir, "llave-firebase.json")
        if os.path.exists(ruta_llave) and not firebase_admin._apps:
            cred = credentials.Certificate(ruta_llave)
            firebase_admin.initialize_app(cred)
            print("🚀 ¡Conexión Establecida por Archivo Físico Local!")
    except Exception as e:
        print(f"⚠️ Alerta en inicio local: {e}")

db = firestore.client()

def verificar_sesion_admin():
    return request.cookies.get('admin_sesion') == 'activa'

def obtener_cliente_logueado():
    nit_usuario = request.cookies.get('cliente_nit')
    if not nit_usuario: 
        return None
    try:
        doc = db.collection("clientes").document(nit_usuario).get()
        return doc.to_dict() if doc.exists else None
    except:
        return None

# --- RUTAS DE CLIENTES Y DROGUERÍAS ---

# 🏠 CARRIL 1: Puerta Principal (Solo muestra la pantalla limpia o el catálogo si ya entró)
@app.route('/')
def inicio():
    cliente = obtener_cliente_logueado()
    
    # 🎯 ANTI-BUCLE VERCEL: Si no hay sesión, pinta el formulario directo sin hacer redirecciones de red
    if not cliente:
        return """<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Ingreso - Alianzas Pharma</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} input{width:92%;padding:12px;margin-bottom:12px;border:1px solid #cbd5e1;border-radius:8px;outline:none;font-size:1rem;} .btn{background:#3498db;color:white;border:none;padding:12px;border-radius:25px;font-weight:bold;cursor:pointer;width:100%;font-size:1rem;margin-top:10px;box-shadow:0 4px 12px rgba(52,152,219,0.2);} .btn:hover{background:#2980b9;}</style></head><body><div class="box"><h2 style="color:#2c3e50; margin:0 0 5px 0; font-size:1.4rem;">ALIANZAS PHARMA</h2><p style="color:#64748b; font-size:0.85rem; margin-bottom:25px; font-weight:bold;">Portal de Pedidos para Droguerías Afiliadas</p><form method="POST" action="/ingresar-portal"><input type="text" name="nit" placeholder="Escribe el NIT de la Droguería" required><input type="password" name="password" placeholder="Contraseña secreta" required><button type="submit" class="btn">Iniciar Sesión</button></form><div style="display:flex; justify-content:space-between; margin-top:25px;"><a href="/registro-cliente" style="color:#3498db; text-decoration:none; font-size:0.85rem; font-weight:600;">Crear Cuenta</a><a href="/recuperar-clave" style="color:#e67e22; text-decoration:none; font-size:0.85rem; font-weight:600;">Olvidé mi clave</a></div></div></body></html>"""

    # 🛡️ BLINDAJE DE BODEGA: Carga tu inventario real sin dejar caer el hosting si está vacío
    lista = []
    try:
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
        print(f"⚠️ Alerta de inventario: Colección de productos vacía o inaccesible ({e})")
        lista = [{"id": "0", "nombre": "Kit Inicial de Prueba Pharma", "precio": 150000, "imagen": "/public/placeholder.jpg", "existencias": 10}]

    return render_template('index.html', productos=lista, cliente=cliente)

# 🚀 CARRIL 2: Validador de Firebase (Ruta exclusiva de procesamiento de contraseñas)
# 🚀 CARRIL EXCLUSIVO: Validador de Firebase para internet (Destruye la carga infinita)
@app.route('/ingresar-portal', methods=['POST'])
def ingresar_portal():
    nit = request.form.get('nit', '').strip()
    password = request.form.get('password', '').strip()
    
    try:
        doc = db.collection("clientes").document(nit).get()
        if doc.exists and doc.to_dict().get('password') == password:
            # Redirección limpia al catálogo con cookies habilitadas para HTTPS
            resp = make_response(redirect(url_for('inicio')))
            resp.headers['Set-Cookie'] = f"cliente_nit={nit}; Path=/; HttpOnly; Secure; SameSite=None"
            return resp
    except Exception as e:
        print(f"Error login: {e}")
        
    return """<html><head><title>Error</title><style>body{font-family:sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px;border-radius:16px;text-align:center;box-shadow:0 10px 25px rgba(0,0,0,0.05);}</style></head><body><div class="box"><h2>❌ Datos Incorrectos</h2><p>El NIT o la contraseña secreta no coinciden en Alianzas Pharma.</p><a href="/" style="background:#3498db;color:white;padding:10px 20px;border-radius:20px;text-decoration:none;font-weight:bold;display:inline-block;margin-top:15px;">Intentar de Nuevo</a></div></body></html>"""

@app.route('/mis-pedidos')
def mis_pedidos():
    cliente = obtener_cliente_logueado()
    if not cliente: return redirect(url_for('inicio'))
    lista_mis_pedidos = []
    try:
        pedidos_ref = db.collection("pedidos").where("cliente.nit", "==", cliente["nit"]).stream()
        for doc in pedidos_ref:
            p = doc.to_dict()
            p["id"] = doc.id
            lista_mis_pedidos.append(p)
    except Exception as e:
        print(f"Error pedidos: {e}")
    return render_template('mis_pedidos.html', pedidos=lista_mis_pedidos, cliente=cliente)

@app.route('/eliminar-mi-pedido/<id_ped>')
def eliminar_mi_pedido(id_ped):
    cliente = obtener_cliente_logueado()
    if not cliente: return redirect(url_for('inicio'))
    doc_ref = db.collection("pedidos").document(id_ped)
    doc_snap = doc_ref.get()
    if doc_snap.exists:
        ped = doc_snap.to_dict()
        if ped.get("cliente", {}).get("nit") == cliente["nit"] and ped.get("estado") == "Pendiente":
            doc_ref.delete()
    return redirect(url_for('mis_pedidos'))
