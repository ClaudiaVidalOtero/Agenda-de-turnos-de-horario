# ================= APP.PY COMPLETO ACTUALIZADO =================

import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from ortools.sat.python import cp_model

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'horarios.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------- MODELOS ----------------
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
    min_manana = db.Column(db.Integer, default=1)
    min_tarde = db.Column(db.Integer, default=1)

class Empleado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo_jornada = db.Column(db.String(50))
    horas_extra = db.Column(db.Integer, default=0)
    tienda_id = db.Column(db.Integer, db.ForeignKey('tienda.id'))

    preferencia_turno = db.Column(db.String(20), default="indiferente")
    dia_libre = db.Column(db.Integer, nullable=True)  # 0-6

# ---------------- OPTIMIZADOR ----------------
def generar_horarios(empleados, tienda, config):
    model = cp_model.CpModel()

    dias = range(7)
    turnos = {"mañana": 4, "tarde": 4}

    x = {}
    for e in empleados:
        for d in dias:
            for t in turnos:
                x[(e.id, d, t)] = model.NewBoolVar(f"x_{e.id}_{d}_{t}")

    # HARD
    for d in dias:
        model.Add(sum(x[(e.id, d, "mañana")] for e in empleados) >= tienda.min_manana)
        model.Add(sum(x[(e.id, d, "tarde")] for e in empleados) >= tienda.min_tarde)

    for e in empleados:
        for d in dias:
            model.Add(sum(x[(e.id, d, t)] for t in turnos) <= 1)

    for e in empleados:
        max_horas = config.horas_completa if e.tipo_jornada == "Completa" else config.horas_parcial
        max_horas += e.horas_extra
        model.Add(sum(x[(e.id, d, t)] * turnos[t] for d in dias for t in turnos) <= max_horas)

    # SOFT
    penalizaciones = []

    for e in empleados:
        for d in dias:
            for t in turnos:
                if e.preferencia_turno != "indiferente" and e.preferencia_turno != t:
                    penalizaciones.append(x[(e.id, d, t)] * 3)

        if e.dia_libre is not None:
            for t in turnos:
                penalizaciones.append(x[(e.id, e.dia_libre, t)] * 6)

    model.Minimize(sum(penalizaciones))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5
    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return None

    resultado = []
    for e in empleados:
        for d in dias:
            for t in turnos:
                if solver.Value(x[(e.id, d, t)]):
                    resultado.append((e.nombre, d, t))

    return resultado

# ---------------- RUTAS ----------------
@app.route('/')
def index():
    tiendas = Tienda.query.all()
    empleados = Empleado.query.all()
    return render_template('index.html', tiendas=tiendas, empleados=empleados)

@app.route('/tiendas', methods=['GET', 'POST'])
def gestionar_tiendas():
    if request.method == 'POST':
        nueva = Tienda(
            nombre=request.form['nombre'],
            apertura=request.form['apertura'],
            cierre=request.form['cierre'],
            min_manana=int(request.form['min_manana']),
            min_tarde=int(request.form['min_tarde'])
        )
        db.session.add(nueva)
        db.session.commit()
        return redirect(url_for('gestionar_tiendas'))
    return render_template('tiendas.html', tiendas=Tienda.query.all())

@app.route('/empleados', methods=['GET', 'POST'])
def gestionar_empleados():
    if request.method == 'POST':
        dia_libre = request.form.get('dia_libre')
        dia_libre = int(dia_libre) if dia_libre != '' else None

        nuevo = Empleado(
            nombre=request.form['nombre'],
            tipo_jornada=request.form['tipo_jornada'],
            horas_extra=int(request.form['horas_extra']),
            tienda_id=request.form['tienda_id'],
            preferencia_turno=request.form['preferencia_turno'],
            dia_libre=dia_libre
        )
        db.session.add(nuevo)
        db.session.commit()
        return redirect(url_for('gestionar_empleados'))

    return render_template('empleados.html', empleados=Empleado.query.all(), tiendas=Tienda.query.all())

@app.route('/generar', methods=['POST'])
def generar():
    tienda_id = request.form['tienda_id']
    empleados_ids = request.form.getlist('empleados')

    tienda = Tienda.query.get(tienda_id)
    empleados = Empleado.query.filter(Empleado.id.in_(empleados_ids)).all()
    config = Configuracion.query.first()

    if len(empleados) < (tienda.min_manana + tienda.min_tarde):
        return "No hay suficientes empleados"

    resultado = generar_horarios(empleados, tienda, config)

    return {"horario": resultado if resultado else "Sin solución"}

# ---------------- INIT ----------------
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)



