from flask import Blueprint, abort, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Tanque, Biometria, EstoqueRacao, RegistroTrato
from datetime import date
from sqlalchemy import func

tanques_bp = Blueprint('tanques', __name__)

@tanques_bp.route('/tanques')
@login_required
def listar_tanques():
    if current_user.is_admin:
        tanques = Tanque.query.all()
    else:
        tanques = Tanque.query.filter_by(user_id=current_user.id).all()
    return render_template('tanques.html', tanques=tanques)

@tanques_bp.route('/cadastrar_tanque', methods=['GET', 'POST'])
@login_required
def cadastrar_tanque():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        especie = request.form.get('especie', '').strip()
        quantidade = request.form.get('quantidade', '')

        if not nome or not especie or not quantidade:
            flash('Preencha todos os campos.', 'erro')
            return redirect(url_for('tanques.cadastrar_tanque'))

        try:
            quantidade = int(quantidade)
            if quantidade <= 0:
                raise ValueError
        except ValueError:
            flash('A quantidade de peixes deve ser um número maior que zero.', 'erro')
            return redirect(url_for('tanques.cadastrar_tanque'))

        novo_tanque = Tanque(
            nome=nome,
            especie=especie,
            quantidade=quantidade,
            user_id=current_user.id
        )

        db.session.add(novo_tanque)
        db.session.commit()

        flash('Tanque cadastrado com sucesso!', 'sucesso')
        return redirect(url_for('tanques.listar_tanques'))

    return render_template('cadastrar_tanque.html')

# -------------------------------------------------------------
# ROTA DE EDIÇÃO DE TANQUE
# -------------------------------------------------------------
@tanques_bp.route('/editar_tanque/<int:tanque_id>', methods=['GET', 'POST'])
@login_required
def editar_tanque(tanque_id):
    tanque = Tanque.query.get_or_404(tanque_id)

    # Verifica se o utilizador tem permissão
    if not current_user.is_admin and tanque.user_id != current_user.id:
        flash('Você não tem permissão para editar este tanque.', 'erro')
        return redirect(url_for('tanques.listar_tanques'))

    if request.method == 'POST':
        try:
            tanque.nome = request.form.get('nome', tanque.nome)
            tanque.especie = request.form.get('especie', tanque.especie)
            
            qtd = request.form.get('quantidade')
            if qtd:
                tanque.quantidade = int(qtd)
                
            volume = request.form.get('volume_m3')
            if volume:
                # Substitui vírgula por ponto para evitar erros no formato decimal
                tanque.volume_m3 = float(str(volume).replace(',', '.'))
                
            db.session.commit()
            flash('Tanque atualizado com sucesso!', 'sucesso')
            return redirect(url_for('tanques.biometria', tanque_id=tanque.id))
            
        except ValueError:
            flash('Valores numéricos inválidos. Verifique a quantidade e o volume.', 'erro')
            return redirect(url_for('tanques.editar_tanque', tanque_id=tanque.id))

    # Renderiza o formulário de edição (reaproveitando a tela de cadastro se necessário)
    return render_template('cadastrar_tanque.html', tanque=tanque)

# -------------------------------------------------------------
# ROTAS ADICIONADAS: ESTOQUE E HISTÓRICO
# -------------------------------------------------------------
@tanques_bp.route('/estoque', methods=['GET', 'POST'])
@login_required
def estoque():
    if request.method == 'POST':
        qtd = request.form.get('quantidade_kg')
        try:
            qtd_float = float(qtd)
            if qtd_float < 0:
                raise ValueError
        except (TypeError, ValueError):
            flash('Informe uma quantidade válida de ração.', 'erro')
            return redirect(url_for('tanques.estoque'))

        item_estoque = EstoqueRacao.query.filter_by(user_id=current_user.id).first()
        if not item_estoque:
            item_estoque = EstoqueRacao(quantidade_kg=qtd_float, user_id=current_user.id)
            db.session.add(item_estoque)
        else:
            item_estoque.quantidade_kg += qtd_float

        db.session.commit()
        flash('Estoque atualizado com sucesso!', 'sucesso')
        return redirect(url_for('tanques.estoque'))

    item_estoque = EstoqueRacao.query.filter_by(user_id=current_user.id).first()
    return render_template('estoque.html', estoque=item_estoque)


@tanques_bp.route('/historico')
@login_required
def historico():
    if current_user.is_admin:
        historico_tratos = RegistroTrato.query.order_by(RegistroTrato.data.desc()).all()
    else:
        historico_tratos = RegistroTrato.query.filter_by(user_id=current_user.id).order_by(RegistroTrato.data.desc()).all()
    
    return render_template('historico.html', historico=historico_tratos)

from datetime import date
from sqlalchemy import func

