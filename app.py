from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

tanques = []

@app.route('/')
def index():
    return render_template('base.html')

@app.route('/tanques/cadastrar', methods=["GET", "POST"])
def cadastrar_tanque():

    if request.method == "POST":
        nome = request.form["nome"]
        especie = request.form["especie"]
        quantidade = request.form["quantidade"]

        tanque = {
            "id": len(tanques) + 1,
            "nome": nome,
            "especie": especie,
            "quantidade": quantidade
        }

        tanques.append(tanque)

        return redirect("/tanques")

    return render_template("cadastrar_tanque.html")

@app.route('/tanques')
def listar_tanques():
    return render_template(
        "tanques.html",
        tanques=tanques  # Repassa a lista para a tela renderizar
    )

@app.route('/tanques/deletar/<int:tanque_id>', methods=["POST"])
def deletar_tanque(tanque_id):
    global tanques
    # Filtra a lista removendo o tanque com o ID correspondente
    tanques = [t for t in tanques if t["id"] != tanque_id]
    return redirect(url_for('listar_tanques'))

@app.route('/tanques/editar/<int:tanque_id>', methods=["GET", "POST"])
def editar_tanque(tanque_id):
    # Busca o tanque pelo ID
    tanque = next((t for t in tanques if t["id"] == tanque_id), None)
    
    if not tanque:
        return redirect(url_for('listar_tanques'))

    if request.method == "POST":
        tanque["nome"] = request.form["nome"]
        tanque["especie"] = request.form["especie"]
        tanque["quantidade"] = request.form["quantidade"]

        return redirect(url_for('listar_tanques'))

    return render_template("editar_tanques.html", tanque=tanque)

if __name__ == "__main__":
    app.run(debug=True)