from flask import Flask, render_template, request, send_file, redirect, url_for, session
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import date
import os
import base64
from staticmap import StaticMap, CircleMarker
from datetime import datetime

app = Flask(__name__)
app.secret_key = "DC_g&rad0r"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Função para gerar mapa OSM ---
def gerar_mapa(lat, lon, caminho_saida):
    try:
        m = StaticMap(600, 400)
        marker = CircleMarker((float(lon), float(lat)), 'red', 12)
        m.add_marker(marker)
        image = m.render(zoom=16)
        image.save(caminho_saida)
        return caminho_saida
    except Exception as e:
        print("❌ Erro ao gerar mapa OSM:", str(e))
        return None

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "defesacivil" and password == "DC_g&rad0r":
            session["logado"] = True
            return redirect(url_for("home"))
        else:
            return render_template("login.html", erro="Usuário ou senha incorretos.")
    return render_template("login.html")

@app.route("/home")
def home():
    if not session.get("logado"):
        return redirect(url_for("login"))
    return render_template("home.html")

# Campos do formulário
campos = [
    ("Nº do Laudo", "numero_laudo"),
    ("Solicitação (n° Ofício, OS, etc)", "n_processo"),
#    ("Nome", "nome"),
#    ("CPF", "cpf"),
#    ("Telefone", "telefone"),
    ("Endereço (Rua, Quadra, Lote)", "endereco"),
    ("Bairro", "bairro"),
    ("Latitude", "latitude"),
    ("Longitude", "longitude"),
    ("Data da Vistoria", "data_vistoria"),
    ("Data do relatório", "data_relatorio")
]

@app.route("/chuvas", methods=["GET", "POST"])
def chuvas():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            doc = DocxTemplate("modelo_laudo_imagens.docx")
            contexto = {campo[1]: request.form.get(campo[1]) for campo in campos}
            contexto["ano"] = date.today().year
            contexto["grau_risco"] = request.form.get("grau_risco")

            # Problemas solo
            problemas = request.form.getlist("problemas_solo")
            outro = request.form.get("problemas_solo_outro", "").strip()
            if outro:
                problemas.append(outro)
            contexto["problemas_solo"] = ", ".join(problemas)
            # Presença cursos
            presenca = request.form.getlist("presenca_cursos")
            cursos = request.form.get("presenca_cursos_outro", "").strip()
            if cursos:
                presenca.append(cursos)
            contexto["presenca_cursos"] = ", ".join(presenca)
            contexto["sinais_instabilidade"] = ", ".join(request.form.getlist("sinais_instabilidade"))
            contexto["fatores_risco"] = ", ".join(request.form.getlist("fatores_risco"))

            imagens = []

            # --- Gerar mapa automático OSM ---
            lat = request.form.get("latitude")
            lon = request.form.get("longitude")
            if lat and lon:
                caminho_mapa = gerar_mapa(lat, lon, os.path.join(UPLOAD_FOLDER, "mapa.png"))
                if caminho_mapa:
                    contexto["imagem1"] = InlineImage(doc, caminho_mapa, width=Mm(100))
                    contexto["descricao1"] = "Localização Geográfica"
                    imagens.append(caminho_mapa)
                else:
                    contexto["imagem1"] = ""
                    contexto["descricao1"] = ""
            else:
                contexto["imagem1"] = ""
                contexto["descricao1"] = ""

            # --- Imagens 2 a 7 (upload manual) ---
            for i in range(2, 8):
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

            # --- Finalizar Word ---
            nome_arquivo = f"Laudo_{contexto['numero_laudo']}-{contexto['ano']}.docx"
            caminho_saida = os.path.join(UPLOAD_FOLDER, nome_arquivo)

            doc.render(contexto)
            doc.save(caminho_saida)

            return send_file(caminho_saida, as_attachment=True)

        except Exception as e:
            return f"Erro interno: {e}", 500

    return render_template("formulario.html", campos=campos)

@app.route("/incendios", methods=["GET", "POST"])
def incendios():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            doc = DocxTemplate("modelo_laudo_incendio.docx")
            contexto = {}
            def formatar_data(data_str):
                if data_str:  # se não estiver vazio
                    return datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m/%Y")
                return ""


                
            # Campos principais
            
            contexto["n_os"] = request.form.get("n_os")
            contexto["origem_ocorrencia"] = request.form.get("origem_ocorrencia")
            contexto["n_ocorrencia"] = request.form.get("n_ocorrencia")
            contexto["equipe"] = ", ".join(request.form.getlist("equipe"))
            contexto["endereco"] = request.form.get("endereco")
            contexto["bairro"] = request.form.get("bairro")
            contexto["cep"] = request.form.get("cep")
            contexto["descricao"] = request.form.get("descricao")
            contexto["nome"] = request.form.get("nome")
            contexto["email"] = request.form.get("email")
            contexto["relato"] = request.form.get("relato")
            contexto["recomendacoes"] = request.form.get("recomendacoes")
            contexto["data_ocorrencia"] = formatar_data(request.form.get("data_ocorrencia"))
            contexto["data_vistoria"] = formatar_data(request.form.get("data_vistoria"))
            contexto["data_fim"] = formatar_data(request.form.get("data_fim"))
            

            # Imagens
            for i in range(1, 5):
                arquivo = request.files.get(f"imagem{i}")
                desc = request.form.get(f"descricao{i}", "")
                contexto[f"descricao{i}"] = desc

                if arquivo and arquivo.filename:
                    caminho = os.path.join(UPLOAD_FOLDER, f"incendio_imagem{i}.jpg")
                    arquivo.save(caminho)
                    contexto[f"imagem{i}"] = InlineImage(doc, caminho, width=Mm(100))
                else:
                    contexto[f"imagem{i}"] = ""

            # Gerar documento
            nome_arquivo = f"Incendio_{contexto['n_ocorrencia']}.docx"
            caminho_saida = os.path.join(UPLOAD_FOLDER, nome_arquivo)

            doc.render(contexto)
            doc.save(caminho_saida)

            return send_file(caminho_saida, as_attachment=True)

        except Exception as e:
            return f"Erro interno: {e}", 500

    return render_template("incendios.html")

@app.route("/equipes")
def equipes():
    return "📌 Página de Equipes (em construção)"

@app.route("/atendimentos")
def atendimentos():
    return "📌 Página de Atendimentos (em construção)"

@app.route("/dashboard")
def dashboard():
    return "📌 Página de Dashboard (em construção)"


@app.route("/logout")
def logout():
    session.pop("logado", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)























