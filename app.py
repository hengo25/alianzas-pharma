import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
from flask_cors import CORS  # 🔌 NUEVO: Controlador de tráfico seguro para internet

import firebase_admin
from firebase_admin import credentials, firestore
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
CORS(app) 


CLAVE_ADMIN = "henry123"

# 🎯 CONFIGURACIÓN BLINDADA PARA LA NUBE DE VERCEL
import json

# 🎯 ENLACE GLOBAL SEGURO: Lee la llave directo de las variables de entorno de Vercel
config_firebase_env = os.environ.get("FIREBASE_CREDENTIALS")

if config_firebase_env:
    try:
        # Cargamos el texto limpio como un diccionario real de Python
        credenciales_directas = json.loads(config_firebase_env)
        if not firebase_admin._apps:
            cred = credentials.Certificate(credenciales_directas)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("🚀 ¡Conexión por Variable de Entorno Establecida con éxito!")
    except Exception as e:
        print(f"❌ Error al procesar JSON de Firebase: {e}")
else:
    print("⚠️ No se encontró la variable FIREBASE_CREDENTIALS, usando modo local...")

# 🎯 LIMPIEZA MATEMÁTICA: Repara los saltos de línea de la llave para que internet conecte en un milisegundo
if not firebase_admin._apps:
    raw_key = credenciales_directas.get("private_key", "")
    # Reemplaza los enters sueltos de texto por el formato real de Google
    credenciales_directas["private_key"] = raw_key.replace("\\n", "\n")
    
    cred = credentials.Certificate(credenciales_directas)
    firebase_admin.initialize_app(cred)

db = firestore.client()
print("🚀 ¡Conexión Nativa Indestructible Establecida con Firebase Cloud!")




def verificar_sesion_admin():
    return request.cookies.get('admin_sesion') == 'activa'

def obtener_cliente_logueado():
    nit_usuario = request.cookies.get('cliente_nit')
    if not nit_usuario: 
        return None
    doc = db.collection("clientes").document(nit_usuario).get()
    return doc.to_dict() if doc.exists else None


# --- RUTAS DE CLIENTES Y DROGUERÍAS ---

@app.route('/')
def inicio():
    cliente = obtener_cliente_logueado()
    # 🎯 ANTI-BUCLE VERCEL: Si no hay sesión, pinta el formulario directo sin hacer redirecciones de red
    if not cliente:
        return """<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Ingreso - Alianzas Pharma</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} input{width:92%;padding:12px;margin-bottom:12px;border:1px solid #cbd5e1;border-radius:8px;outline:none;font-size:1rem;} .btn{background:#3498db;color:white;border:none;padding:12px;border-radius:25px;font-weight:bold;cursor:pointer;width:100%;font-size:1rem;margin-top:10px;box-shadow:0 4px 12px rgba(52,152,219,0.2);} .btn:hover{background:#2980b9;}</style></head><body><div class="box"><img src="https://vercel.com" style="max-height:45px; margin-bottom:15px;"><h2 style="color:#2c3e50; margin:0 0 5px 0; font-size:1.4rem;">ALIANZAS PHARMA</h2><p style="color:#64748b; font-size:0.85rem; margin-bottom:25px; font-weight:bold;">Portal de Pedidos para Droguerías Afiliadas</p><form method="POST" action="/login-cliente"><input type="text" name="nit" placeholder="Escribe el NIT de la Droguería" required><input type="password" name="password" placeholder="Contraseña secreta" required><button type="submit" class="btn">Iniciar Sesión</button></form><div style="display:flex; justify-content:space-between; margin-top:25px;"><a href="/registro-cliente" style="color:#3498db; text-decoration:none; font-size:0.85rem; font-weight:600;">Crear Cuenta</a><a href="/recuperar-clave" style="color:#e67e22; text-decoration:none; font-size:0.85rem; font-weight:600;">Olvidé mi clave</a></div></div></body></html>"""

    lista = []
    for doc in db.collection("productos").stream():
        p = doc.to_dict()
        lista.append({"id": doc.id, "nombre": p.get("nombre", "Sin nombre"), "precio": int(p.get("precio", 0)), "imagen": p.get("imagen", "/public/placeholder.jpg"), "existencias": int(p.get("existencias", 0))})
    lista.sort(key=lambda x: x["nombre"].lower())
    return render_template('index.html', productos=lista, cliente=cliente)

@app.route('/mis-pedidos')
def mis_pedidos():
    cliente = obtener_cliente_logueado()
    if not cliente: return redirect(url_for('login_cliente'))
    lista_mis_pedidos = []
    pedidos_ref = db.collection("pedidos").where("cliente.nit", "==", cliente["nit"]).stream()
    for doc in pedidos_ref:
        p = doc.to_dict()
        p["id"] = doc.id
        lista_mis_pedidos.append(p)
    return render_template('mis_pedidos.html', pedidos=lista_mis_pedidos, cliente=cliente)

