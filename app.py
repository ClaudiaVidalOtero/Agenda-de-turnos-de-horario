import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura' # Necesario para mostrar mensajes de error (flash)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'horarios.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS ---
class Configuracion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    horas_completa = db.Column(db.Integer, default=40)
    horas_parcial = db.Column(db.Integer, default=20)
    max_horas_semanales = db.Column(db.Integer, default=48)

class Tienda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apertura = db.Column(db.String(10))
    cierre = db.Column(db.String(10))
    empleados = db.relationship('Empleado', backref='tienda_asignada', lazy=True)

class Empleado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo_jornada = db.Column(db.String(50)) 
    horas_extra = db.Column(db.Integer, default=0)
    tienda_id = db.Column(db.Integer, db.ForeignKey('tienda.id'))

with app.app_context():
    db.create_all()
    if not Configuracion.query.first():
        db.session.add(Configuracion(horas_completa=40, horas_parcial=20, max_horas_semanales=48))
        db.session.commit()

# --- RUTAS DE CONFIGURACIÓN ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/configuracion', methods=['GET', 'POST'])
def configurar():
    conf = Configuracion.query.first()
    if request.method == 'POST':
        conf.horas_completa = int(request.form['horas_completa'])
        conf.horas_parcial = int(request.form['horas_parcial'])
        conf.max_horas_semanales = int(request.form['max_horas_semanales'])
        db.session.commit()
        flash("Configuración actualizada", "success")
        return redirect(url_for('configurar'))
    return render_template('configuracion.html', conf=conf)

# --- RUTAS DE TIENDAS (Gestionar, Editar, Borrar) ---
@app.route('/tiendas', methods=['GET', 'POST'])
def gestionar_tiendas():
    if request.method == 'POST':
        nueva = Tienda(nombre=request.form['nombre'], apertura=request.form['apertura'], cierre=request.form['cierre'])
        db.session.add(nueva)
        db.session.commit()
        return redirect(url_for('gestionar_tiendas'))
    return render_template('tiendas.html', tiendas=Tienda.query.all())

@app.route('/editar_tienda/<int:id>', methods=['GET', 'POST'])
def editar_tienda(id):
    t = Tienda.query.get_or_404(id)
    if request.method == 'POST':
        t.nombre = request.form['nombre']
        t.apertura = request.form['apertura']
        t.cierre = request.form['cierre']
        db.session.commit()
        return redirect(url_for('gestionar_tiendas'))
    return render_template('editar_tienda.html', tienda=t)

@app.route('/eliminar_tienda/<int:id>')
def eliminar_tienda(id):
    db.session.delete(Tienda.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('gestionar_tiendas'))

# --- RUTAS DE EMPLEADOS (Con Validación de Horas Máximas) ---
@app.route('/empleados', methods=['GET', 'POST'])
def gestionar_empleados():
    conf = Configuracion.query.first()
    if request.method == 'POST':
        nombre = request.form['nombre']
        tipo = request.form['tipo_jornada']
        extras = int(request.form.get('horas_extra', 0))
        tienda_id = request.form['tienda_id']
        
        base = conf.horas_completa if tipo == "Completa" else conf.horas_parcial
        if (base + extras) > conf.max_horas_semanales:
            flash(f"¡ERROR! El total ({base + extras}h) supera el máximo de {conf.max_horas_semanales}h.", "danger")
        else:
            nuevo = Empleado(nombre=nombre, tipo_jornada=tipo, horas_extra=extras, tienda_id=tienda_id)
            db.session.add(nuevo)
            db.session.commit()
            flash("Empleado guardado correctamente", "success")
            
        return redirect(url_for('gestionar_empleados'))
    
    return render_template('empleados.html', empleados=Empleado.query.all(), tiendas=Tienda.query.all())

@app.route('/editar_empleado/<int:id>', methods=['GET', 'POST'])
def editar_empleado(id):
    e = Empleado.query.get_or_404(id)
    conf = Configuracion.query.first()
    tiendas = Tienda.query.all()
    if request.method == 'POST':
        tipo = request.form['tipo_jornada']
        extras = int(request.form['horas_extra'])
        base = conf.horas_completa if tipo == "Completa" else conf.horas_parcial
        
        if (base + extras) > conf.max_horas_semanales:
            flash("No se pudo editar: Supera el límite de horas.", "danger")
        else:
            e.nombre = request.form['nombre']
            e.tipo_jornada = tipo
            e.horas_extra = extras
            e.tienda_id = request.form['tienda_id']
            db.session.commit()
            return redirect(url_for('gestionar_empleados'))
            
    return render_template('editar_empleado.html', emp=e, tiendas=tiendas)

@app.route('/eliminar_empleado/<int:id>')
def eliminar_empleado(id):
    emp = Empleado.query.get_or_404(id)
    db.session.delete(emp)
    db.session.commit()
    return redirect(url_for('gestionar_empleados'))

@app.route('/exportar')
def exportar():
    # Lógica de Excel (igual a la anterior, usando Configuracion.query.first())
    # ...
    return "Excel Generado" # Simplificado para el ejemplo

if __name__ == '__main__':
    app.run(debug=True)