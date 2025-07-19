from flask import Flask, render_template, request, send_file
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import date
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

campos = [
    ("Nº do Laudo", "numero_laudo"),
    ("Número do Processo", "numero_processo"),
    ("Nome", "nome"),
    ("CPF", "cpf"),
    ("Telefone", "telefone"),
    ("Endereço (Rua, Quadra, Lote)", "endereco"),
    ("Bairro", "bairro"),
    ("Latitude", "latitude"),
    ("Longitude", "longitude"),
    ("Data da Vistoria", "data_vistoria"),
]

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            doc = DocxTemplate("modelo_laudo_imagens.docx")
            contexto = {campo[1]: request.form.get(campo[1]) for campo in campos}
            contexto["ano"] = date.today().year
            contexto["grau_risco"] = request.form.get("grau_risco")

            # Solo - novos grupos
            problemas = request.form.getlist("problemas_solo")
            outro = request.form.get("problemas_solo_outro", "").strip()
            if outro:
                problemas.append(outro)
                contexto["problemas_solo"] = ", ".join(problemas)

            contexto["presenca_cursos"] = ", ".join(request.form.getlist("presenca_cursos"))
            contexto["sinais_instabilidade"] = ", ".join(request.form.getlist("sinais_instabilidade"))
            contexto["fatores_risco"] = ", ".join(request.form.getlist("fatores_risco"))

            imagens = []
            for i in range(1, 8):
                arquivo = request.files.get(f"imagem{i}")
                desc = request.form.get(f"descricao{i}", "")
                contexto[f"descricao{i}"] = desc
                if arquivo and arquivo.filename:
                    caminho = os.path.join(UPLOAD_FOLDER, f"imagem{i}.jpg")
                    arquivo.save(caminho)
                    imagens.append(caminho)
                    contexto[f"imagem{i}"] = InlineImage(doc, caminho, width=Mm(100))
                else:
                    contexto[f"imagem{i}"] = ""

            nome_arquivo = f"Laudo_{contexto['numero_laudo']}-{contexto['ano']}.docx"
            caminho_saida = os.path.join(UPLOAD_FOLDER, nome_arquivo)

            doc.render(contexto)
            doc.save(caminho_saida)

            return send_file(caminho_saida, as_attachment=True)
        except Exception as e:
            return f"Erro interno: {e}", 500

    return render_template("formulario.html", campos=campos)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
