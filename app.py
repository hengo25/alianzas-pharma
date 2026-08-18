import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response, send_from_directory
import firebase_admin
from firebase_admin import credentials, firestore
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
os.makedirs('static', exist_ok=True)

# --- CORRECCIÓN MÍNIMA PARA SERVIR LAS IMÁGENES EN VERCEL ---
# No cambia la estructura de la aplicación. Solo intercepta las
# peticiones /static/... y las sirve directamente desde la carpeta static.
@app.before_request
def servir_static_en_vercel():
    if request.path.startswith('/static/'):
        nombre = request.path[len('/static/'):].replace('\\', '/')
        return send_from_directory('static', nombre)
    return None

CLAVE_ADMIN = "80230881"

ruta_llave = "llave-firebase.json"
if os.path.exists(ruta_llave):
    cred = credentials.Certificate(ruta_llave)
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
        lista.append({"id": doc.id, "nombre": p.get("nombre", "Sin nombre"), "precio": int(p.get("precio", 0)), "imagen": p.get("imagen", "/static/placeholder.jpg"), "existencias": int(p.get("existencias", 0))})
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
        return """<html><head><title>Error de Ingreso</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} .btn{display:inline-block;background:#e74c3c;color:white;padding:12px 24px;border-radius:25px;text-decoration:none;font-weight:bold;font-size:1rem;margin-top:10px;box-shadow:0 4px 12px rgba(231,76,60,0.2);transition:background 0.2s;} .btn:hover{background:#c0392b;}</style></head><body><div class="box"><img src="/static/logo.jpeg" style="max-height:80px; margin-bottom:10px;"><h2 style="color:#e74c3c; margin:0 0 10px 0;">❌ Acceso Denegado</h2><p style="color:#64748b; font-size:0.95rem; margin:0 0 25px 0; line-height:1.4;">El NIT o la contraseña secreta ingresados no coinciden en la plataforma de Alianzas Pharma.</p><a href="/login-cliente" class="btn">Volver a Intentarlo</a></div></body></html>"""
    return render_template('login_cliente.html')

@app.route('/registro-cliente', methods=['GET', 'POST'])
def registro_cliente():
    if request.method == 'POST':
        nombre, nit, direccion, telefono, password = request.form.get('nombre').strip(), request.form.get('nit').strip(), request.form.get('direccion').strip(), request.form.get('telefono').strip(), request.form.get('password').strip()
        if db.collection("clientes").document(nit).get().exists:
            return "<html><body style='font-family:sans-serif;text-align:center;padding-top:50px;'><h2 style='color:#e67e22;'>⚠️ Este NIT ya existe</h2><a href='/registro-cliente'>Volver</a></body></html>"
        db.collection("clientes").document(nit).set({"nombre": nombre, "nit": nit, "direccion": direccion, "telefono": telefono, "password": password})
        return """<html><head><title>Registro Exitoso</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} .btn{display:inline-block;background:#3498db;color:white;padding:12px 24px;border-radius:25px;text-decoration:none;font-weight:bold;font-size:1rem;margin-top:10px;box-shadow:0 4px 12px rgba(52,152,219,0.2); transition:background 0.2s;} .btn:hover{background:#2980b9;}</style></head><body><div class="box"><img src="/static/logo.jpeg" style="max-height:80px; margin-bottom:10px;"><h2 style="color:#2ecc71; margin:0 0 10px 0;">🎉 ¡Registro Exitoso!</h2><p style="color:#64748b; font-size:0.95rem; margin:0 0 25px 0; line-height:1.4;">Tu drogueria ha sido ingresada correctamente en la plataforma de alianzas pharma.</p><a href="/login-cliente" class="btn">Ir a Iniciar Sesión</a></div></body></html>"""
    return render_template('registro_cliente.html')