@app.route('/eliminar-mi-pedido/<id_ped>')
def eliminar_mi_pedido(id_ped):
    cliente = obtener_cliente_logueado()
    if not cliente: return redirect(url_for('login_cliente'))
    doc_ref = db.collection("pedidos").document(id_ped)
    doc_snap = doc_ref.get()
    if doc_snap.exists:
        ped = doc_snap.to_dict()
        if ped.get("cliente", {}).get("nit") == cliente["nit"] and ped.get("estado") == "Pendiente":
            articulos = ped.get("articulos", [])
            for art in articulos:
                prod_id = str(art.get("id"))
                cant_cancelada = int(art.get("cantidad", 0))
                prod_ref = db.collection("productos").document(prod_id)
                prod_snap = prod_ref.get().to_dict()
                if prod_snap:
                    stock_actual = int(prod_snap.get("existencias", 0))
                    prod_ref.update({"existencias": stock_actual + cant_cancelada})
            doc_ref.delete()
            return redirect(url_for('mis_pedidos'))
    return "<html><body><script>alert('No puedes eliminar un pedido despachado.'); window.location.href='/mis-pedidos';</script></body></html>"

@app.route('/limpiar-mi-historial/<id_ped>')
def limpiar_mi_historial(id_ped):
    cliente = obtener_cliente_logueado()
    if not cliente: return redirect(url_for('login_cliente'))
    doc_ref = db.collection("pedidos").document(id_ped)
    doc_snap = doc_ref.get()
    if doc_snap.exists:
        ped = doc_snap.to_dict()
        if ped.get("cliente", {}).get("nit") == cliente["nit"] and ped.get("estado") == "Despachado":
            doc_ref.delete()
            return redirect(url_for('mis_pedidos'))
    return redirect(url_for('mis_pedidos'))

@app.route('/login-cliente', methods=['GET', 'POST'])
def login_cliente():
    if request.method == 'POST':
        nit = request.form.get('nit').strip()
        password = request.form.get('password').strip()
        doc = db.collection("clientes").document(nit).get()
        
        if doc.exists and doc.to_dict().get('password') == password:
            resp = make_response(redirect(url_for('inicio')))
            resp.headers['Set-Cookie'] = f"cliente_nit={nit}; Path=/; HttpOnly; Secure; SameSite=None"
            return resp
            
        return """<html><head><title>Error</title><style>body{font-family:sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px;border-radius:16px;text-align:center;box-shadow:0 10px 25px rgba(0,0,0,0.05);}</style></head><body><div class="box"><h2>❌ Datos Incorrectos</h2><p>El NIT o contraseña no coinciden.</p><a href="/login-cliente" style="background:#3498db;color:white;padding:10px 20px;border-radius:20px;text-decoration:none;font-weight:bold;">Intentar de Nuevo</a></div></body></html>"""
            
    # 🎯 PARCHE MAESTRO: HTML nativo directo desde Python para internet sin depender de carpetas
    return """<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Ingreso - Alianzas Pharma</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} input{width:92%;padding:12px;margin-bottom:12px;border:1px solid #cbd5e1;border-radius:8px;outline:none;font-size:1rem;} .btn{background:#3498db;color:white;border:none;padding:12px;border-radius:25px;font-weight:bold;cursor:pointer;width:100%;font-size:1rem;margin-top:10px;box-shadow:0 4px 12px rgba(52,152,219,0.2);} .btn:hover{background:#2980b9;}</style></head><body><div class="box"><img src="https://vercel.com" style="max-height:45px; margin-bottom:15px;"><h2 style="color:#2c3e50; margin:0 0 5px 0; font-size:1.4rem;">ALIANZAS PHARMA</h2><p style="color:#64748b; font-size:0.85rem; margin-bottom:25px; font-weight:bold;">Portal de Pedidos para Droguerías Afiliadas</p><form method="POST" action="/login-cliente"><input type="text" name="nit" placeholder="Escribe el NIT de la Droguería" required><input type="password" name="password" placeholder="Contraseña secreta" required><button type="submit" class="btn">Iniciar Sesión</button></form><div style="display:flex; justify-content:space-between; margin-top:25px;"><a href="/registro-cliente" style="color:#3498db; text-decoration:none; font-size:0.85rem; font-weight:600;">Crear Cuenta</a><a href="/recuperar-clave" style="color:#e67e22; text-decoration:none; font-size:0.85rem; font-weight:600;">Olvidé mi clave</a></div></div></body></html>"""


