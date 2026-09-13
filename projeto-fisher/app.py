from flask import Flask, render_template, request, redirect

app = Flask(__name__)

# Banco de dados simulado em memória (Lista de dicionários)
registros_biometria = []

@app.route('/')
def index():
    return render_template('base.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        # Recebendo os dados do formulário
        tanque = request.form.get('tanque')
        qtd_peixes = int(request.form.get('qtd_peixes'))
        peso_medio = float(request.form.get('peso_medio'))
        taxa_racao = float(request.form.get('taxa_racao'))

        # Salvando no "banco de dados"
        novo_registro = {
            'tanque': tanque,
            'qtd_peixes': qtd_peixes,
            'peso_medio': peso_medio,
            'taxa_racao': taxa_racao
        }
        registros_biometria.append(novo_registro)
        
        return redirect('/listagem')
    
    return render_template('cadastro.html')

if __name__ == '__main__':
    app.run(debug=True)