@app.route('/recuperar-clave', methods=['GET', 'POST'])
def recuperar_clave():
    if request.method == 'POST':
        nit, telefono = request.form.get('nit').strip(), request.form.get('telefono').strip()
        doc = db.collection("clientes").document(nit).get()
        
        # 🔑 PANTALLA 1: ÉXITO - MUESTRA LA CLAVE DE FORMA PREMIUM
        if doc.exists and doc.to_dict().get('telefono') == telefono:
            clave_secreta = doc.to_dict().get('password')
            return f"""<html><head><title>Clave Recuperada</title><style>body{{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}} .box{{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;}} .btn{{display:inline-block;background:#3498db;color:white;padding:12px 24px;border-radius:25px;text-decoration:none;font-weight:bold;font-size:1rem;margin-top:15px;box-shadow:0 4px 12px rgba(52,152,219,0.2);}}</style></head><body><div class="box"><img src="/static/logo.jpeg" style="max-height:80px; margin-bottom:10px;"><h2 style="color:#2c3e50; margin:0 0 15px 0;">🔐 Clave Recuperada</h2><p style="color:#64748b; font-size:0.95rem; margin:0;">Tu contraseña secreta para ingresar es:</p><div style="background:#f1f5f9; padding:15px; border-radius:10px; font-size:1.4rem; font-weight:bold; color:#8b5cf6; margin:15px 0; border:1px dashed #cbd5e1; letter-spacing:1px;">{clave_secreta}</div><a href="/login-cliente" class="btn">Regresar al Login</a></div></body></html>"""
            
        # ❌ PANTALLA 2: ERROR - LOS DATOS NO COINCIDEN
        return """<html><head><title>Error de Validación</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:40px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} .btn{display:inline-block;background:#e74c3c;color:white;padding:12px 24px;border-radius:25px;text-decoration:none;font-weight:bold;font-size:1rem;margin-top:10px;box-shadow:0 4px 12px rgba(231,76,60,0.2);}</style></head><body><div class="box"><img src="/static/logo.jpeg" style="max-height:80px; margin-bottom:10px;"><h2 style="color:#e74c3c; margin:0 0 10px 0;">❌ Validación Fallida</h2><p style="color:#64748b; font-size:0.95rem; margin:0 0 25px 0; line-height:1.4;">El NIT o el teléfono ingresados no coinciden con ninguna droguería registrada.</p><a href="/recuperar-clave" class="btn">Intentar de Nuevo</a></div></body></html>"""
        
    # 📝 PANTALLA 3: FORMULARIO PRINCIPAL DE RECUPERACIÓN ESTILIZADO CON LOGO
    return """<html><head><title>Recuperar Clave - Alianzas Pharma</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .box{background:white;padding:35px 30px;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);text-align:center;width:320px;} input{width:90%;padding:11px;margin-bottom:12px;border:1px solid #cbd5e1;border-radius:8px;outline:none;font-size:1rem;} button{background:#e67e22;color:white;border:none;padding:12px;border-radius:8px;font-weight:bold;cursor:pointer;width:97%;font-size:1rem;box-shadow:0 4px 10px rgba(230,126,34,0.2);} button:hover{background:#d35400;} a{color:#3498db;text-decoration:none;font-weight:600;font-size:0.9rem;display:inline-block;margin-top:15px;}</style></head><body><div class="box"><img src="/static/logo.jpeg" style="max-height:80px; margin-bottom:10px;"><h2 style="color:#2c3e50; margin:0 0 5px 0; letter-spacing:0.5px;">Recuperar Clave 🔑</h2><p style="color:#64748b; font-size:0.85rem; margin-bottom:20px; font-weight:bold;">Ingresa tus datos para validar tu identidad</p><form method="POST"><input type="text" name="nit" placeholder="Escribe tu NIT" required><br><input type="text" name="telefono" placeholder="Teléfono asociado" required><br><br><button type="submit">Ver Mi Clave Secreta</button></form><a href="/login-cliente">← Volver al Portal</a></div></body></html>"""


@app.route('/logout-cliente')
def logout_cliente():
    resp = make_response(redirect(url_for('login_cliente')))
    resp.set_cookie('cliente_nit', '', expires=0)
    return resp

