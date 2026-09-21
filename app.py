from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fisher.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '123456789'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redireciona para a função def login()
login_manager.login_message = "Por favor, inicie sessão para aceder a esta página."

class Produtor(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return Produtor.query.get(int(user_id))

# ----------------- MODELOS DO BANCO DE DADOS -----------------

class Tanque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    especie = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    biometrias = db.relationship('Biometria', backref='tanque', lazy=True, cascade="all, delete")

class Biometria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tanque_id = db.Column(db.Integer, db.ForeignKey('tanque.id'), nullable=False)
    data = db.Column(db.Date, default=datetime.today)
    peso_medio_gramas = db.Column(db.Float, nullable=False)
    temperatura_agua = db.Column(db.Float, nullable=True)

with app.app_context():
    db.create_all()

# ----------------- ROTAS DO SISTEMA -----------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tanques/cadastrar', methods=["GET", "POST"])
@login_required
def cadastrar_tanque():
    if request.method == "POST":
        novo_tanque = Tanque(
            nome=request.form["nome"],
            especie=request.form["especie"],
            quantidade=int(request.form["quantidade"])
        )
        db.session.add(novo_tanque)
        db.session.commit()
        return redirect(url_for('listar_tanques'))
    return render_template("cadastrar_tanque.html")

@app.route('/tanques')
@login_required
def listar_tanques():
    tanques = Tanque.query.all()
    return render_template("tanques.html", tanques=tanques)

@app.route('/tanques/deletar/<int:tanque_id>', methods=["POST"])
@login_required
def deletar_tanque(tanque_id):
    tanque = Tanque.query.get_or_404(tanque_id)
    db.session.delete(tanque)
    db.session.commit()
    return redirect(url_for('listar_tanques'))

@app.route('/tanques/editar/<int:tanque_id>', methods=["GET", "POST"])
@login_required
def editar_tanque(tanque_id):
    tanque = Tanque.query.get_or_404(tanque_id)
    
    if request.method == "POST":
        tanque.nome = request.form["nome"]
        tanque.especie = request.form["especie"]
        tanque.quantidade = int(request.form["quantidade"])
        db.session.commit()
        return redirect(url_for('listar_tanques'))

    return render_template("editar_tanques.html", tanque=tanque)

# ----------------- BIOMETRIA E CÁLCULO DE RAÇÃO -----------------

@app.route('/tanques/<int:tanque_id>/biometria', methods=["GET", "POST"])
@login_required
def biometria(tanque_id):
    tanque = Tanque.query.get_or_404(tanque_id)
    
    if request.method == "POST":
        nova_biometria = Biometria(
            tanque_id=tanque.id,
            peso_medio_gramas=float(request.form["peso_medio"]),
            temperatura_agua=float(request.form.get("temperatura", 0))
        )
        db.session.add(nova_biometria)
        db.session.commit()
        return redirect(url_for('biometria', tanque_id=tanque.id))
        
    biometrias = Biometria.query.filter_by(tanque_id=tanque.id).order_by(Biometria.data.desc()).all()
    
    racao_sugerida = 0
    if biometrias:
        ultima_biometria = biometrias[0]
        biomassa_total_kg = (ultima_biometria.peso_medio_gramas / 1000) * tanque.quantidade
        
        taxa_alimentacao = 0.03
        
        if ultima_biometria.temperatura_agua < 22:
            taxa_alimentacao = 0.015
        elif ultima_biometria.temperatura_agua > 32:
            taxa_alimentacao = 0.020
            
        racao_sugerida = biomassa_total_kg * taxa_alimentacao
        
    return render_template("biometria.html", tanque=tanque, biometrias=biometrias, racao_sugerida=round(racao_sugerida, 2))

# ----------------- REGISTRO, LOGIN E LOGOUT -----------------
@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        
        usuario_existente = Produtor.query.filter_by(email=email).first()
        if usuario_existente:
            flash('Este email já está registrado. Por favor, faça login.')
            return redirect(url_for('registrar'))
            
        senha_encriptada = generate_password_hash(senha)
        
        novo_produtor = Produtor(nome=nome, email=email, senha=senha_encriptada)
        db.session.add(novo_produtor)
        db.session.commit()
        
        flash('Conta criada com sucesso! Pode fazer login agora.')
        return redirect(url_for('login'))
        
    return render_template('registrar.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        print(f"Tentando fazer login com o email: {email}")
        
        produtor = Produtor.query.filter_by(email=email).first()
        
        if not produtor:
            print("ERRO: Utilizador não encontrado na base de dados!")
            flash('Email ou palavra-passe incorretos.')
            return render_template('login.html')
            
        print("Utilizador encontrado! Verificando a palavra-passe...")
        
        if check_password_hash(produtor.senha, senha):
            print("Palavra-passe correta! Redirecionando para o index...")
            login_user(produtor)
            return redirect(url_for('index'))
        else:
            print("ERRO: A palavra-passe está errada!")
            flash('Email ou palavra-passe incorretos.')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)