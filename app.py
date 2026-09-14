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

if __name__ == "__main__":
    app.run(debug=True)