# -------------------------------------------------------------
# ROTA DE BIOMETRIA E BEM-ESTAR
# -------------------------------------------------------------
@tanques_bp.route('/biometria/<int:tanque_id>', methods=['GET', 'POST'])
@login_required
def biometria(tanque_id):
    tanque = Tanque.query.get_or_404(tanque_id)

    if not current_user.is_admin and tanque.user_id != current_user.id:
        flash('Você não tem permissão para acessar este tanque.', 'erro')
        return redirect(url_for('tanques.listar_tanques'))

    if request.method == 'POST':
        try:
            peso_medio = float(request.form.get('peso_medio'))
            temperatura = float(request.form.get('temperatura'))
            if peso_medio <= 0:
                raise ValueError
        except (TypeError, ValueError):
            flash('Digite valores válidos para peso e temperatura.', 'erro')
            return redirect(url_for('tanques.biometria', tanque_id=tanque.id))

        nova_biometria = Biometria(
            peso_medio_gramas=peso_medio,
            temperatura_agua=temperatura,
            tanque_id=tanque.id
        )

        db.session.add(nova_biometria)
        db.session.commit()

        flash('Biometria registrada com sucesso!', 'sucesso')
        return redirect(url_for('tanques.biometria', tanque_id=tanque.id))

    historico = Biometria.query.filter_by(tanque_id=tanque.id).order_by(Biometria.data.desc()).all()
    ultima_medicao = historico[0] if historico else None
    
    # Soma todas as quantidades de ração dadas a este tanque no dia de hoje
    hoje = date.today()
    tratos_hoje = db.session.query(func.sum(RegistroTrato.quantidade_kg)).filter(
        RegistroTrato.tanque_id == tanque.id,
        func.date(RegistroTrato.data) == hoje
    ).scalar()
    
    fornecido_hoje_kg = tratos_hoje if tratos_hoje else 0.0

    # Estrutura base vazia para tanques novos
    av = {
        'score': None,
        'nivel': 'info',
        'rotulo': 'Sem dados',
        'calc': None,
        'alimentacao': None,
        'alertas': []
    }
    racao_sugerida = 0
    
    if ultima_medicao:
        # 1. Cálculos de Biomassa e Ração
        biomassa_kg = (ultima_medicao.peso_medio_gramas * tanque.quantidade) / 1000
        taxa = 0.03
        
        temp_atual = ultima_medicao.temperatura_agua
        
        if temp_atual < 22:
            taxa = 0.01
        elif temp_atual > 32:
            taxa = 0.015
            
        racao_sugerida = round(biomassa_kg * taxa, 2)
        
        falta_kg = max(0, racao_sugerida - fornecido_hoje_kg)
        cobertura = (fornecido_hoje_kg / racao_sugerida) if racao_sugerida > 0 else 0
        total_registos = RegistroTrato.query.filter_by(tanque_id=tanque.id).count()
        
        # 2. CÁLCULO DINÂMICO: Nota da Alimentação (35% do score)
        nota_alim = min(100, int(cobertura * 100)) if cobertura <= 1.15 else 60
        
        # 3. CÁLCULO DINÂMICO: Nota da Temperatura (40% do score)
        # Ideal: 26 a 30°C
        if 26 <= temp_atual <= 30:
            nota_temp = 100
        elif 24 <= temp_atual < 26 or 30 < temp_atual <= 32:
            nota_temp = 80
        elif 20 <= temp_atual < 24 or 32 < temp_atual <= 34:
            nota_temp = 50
        else:
            nota_temp = 20
            
        # 4. CÁLCULO DINÂMICO: Nota do Monitoramento/Biometria (25% do score)
        # Quantos dias se passaram desde a última medição?
        dias_sem_biometria = (hoje - ultima_medicao.data.date()).days if ultima_medicao.data else 0
        if dias_sem_biometria <= 7:
            nota_biom = 100
        elif dias_sem_biometria <= 15:
            nota_biom = 80
        elif dias_sem_biometria <= 30:
            nota_biom = 50
        else:
            nota_biom = 20

        # 5. CÁLCULO FINAL: O Score do Bem-estar
        score_geral = int((nota_temp * 0.40) + (nota_alim * 0.35) + (nota_biom * 0.25))
        
        if score_geral >= 85:
            nivel_geral, rotulo_geral = 'otimo', 'Excelente'
        elif score_geral >= 70:
            nivel_geral, rotulo_geral = 'bom', 'Bom'
        elif score_geral >= 50:
            nivel_geral, rotulo_geral = 'atencao', 'Atenção'
        else:
            nivel_geral, rotulo_geral = 'critico', 'Crítico'

        # Monta o dicionário preenchido
        av = {
            'calc': {
                'temp_chave': 'otimo' if 26 <= temp_atual <= 30 else 'atencao',
                'temp_rotulo': 'Temperatura OK' if 26 <= temp_atual <= 30 else 'Atenção',
                'total_kg': racao_sugerida,
                'taxa_ajustada': taxa * 100,
                'refeicoes': 3,
                'por_refeicao_kg': round(racao_sugerida / 3, 2),
                'proteina': 32,
                'biomassa_kg': biomassa_kg,
                'taxa_base': 3.0,
                'fator_temperatura': round(taxa / 0.03, 2),
                'perfil_nome': tanque.especie,
                'temp_ideal': [26, 30],
                'temp_mensagem': 'Temperatura da água atualizada.'
            },
            'alimentacao': {
                'cobertura_hoje': cobertura,
                'fornecido_hoje_kg': round(fornecido_hoje_kg, 2),
                'falta_kg': round(falta_kg, 2),
                'nota': nota_alim,
                'sem_registros': total_registos == 0
            },
            'score': score_geral,
            'nivel': nivel_geral,
            'rotulo': rotulo_geral,
            'temperatura': {
                'valor': temp_atual,
                'nota': nota_temp,
                'ideal': [26, 30]
            },
            'monitoramento': {
                'nota': nota_biom,
                'dias': dias_sem_biometria
            },
            'alertas': []
        }

    return render_template(
        'biometria.html',
        tanque=tanque,
        racao_sugerida=racao_sugerida,
        biometrias=historico,
        ultima=ultima_medicao,
        av=av
    )