# --- RUTAS DEL ADMINISTRADOR ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == CLAVE_ADMIN:
            resp = make_response(redirect(url_for('administrador')))
            resp.set_cookie('admin_sesion', 'activa', max_age=60*60*24)
            return resp
        return "<html><body style='text-align:center;padding-top:50px;'><h2>❌ Contraseña Incorrecta</h2><a href='/login'>Volver</a></body></html>"
    return "<html><body style='font-family:sans-serif;background:#f4f6f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;'><div style='background:white;padding:30px;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.1);text-align:center;width:300px;'><h2>Henry Admin 🔐</h2><form method='POST'>Incorpore la clave:<br><br><input type='password' name='password' style='width:90%;padding:10px;border:1px solid #ccc;border-radius:6px;' required><br><br><button type='submit' style='background:#3498db;color:white;border:none;padding:10px 20px;border-radius:6px;font-weight:bold;cursor:pointer;width:100%;'>Entrar al Panel</button></form></div></body></html>"

@app.route('/admin', methods=['GET', 'POST'])
def administrador():
    if not verificar_sesion_admin(): 
        return redirect(url_for('login'))
        
    # Capturamos las variables del formulario antes de validar
    nombre = request.form.get('nombre')
    precio = request.form.get('precio')
    stock = request.form.get('existencias', 0)
    foto = request.files.get('foto')
    
    # Procesamos la creación de un nuevo medicamento si viene por POST
    if request.method == 'POST':
        if nombre and precio:
            # Guardamos físicamente la foto en la carpeta static al crear el producto
            if foto and foto.filename != '':
                foto.save(os.path.join('static', foto.filename))
                ruta_imagen = f"/static/{foto.filename}"
            else:
                ruta_imagen = "/static/placeholder.jpg"
                
            db.collection("productos").document().set({
                "nombre": nombre, 
                "precio": int(precio), 
                "existencias": int(stock), 
                "imagen": ruta_imagen
            })
            return redirect(url_for('administrador'))
            
    # Traemos todos los medicamentos de Google Firebase Cloud
    lista_completa = []
    for doc in db.collection("productos").stream():
        p = doc.to_dict()
        lista_completa.append({
            "id": doc.id, 
            "nombre": p.get("nombre", "Sin nombre"), 
            "precio": int(p.get("precio", 0)), 
            "imagen": p.get("imagen", "/static/placeholder.jpg"), 
            "existencias": int(p.get("existencias", 0))
        })
    lista_completa.sort(key=lambda x: x["nombre"].lower())
    
    # Entrega la lista entera ordenada para que el buscador de JavaScript sea global
    return render_template('admin.html', productos=lista_completa)


    
    # Realizamos la segmentación matemática para la porción de pantalla
    total_productos = len(lista_completa)
    total_paginas = max(1, (total_productos + productos_por_pagina - 1) // productos_por_pagina)
    
    inicio_index = (pagina_actual - 1) * productos_por_pagina
    fin_index = inicio_index + productos_por_pagina
    productos_pantalla = lista_completa[inicio_index:fin_index]
    
    # Enviamos los datos ordenados y las variables de navegación a la interfaz
    return render_template(
        'admin.html', 
        productos=productos_pantalla, 
        current_page=pagina_actual, 
        total_pages=total_paginas
    )


@app.route('/ver-clientes')
def ver_clientes():
    if not verificar_sesion_admin(): return redirect(url_for('login'))
    lista_clientes = []
    for doc in db.collection("clientes").stream():
        lista_clientes.append(doc.to_dict())
    lista_clientes.sort(key=lambda x: x.get("nombre", "").lower())
    html_clientes = ""
    for c in lista_clientes:
        nit_c = c.get("nit")
        html_clientes += f'<tr class="f-cli"><td style="padding:12px;"><b>{c.get("nombre")}</b></td><td style="padding:12px;">{nit_c}</td><td style="padding:12px;">{c.get("direccion")}</td><td style="padding:12px;">{c.get("telefono")}</td><td style="padding:12px;color:#9b59b6;font-weight:bold;">{c.get("password")}</td><td style="padding:12px;"><a href="/eliminar-cliente/{nit_c}" style="background:#fee2e2; color:#ef4444; padding:5px 10px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:0.85rem;" onclick="return confirm(\'¿Seguro de borrar?\')">Eliminar</a></td></tr>'
    return f'<html><head><title>Clientes</title><style>body{{font-family:sans-serif;background:#f4f6f9;padding:40px;}} .box{{max-width:900px;margin:0 auto;background:white;padding:25px;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.05);}} table{{width:100%;border-collapse:collapse;margin-top:15px;}} th{{background:#34495e;color:white;padding:12px;text-align:left;}}</style></head><body><div class="box"><a href="/admin" style="display:inline-block;background:#3498db;color:white;padding:10px 15px;border-radius:20px;text-decoration:none;font-weight:bold;margin-bottom:15px;">← Volver</a><h1>📋 DROGUERÍAS AFILIADAS EN FIREBASE</h1><table><thead><tr><th>Nombre Droguería</th><th>NIT</th><th>Dirección</th><th>Teléfono</th><th>Contraseña</th><th>Acción</th></tr></thead><tbody>{html_clientes if html_clientes else "<tr><td colspan='6' align='center'>No hay droguerías registradas.</td></tr>"}</tbody></table></div></body></html>'

@app.route('/eliminar-cliente/<nit>')
def eliminar_cliente(nit):
    if not verificar_sesion_admin(): return redirect(url_for('login'))
    db.collection("clientes").document(str(nit)).delete()
    return redirect(url_for('ver_clientes'))

@app.route('/actualizar-stock/<id>', methods=['POST'])
def actualizar_stock(id):
    if not verificar_sesion_admin(): 
        return redirect(url_for('login'))
    ref = db.collection("productos").document(id)
    data = ref.get().to_dict()
    if not data:
        return redirect(url_for('administrador'))
        
    # Verifica si el formulario viene de la edición en caliente
    if 'nombre' in request.form:
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        stock = request.form.get('existencias')
        foto = request.files.get('foto')
        
        update_data = {
            "nombre": nombre, 
            "precio": int(precio), 
            "existencias": int(stock)
        }
        # Si el administrador subió una foto nueva, la reemplaza
        if foto and foto.filename != '':
            foto.save(os.path.join('static', foto.filename))
            update_data["imagen"] = f"/static/{foto.filename}"
            
        ref.update(update_data)
    else:
        # Si viene de los botones rápidos de -1 y +1
        cambio = int(request.form.get('cantidad_cambio', 0))
        ref.update({"existencias": max(0, int(data.get("existencias", 0)) + cambio)})
        
    return redirect(url_for('administrador'))


@app.route('/eliminar/<id>')
def eliminar(id):
    if not verificar_sesion_admin(): return redirect(url_for('login'))
    db.collection("productos").document(id).delete()
    return redirect(url_for('administrador'))

@app.route('/eliminar-pedido/<id_ped>')
def eliminar_pedido(id_ped):
    if not verificar_sesion_admin(): return redirect(url_for('login'))
    db.collection("pedidos").document(id_ped).delete()
    return redirect(url_for('ver_pedidos'))

@app.route('/cambiar-estado/<id_ped>')
def cambiar_estado(id_ped):
    if not verificar_sesion_admin(): return redirect(url_for('login'))
    db.collection("pedidos").document(id_ped).update({"estado": "Despachado"})
    return redirect(url_for('ver_pedidos'))

@app.route('/ver-pedidos')
def ver_pedidos():
    if not verificar_sesion_admin(): return redirect(url_for('login'))
    lista_pedidos = []
    for doc in db.collection("pedidos").order_by("fecha", direction=firestore.Query.DESCENDING).stream():
        p = doc.to_dict()
        p["id"] = doc.id
        lista_pedidos.append(p)
    return render_template('pedidos.html', pedidos=lista_pedidos)

@app.route('/api/conteo-pendientes')
def conteo_pendientes():
    try:
        pedidos_ref = db.collection("pedidos").where("estado", "==", "Pendiente").stream()
        total = len(list(pedidos_ref))
        return jsonify({"status": "ok", "conteo": total})
    except Exception as e:
        return jsonify({"status": "error", "conteo": 0})

@app.route('/hacer-pedido', methods=['POST'])
def hacer_pedido():
    datos = request.get_json()
    arts = datos.get('articulos', [])
    cli = datos.get('cliente', {})
    if not arts:
        return jsonify({"status": "error"}), 400
    tot = 0
    # Validamos que haya inventario suficiente antes de vender
    for a in arts:
        ref = db.collection("productos").document(str(a['id']))
        snap = ref.get().to_dict()
        if not snap or int(snap.get("existencias", 0)) < int(a['cantidad']):
            return jsonify({"status": "error", "message": f"Agotado: {a['nombre']}"}), 400
    # Descontamos de la bodega local y sumamos al total de la factura
    for a in arts:
        ref = db.collection("productos").document(str(a['id']))
        stock_actual = int(ref.get().to_dict().get("existencias", 0))
        ref.update({"existencias": stock_actual - int(a['cantidad'])})
        tot += int(a['precio']) * int(a['cantidad'])
    # Guardamos el pedido en la colección central de Firebase
    db.collection("pedidos").document().set({
        "cliente": cli, 
        "articulos": arts, 
        "total": tot, 
        "estado": "Pendiente", 
        "fecha": firestore.SERVER_TIMESTAMP
    })
    return jsonify({"status": "ok", "message": "Pedido guardado"})

@app.route('/descargar-pdf/<id_ped>')
def descargar_pdf(id_ped):
    if not verificar_sesion_admin(): 
        return redirect(url_for('login'))
    doc_snap = db.collection("pedidos").document(id_ped).get()
    if not doc_snap.exists: 
        return "No encontrado", 404
        
    ped = doc_snap.to_dict()
    cli = ped.get("cliente", {})
    articulos = ped.get("articulos", [])
    pdf_path = f"static/factura_{id_ped}.pdf"
    
    # Fabricación del lienzo PDF estándar letter
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, 730, "ALIANZAS PHARMA ⚕️")
    c.setFont("Helvetica", 10)
    c.drawString(50, 715, "Distribuidora Mayorista y Logistica Farmaceutica")
    c.drawString(50, 675, f"ID COMPROBANTE: {id_ped}")
    c.drawString(50, 655, f"ESTADO ACTUAL: {ped.get('estado', 'Pendiente').upper()}")
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 620, "DATOS DE DESPACHO:")
    c.setFont("Helvetica", 11)
    c.drawString(50, 600, f"Destinatario: {cli.get('nombre')}")
    c.drawString(50, 580, f"Telefono:     {cli.get('telefono')}")
    c.drawString(50, 560, f"Direccion:    {cli.get('direccion')}")
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 515, "DETALLE DE PRODUCTOS SOLICITADOS:")
    c.setFont("Helvetica", 11)
    
    y = 490
    for art in articulos:
        sub = int(art['precio']) * int(art['cantidad'])
        c.drawString(60, y, f"- {art['nombre']} (Cant: {art['cantidad']}) Subtotal: ${sub}")
        y -= 20
        if y < 80: # Salto de página de seguridad si el pedido es gigantesco
            c.showPage()
            c.setFont("Helvetica", 11)
            y = 700
            
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y-30, f"TOTAL DE LA ORDEN: ${ped.get('total', 0)}")
    c.save()
    
    # Despacho del archivo binario directo al navegador del cliente
    response = make_response(open(pdf_path, 'rb').read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Factura_{cli.get("nombre", "Henry")}_{id_ped[:6]}.pdf'
    return response



if __name__ == '__main__':
    app.run(debug=True, port=5000)
