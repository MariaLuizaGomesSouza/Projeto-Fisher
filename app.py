from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# Configurações de segurança e Banco de Dados
app.config['SECRET_KEY'] = 'chave_secreta_fisher_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fisher.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça login para acessar esta página."

# ==========================================
# MODELOS DE BANCO DE DADOS
# ==========================================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    # Relação: Um usuário pode ter vários tanques
    tanques = db.relationship('Tanque', backref='dono', lazy=True)

class Tanque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    especie = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    # Chave estrangeira ligando o tanque ao dono
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Adicione esta linha lá no topo do arquivo, junto com os outros imports:
from datetime import datetime

# Cole este bloco logo ABAIXO da classe Tanque:
class Biometria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    peso_medio_gramas = db.Column(db.Float, nullable=False)
    temperatura_agua = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Chave estrangeira ligando a biometria ao tanque
    tanque_id = db.Column(db.Integer, db.ForeignKey('tanque.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================
# ROTAS DE AUTENTICAÇÃO
# ==========================================
@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        if User.query.filter_by(email=email).first():
            flash('Este e-mail já está cadastrado!')
            return redirect(url_for('registrar'))
        
        # O PRIMEIRO usuário a se cadastrar no sistema vira Admin automaticamente
        is_admin = True if User.query.count() == 0 else False
        
        novo_user = User(nome=nome, email=email, senha=generate_password_hash(senha), is_admin=is_admin)
        db.session.add(novo_user)
        db.session.commit()
        
        flash('Conta criada com sucesso! Faça login.')
        return redirect(url_for('login'))
    return render_template('registrar.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.senha, senha):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('E-mail ou senha incorretos.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ==========================================
# ROTAS DO SISTEMA (Requerem Login)
# ==========================================
@app.route('/')
@login_required
def dashboard():
    # Se for admin, conta todos os tanques. Se for produtor, conta só os dele.
    if current_user.is_admin:
        meus_tanques = Tanque.query.all()
    else:
        meus_tanques = Tanque.query.filter_by(user_id=current_user.id).all()
        
    total_tanques = len(meus_tanques)
    return render_template('index.html', total_tanques=total_tanques)

@app.route('/tanques')
@login_required
def listar_tanques():
    if current_user.is_admin:
        tanques = Tanque.query.all()
    else:
        tanques = Tanque.query.filter_by(user_id=current_user.id).all()
    return render_template('tanques.html', tanques=tanques)

@app.route('/cadastrar_tanque', methods=['GET', 'POST'])
@login_required
def cadastrar_tanque():
    if request.method == 'POST':
        novo_tanque = Tanque(
            nome=request.form.get('nome'),
            especie=request.form.get('especie'),
            quantidade=request.form.get('quantidade'),
            user_id=current_user.id # Salva o tanque no nome do usuário logado
        )
        db.session.add(novo_tanque)
        db.session.commit()
        return redirect(url_for('listar_tanques'))
    return render_template('cadastrar_tanque.html')
# ==========================================
# ROTAS DE AÇÕES DOS TANQUES
# ==========================================
@app.route('/biometria/<int:tanque_id>', methods=['GET', 'POST'])
@login_required
def biometria(tanque_id):
    tanque = Tanque.query.get_or_404(tanque_id)
    
    if not current_user.is_admin and tanque.user_id != current_user.id:
        flash('Você não tem permissão para acessar este tanque.')
        return redirect(url_for('listar_tanques'))

    # Se o usuário clicou no botão de Salvar Biometria
    if request.method == 'POST':
        peso_medio = float(request.form.get('peso_medio'))
        temperatura = float(request.form.get('temperatura'))
        
        nova_biometria = Biometria(
            peso_medio_gramas=peso_medio,
            temperatura_agua=temperatura,
            tanque_id=tanque.id
        )
        db.session.add(nova_biometria)
        db.session.commit()
        
        flash('Biometria registrada com sucesso!')
        return redirect(url_for('biometria', tanque_id=tanque.id))
        
    # Busca todas as biometrias desse tanque, da mais recente para a mais antiga
    historico = Biometria.query.filter_by(tanque_id=tanque.id).order_by(Biometria.data.desc()).all()
    
    # Cálculo automático de Ração (Exemplo usando 3% da biomassa)
    racao_sugerida = 0
    if historico:
        ultima_medicao = historico[0]
        # Biomassa total em KG: (Peso médio em gramas * quantidade de peixes) / 1000
        biomassa_kg = (ultima_medicao.peso_medio_gramas * tanque.quantidade) / 1000
        
        taxa = 0.03 # 3% do peso corporal por padrão
        
        # Ajuste de metabolismo baseado na temperatura
        if ultima_medicao.temperatura_agua < 22:
            taxa = 0.01 # Come menos na água fria
        elif ultima_medicao.temperatura_agua > 32:
            taxa = 0.015 # Restrição em calor extremo para não faltar oxigênio
            
        racao_sugerida = round(biomassa_kg * taxa, 2)

    return render_template('biometria.html', tanque=tanque, racao_sugerida=racao_sugerida, biometrias=historico)

@app.route('/editar_tanque/<int:tanque_id>', methods=['GET', 'POST'])
@login_required
def editar_tanque(tanque_id):
    tanque = Tanque.query.get_or_404(tanque_id)
    if not current_user.is_admin and tanque.user_id != current_user.id:
        flash('Você não tem permissão para editar este tanque.')
        return redirect(url_for('listar_tanques'))

    if request.method == 'POST':
        tanque.nome = request.form.get('nome')
        tanque.especie = request.form.get('especie')
        tanque.quantidade = request.form.get('quantidade')
        db.session.commit()
        return redirect(url_for('listar_tanques'))
        
    return render_template('editar_tanques.html', tanque=tanque)

@app.route('/deletar_tanque/<int:tanque_id>', methods=['POST'])
@login_required
def deletar_tanque(tanque_id):
    tanque = Tanque.query.get_or_404(tanque_id)
    if not current_user.is_admin and tanque.user_id != current_user.id:
        flash('Você não tem permissão para deletar este tanque.')
        return redirect(url_for('listar_tanques'))
        
    db.session.delete(tanque)
    db.session.commit()
    return redirect(url_for('listar_tanques'))
# Cria as tabelas no banco de dados se não existirem
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)