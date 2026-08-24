import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'clave_secreta_para_sesiones'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

CREDENTIALS_FILE = 'credentials.txt'

def get_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'w') as f:
            f.write("misio2026,Assdas123")
    with open(CREDENTIALS_FILE, 'r') as f:
        data = f.read().strip().split(',')
        return data[0], data[1]

def set_credentials(user, pwd):
    with open(CREDENTIALS_FILE, 'w') as f:
        f.write(f"{user},{pwd}")

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio TEXT NOT NULL,
            descripcion TEXT,
            imagen TEXT NOT NULL,
            descuentos TEXT,
            video_url TEXT,
            texto_extra TEXT,
            fotos_extra TEXT,
            activo INTEGER DEFAULT 1
        )
    ''')
    
    columnas_nuevas = ['descuentos', 'video_url', 'texto_extra', 'fotos_extra', 'activo']
    for columna in columnas_nuevas:
        try:
            if columna == 'activo':
                cursor.execute('ALTER TABLE productos ADD COLUMN activo INTEGER DEFAULT 1')
            else:
                cursor.execute(f'ALTER TABLE productos ADD COLUMN {columna} TEXT')
        except sqlite3.OperationalError:
            pass
            
    # Asegura que los productos existentes tengan activo = 1 si estaban en NULL
    cursor.execute('UPDATE productos SET activo = 1 WHERE activo IS NULL')
    conn.commit()
    conn.close()

init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form.get('usuario')
        password = request.form.get('clave')
        valid_user, valid_pwd = get_credentials()
        
        if user == valid_user and password == valid_pwd:
            session['autenticado'] = True
            return redirect(url_for('catalogo'))
        else:
            error = "Usuario o contraseña incorrectos."
            
    return render_template('login.html', error=error)

@app.route('/')
def catalogo():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    es_admin = session.get('autenticado', False)
    
    # Si es admin ve todos; si es cliente solo ve los activos (activo = 1)
    if es_admin:
        cursor.execute('SELECT * FROM productos')
    else:
        cursor.execute('SELECT * FROM productos WHERE activo = 1 OR activo IS NULL')
        
    filas = cursor.fetchall()
    conn.close()
    
    productos = [dict(f) for f in filas]
    return render_template('index.html', productos=productos, es_admin=es_admin)

@app.route('/admin/ocultar/<int:id>', methods=['POST'])
def toggle_ocultar(id):
    if not session.get('autenticado'):
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Invierte el estado actual (si es 1 pasa a 0, si es 0 pasa a 1)
    cursor.execute('UPDATE productos SET activo = CASE WHEN activo = 1 THEN 0 ELSE 1 END WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('catalogo'))

@app.route('/admin/agregar', methods=['GET', 'POST'])
def agregar():
    if not session.get('autenticado'):
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        descripcion = request.form.get('descripcion')
        file = request.files.get('imagen')
        
        img_url = ""
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            img_url = f"/static/uploads/{filename}"
            
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO productos (nombre, precio, descripcion, imagen, activo) 
            VALUES (?, ?, ?, ?, 1)
        ''', (nombre, precio, descripcion, img_url))
        conn.commit()
        conn.close()
        return redirect(url_for('catalogo'))
            
    return render_template('agregar.html')

@app.route('/admin/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    if not session.get('autenticado'):
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        descripcion = request.form.get('descripcion')
        descuentos = request.form.get('descuentos')
        video_url = request.form.get('video_url')
        texto_extra = request.form.get('texto_extra')
        
        file = request.files.get('imagen')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            img_url = f"/static/uploads/{filename}"
            cursor.execute('UPDATE productos SET imagen = ? WHERE id = ?', (img_url, id))

        files_extra = request.files.getlist('fotos_extra')
        urls_extra = []
        for f in files_extra:
            if f and f.filename != '':
                fname = secure_filename(f.filename)
                fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
                f.save(fpath)
                urls_extra.append(f"/static/uploads/{fname}")
        
        if urls_extra:
            fotos_extra_str = ",".join(urls_extra)
            cursor.execute('UPDATE productos SET fotos_extra = ? WHERE id = ?', (fotos_extra_str, id))

        cursor.execute('''
            UPDATE productos 
            SET nombre = ?, precio = ?, descripcion = ?, descuentos = ?, video_url = ?, texto_extra = ?
            WHERE id = ?
        ''', (nombre, precio, descripcion, descuentos, video_url, texto_extra, id))
        
        conn.commit()
        conn.close()
        return redirect(url_for('ver_producto', id=id))

    producto = cursor.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('editar.html', producto=producto)

@app.route('/producto/<int:id>/descuentos')
def ver_descuentos(id):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    producto = cursor.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
    conn.close()

    if producto is None:
        return "Producto no encontrado", 404

    return render_template('descuentos.html', producto=producto)

@app.route('/admin/cambiar_clave', methods=['GET', 'POST'])
def cambiar_clave():
    if not session.get('autenticado'):
        return redirect(url_for('login'))
    
    mensaje = None
    if request.method == 'POST':
        nuevo_user = request.form.get('username')
        nueva_pwd = request.form.get('password')
        set_credentials(nuevo_user, nueva_pwd)
        mensaje = "¡Credenciales actualizadas correctamente!"
        
    return render_template('cambiar_clave.html', mensaje=mensaje)

@app.route('/logout')
def logout():
    session.pop('autenticado', None)
    return redirect(url_for('login'))

@app.route('/admin/eliminar/<int:id>', methods=['POST'])
def eliminar_producto(id):
    if not session.get('autenticado'):
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM productos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('catalogo'))

@app.route('/producto/<int:id>')
def ver_producto(id):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    producto = cursor.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
    conn.close()

    if producto is None:
        return "Producto no encontrado", 404

    fotos_extra_list = []
    if producto['fotos_extra']:
        fotos_extra_list = producto['fotos_extra'].split(',')

    es_admin = session.get('autenticado', False)
    return render_template('detalle.html', producto=producto, fotos_extra=fotos_extra_list, es_admin=es_admin)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)