from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import date, datetime
import os, json
from staticmap import StaticMap, CircleMarker

# --- Configuração inicial ---
app = Flask(__name__)
app.secret_key = "DC_g&rad0r"

UPLOAD_FOLDER = "uploads/laudos"
DATA_FILE = "data/atendimentos.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("data", exist_ok=True)

# --- Função para salvar atendimentos ---
def salvar_atendimento(atendimento):
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
        else:
            dados = []

        dados.append(atendimento)

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

        print(f"✅ Atendimento salvo: {atendimento['numero_laudo']}")
    except Exception as e:
        print(f"❌ Erro ao salvar atendimento: {e}")

# --- Gerar mapa OSM ---
def gerar_mapa(lat, lon, caminho_saida):
    try:
        m = StaticMap(600, 400)
        marker = CircleMarker((float(lon), float(lat)), 'red', 12)
        m.add_marker(marker)
        image = m.render(zoom=16)
        image.save(caminho_saida)
        return caminho_saida
    except Exception as e:
        print("❌ Erro ao gerar mapa OSM:", e)
        return None

# --- Login ---
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

# --- Logout ---
@app.route("/logout")
def logout():
    session.pop("logado", None)
    return redirect(url_for("login"))

# --- Página Inicial ---
@app.route("/home")
def home():
    if not session.get("logado"):
        return redirect(url_for("login"))
    return render_template("home.html")

# --- Campos padrão ---
campos_base = [
    ("Nº do Laudo", "numero_laudo"),
    ("Solicitação (n° Processo, Ofício, OS, etc)", "n_processo"),
    ("Endereço (Rua, Quadra, Lote)", "endereco"),
    ("Bairro", "bairro"),
    ("Latitude", "latitude"),
    ("Longitude", "longitude"),
    ("Data da Vistoria", "data_vistoria"),
    ("Data do Relatório", "data_relatorio")
]

# --- Campos adicionais para Chuvas ---
campos_chuvas = [
    ("Nome", "nome"),
    ("CPF", "cpf"),
    ("Telefone", "telefone")
] + campos_base

# --- Função auxiliar: salvar laudo e registrar ---
def processar_laudo(contexto, tipo, template_file):
    doc = DocxTemplate(template_file)
    doc.render(contexto)

    nome_arquivo = f"Laudo_{contexto['numero_laudo']}-{date.today().year}.docx"
    caminho_saida = os.path.join(UPLOAD_FOLDER, nome_arquivo)
    doc.save(caminho_saida)

    atendimento = {
        "tipo": tipo,
        "numero_laudo": contexto.get("numero_laudo", ""),
        "bairro": contexto.get("bairro", ""),
        "latitude": contexto.get("latitude", ""),
        "longitude": contexto.get("longitude", ""),
        "grau_risco": contexto.get("grau_risco", ""),
        "data_vistoria": contexto.get("data_vistoria", ""),
        "arquivo": caminho_saida
    }
    salvar_atendimento(atendimento)

# --- Chuvas ---
@app.route("/chuvas", methods=["GET", "POST"])
def chuvas():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        try:
            contexto = {campo[1]: request.form.get(campo[1]) for campo in campos_chuvas}
            contexto["ano"] = date.today().year
            contexto["grau_risco"] = request.form.get("grau_risco", "")

            lat, lon = contexto.get("latitude"), contexto.get("longitude")
            if lat and lon:
                gerar_mapa(lat, lon, os.path.join("uploads", "mapa.png"))

            processar_laudo(contexto, "chuvas", "modelo_laudo_chuvas.docx")

            return redirect(url_for("atendimentos"))
        except Exception as e:
            return f"Erro interno: {e}", 500
    return render_template("chuvas.html", campos=campos_chuvas)

# --- Regularização ---
@app.route("/regularizacao", methods=["GET", "POST"])
def regularizacao():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        try:
            contexto = {campo[1]: request.form.get(campo[1]) for campo in campos_base}
            contexto["ano"] = date.today().year
            contexto["grau_risco"] = request.form.get("grau_risco", "")
            lat, lon = contexto.get("latitude"), contexto.get("longitude")
            if lat and lon:
                gerar_mapa(lat, lon, os.path.join("uploads", "mapa.png"))
            processar_laudo(contexto, "regularizacao", "modelo_laudo_reg.docx")
            return redirect(url_for("atendimentos"))
        except Exception as e:
            return f"Erro interno: {e}", 500
    return render_template("regularizacao.html", campos=campos_base)

# --- Incêndios ---
@app.route("/incendios", methods=["GET", "POST"])
def incendios():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        try:
            contexto = {
                "numero_laudo": request.form.get("n_ocorrencia"),
                "bairro": request.form.get("bairro"),
                "latitude": request.form.get("latitude"),
                "longitude": request.form.get("longitude"),
                "grau_risco": request.form.get("grau_risco", ""),
                "data_vistoria": request.form.get("data_vistoria")
            }
            processar_laudo(contexto, "incendios", "modelo_laudo_incendio.docx")
            return redirect(url_for("atendimentos"))
        except Exception as e:
            return f"Erro interno: {e}", 500
    return render_template("incendios.html")

# --- Atendimentos ---
@app.route("/atendimentos")
def atendimentos():
    if not session.get("logado"):
        return redirect(url_for("login"))
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
        else:
            dados = []
    except Exception as e:
        print("❌ Erro ao ler atendimentos:", e)
        dados = []
    return render_template("atendimentos.html", atendimentos=dados)

# --- Download do Laudo ---
@app.route("/download/<path:filename>")
def download(filename):
    return send_from_directory("uploads/laudos", filename, as_attachment=True)

# --- Execução ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)








































