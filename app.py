import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
import firebase_admin
from firebase_admin import credentials, firestore
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

CLAVE_ADMIN = "henry123"

# 🎯 CONFIGURACIÓN BLINDADA PARA LA NUBE DE VERCEL
base_dir = os.path.dirname(os.path.abspath(__file__))
ruta_llave = os.path.join(base_dir, "llave-firebase.json")

if os.path.exists(ruta_llave):
    cred = credentials.Certificate(ruta_llave)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("🚀 ¡Python conectado con éxito a Firebase!")
else:
    print("❌ ERROR: No se encontró llave-firebase.json")

def verificar_sesion_admin():
    return request.cookies.get('admin_sesion') == 'activa'

def obtener_cliente_logueado():
    nit_usuario = request.cookies.get('cliente_nit')
    if not nit_usuario: return None
    doc = db.collection("clientes").document(nit_usuario).get()
    return doc.to_dict() if doc.exists else None

# --- RUTAS DE CLIENTES Y DROGUERÍAS ---

@app.route('/')
def inicio():
    cliente = obtener_cliente_logueado()
    if not cliente: return redirect(url_for('login_cliente'))
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
        nit, password = request.form.get('nit').strip(), request.form.get('password').strip()
        doc = db.collection("clientes").document(nit).get()
        if doc.exists and doc.to_dict().get('password') == password:
            resp = make_response(redirect(url_for('inicio')))
            resp.set_cookie('cliente_nit', nit, max_age=60*60*24*30)
            return resp
        return """<html><head><title>Error de Ingreso</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} .btn{display:inline-block;background:#e74c3c;color:white;padding:12px 24px;border-radius:25px;text-decoration:none;font-weight:bold;font-size:1rem;margin-top:10px;box-shadow:0 4px 12px rgba(231,76,60,0.2);transition:background 0.2s;} .btn:hover{background:#c0392b;}</style></head><body><div class="box"><img src="/logo.jpeg" style="max-height:80px; margin-bottom:10px;"><h2 style="color:#e74c3c; margin:0 0 10px 0;">❌ Acceso Denegado</h2><p style="color:#64748b; font-size:0.95rem; margin:0 0 25px 0; line-height:1.4;">El NIT o la contraseña secreta ingresados no coinciden en la plataforma de Alianzas Pharma.</p><a href="/login-cliente" class="btn">Volver a Intentarlo</a></div></body></html>"""
    return render_template('login_cliente.html')

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