# -------------------------------------------------------------
# ROTA DE REGISTRO DE TRATO (RAÇÃO)
# -------------------------------------------------------------
@tanques_bp.route('/registrar_trato/<int:tanque_id>', methods=['POST'])
@login_required
def registrar_trato(tanque_id):
    tanque = Tanque.query.get_or_404(tanque_id)

    # Verifica se o usuário é dono do tanque ou admin
    if not current_user.is_admin and tanque.user_id != current_user.id:
        if request.is_json:
            return jsonify({'erro': 'Sem permissão'}), 403
        flash('Sem permissão para acessar este tanque.', 'erro')
        return redirect(url_for('tanques.listar_tanques'))

    # Pega os dados enviados (suporta formulário tradicional ou JSON)
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    # Tenta capturar as chaves mais comuns que o frontend pode estar enviando
    qtd = data.get('valor') or data.get('quantidade_kg') or data.get('quantidade')

    try:
        if qtd is None or str(qtd).strip() == '':
            raise ValueError
            
        # Tratamento crucial: substitui vírgula por ponto (ex: "1,5" vira "1.5")
        qtd_str = str(qtd).replace(',', '.')
        qtd_float = float(qtd_str)
        
        if qtd_float <= 0:
            raise ValueError
            
    except (TypeError, ValueError):
        if request.is_json:
            return jsonify({'erro': 'Quantidade inválida'}), 400
        flash('Informe uma quantidade válida maior que zero.', 'erro')
        return redirect(url_for('tanques.biometria', tanque_id=tanque.id))

    # 1. Registra o trato no histórico
    novo_trato = RegistroTrato(
        quantidade_kg=qtd_float,
        tanque_id=tanque.id,
        user_id=current_user.id
    )
    db.session.add(novo_trato)

    # 2. Desconta automaticamente do estoque de ração
    estoque = EstoqueRacao.query.filter_by(user_id=current_user.id).first()
    if estoque:
        estoque.quantidade_kg -= qtd_float
        if estoque.quantidade_kg < 0:
            estoque.quantidade_kg = 0

    db.session.commit()

    # Responde de acordo com quem chamou (JS vs HTML tradicional)
    if request.is_json:
        return jsonify({'ok': True}), 200
        
    flash('Ração registrada com sucesso!', 'sucesso')
    return redirect(url_for('tanques.biometria', tanque_id=tanque.id))

# -------------------------------------------------------------
# ROTA DE EXCLUSÃO DE TANQUE
# -------------------------------------------------------------
@tanques_bp.route('/excluir_tanque/<int:tanque_id>', methods=['POST'])
@login_required
def excluir_tanque(tanque_id):
    tanque = Tanque.query.get_or_404(tanque_id)

    # Verifica se o utilizador é dono do tanque ou admin
    if not current_user.is_admin and tanque.user_id != current_user.id:
        flash('Você não tem permissão para excluir este tanque.', 'erro')
        return redirect(url_for('tanques.listar_tanques'))

    # Apaga os registos dependentes primeiro (para não dar erro no banco de dados)
    Biometria.query.filter_by(tanque_id=tanque.id).delete()
    RegistroTrato.query.filter_by(tanque_id=tanque.id).delete()
    
    # Apaga o tanque em si
    db.session.delete(tanque)
    db.session.commit()

    flash(f'O tanque "{tanque.nome}" e todo o seu histórico foram excluídos!', 'sucesso')
    return redirect(url_for('tanques.listar_tanques'))