@app.route('/registro-cliente', methods=['GET', 'POST'])
def registro_cliente():
    if request.method == 'POST':
        nombre, nit, direccion, telefono, password = request.form.get('nombre').strip(), request.form.get('nit').strip(), request.form.get('direccion').strip(), request.form.get('telefono').strip(), request.form.get('password').strip()
        if db.collection("clientes").document(nit).get().exists:
            return "<html><body style='font-family:sans-serif;text-align:center;padding-top:50px;'><h2 style='color:#e67e22;'>⚠️ Este NIT ya existe</h2><a href='/registro-cliente'>Volver</a></body></html>"
        db.collection("clientes").document(nit).set({"nombre": nombre, "nit": nit, "direccion": direccion, "telefono": telefono, "password": password})
        return """<html><head><title>Registro Exitoso</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} .btn{display:inline-block;background:#3498db;color:white;padding:12px 24px;border-radius:25px;text-decoration:none;font-weight:bold;font-size:1rem;margin-top:10px;box-shadow:0 4px 12px rgba(52,152,219,0.2); transition:background 0.2s;} .btn:hover{background:#2980b9;}</style></head><body><div class="box"><img src="/logo.jpeg" style="max-height:80px; margin-bottom:10px;"><h2 style="color:#2ecc71; margin:0 0 10px 0;">🎉 ¡Registro Exitoso!</h2><p style="color:#64748b; font-size:0.95rem; margin:0 0 25px 0; line-height:1.4;">Tu drogueria ha sido ingresada correctamente en la plataforma de alianzas pharma.</p><a href="/login-cliente" class="btn">Ir a Iniciar Sesión</a></div></body></html>"""
    return render_template('registro_cliente.html')

@app.route('/recuperar-clave', methods=['GET', 'POST'])
def recuperar_clave():
    if request.method == 'POST':
        nit = request.form.get('nit').strip()
        telefono = request.form.get('telefono').strip()
        doc = db.collection("clientes").document(nit).get()
        
        if doc.exists and doc.to_dict().get('telefono') == telefono:
            clave_secreta = doc.to_dict().get('password')
            return f"""<html><head><title>Clave Recuperada</title><style>body{{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}} .box{{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;}} .btn{{display:inline-block;background:#3498db;color:white;padding:12px 24px;border-radius:25px;text-decoration:none;font-weight:bold;font-size:1rem;margin-top:15px;box-shadow:0 4px 12px rgba(52,152,219,0.2);}}</style></head><body><div class="box"><img src="/public/logo.jpeg" style="max-height:80px; margin-bottom:10px;"><h2 style="color:#2c3e50; margin:0 0 15px 0;">🔐 Clave Recuperada</h2><p style="color:#64748b; font-size:0.95rem; margin:0;">Tu contraseña secreta para ingresar es:</p><div style="background:#f1f5f9; padding:15px; border-radius:10px; font-size:1.4rem; font-weight:bold; color:#8b5cf6; margin:15px 0; border:1px dashed #cbd5e1; letter-spacing:1px;">{clave_secreta}</div><a href="/login-cliente" class="btn">Regresar al Login</a></div></body></html>"""
            
        return """<html><head><title>Error de Validación</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} .btn{display:inline-block;background:#e74c3c;color:white;padding:12px 24px;border-radius:25px;text-decoration:none;font-weight:bold;font-size:1rem;margin-top:10px;box-shadow:0 4px 12px rgba(231,76,60,0.2);}</style></head><body><div class="box"><img src="/public/logo.jpeg" style="max-height:80px; margin-bottom:10px;"><h2 style="color:#e74c3c; margin:0 0 10px 0;">❌ Validación Fallida</h2><p style="color:#64748b; font-size:0.95rem; margin:0 0 25px 0; line-height:1.4;">El NIT o el teléfono ingresados no coinciden con ninguna droguería registrada.</p><a href="/recuperar-clave" class="btn">Intentar de Nuevo</a></div></body></html>"""
        
    return """<html><head><title>Recuperar Clave - Alianzas Pharma</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:35px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} input{width:90%;padding:11px;margin-bottom:12px;border:1px solid #cbd5e1;border-radius:8px;outline:none;font-size:1rem;} button{background:#e67e22;color:white;border:none;padding:12px;border-radius:8px;font-weight:bold;cursor:pointer;width:97%;font-size:1rem;box-shadow:0 4px 10px rgba(230,126,34,0.2);} button:hover{background:#e67e22;} a{color:#3498db;text-decoration:none;font-weight:600;font-size:0.9rem;display:inline-block;margin-top:15px;}</style></head><body><div class="box"><img src="/public/logo.jpeg" style="max-height:80px; margin-bottom:10px;"><h2 style="color:#2c3e50; margin:0 0 5px 0; letter-spacing:0.5px;">Recuperar Clave 🔑</h2><p style="color:#64748b; font-size:0.85rem; margin-bottom:20px; font-weight:bold;">Ingresa tus datos para validar tu identidad</p><form method="POST"><input type="text" name="nit" placeholder="Escribe tu NIT" required><br><input type="text" name="telefono" placeholder="Teléfono asociado" required><br><br><button type="submit">Ver Mi Clave Secreta</button></form><a href="/login-cliente">← Volver al Portal</a></div></body></html>"""

@app.route('/logout-cliente')
def logout_cliente():
    resp = make_response(redirect(url_for('login_cliente')))
    resp.set_cookie('cliente_nit', '', expires=0)
    return resp
