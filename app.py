from flask import Flask, render_template, request, send_file
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import date
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            doc = DocxTemplate("modelo_laudo_imagens.docx")

            campos = ["numero_laudo", "numero_processo", "nome", "cpf", "telefone", "endereco",
                      "bairro", "latitude", "longitude", "data_vistoria"]

            contexto = {campo: request.form.get(campo) for campo in campos}
            contexto["ano"] = date.today().year
            contexto["grau_risco"] = request.form.get("grau_risco")
            contexto["patologias"] = ", ".join(request.form.getlist("patologias"))

            for i in range(1, 8):
                contexto[f"descricao{i}"] = request.form.get(f"descricao{i}", "")
                imagem = request.files.get(f"imagem{i}")
                if imagem and imagem.filename:
                    caminho = os.path.join(UPLOAD_FOLDER, f"imagem{i}.jpg")
                    imagem.save(caminho)
                    contexto[f"imagem{i}"] = InlineImage(doc, caminho, width=Mm(100))
                else:
                    contexto[f"imagem{i}"] = ""

            nome_arquivo = f"Laudo_{contexto['numero_laudo']}-{contexto['ano']} - {contexto['nome']}.docx"
            doc.render(contexto)
            doc.save(nome_arquivo)

            return send_file(nome_arquivo, as_attachment=True)
        except Exception as e:
            return f"Erro ao gerar laudo: {str(e)}", 500

    return render_template("formulario.html")

if __name__ == "__main__":
    app.run(debug=True)
