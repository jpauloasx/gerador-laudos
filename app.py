from flask import (
    Flask, render_template, request, redirect, url_for, session, send_file
)
from flask_sqlalchemy import SQLAlchemy
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import date, datetime
from staticmap import StaticMap, CircleMarker
import os

# ==========================================================
# CONFIGURAÇÕES INICIAIS
# ==========================================================
app = Flask(__name__)
app.secret_key = "DC_g&rad0r"

# Diretórios
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Banco de dados SQLite
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "atendimentos.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
os.makedirs("data", exist_ok=True)

db = SQLAlchemy(app)

# ==========================================================
# MODELO DE BANCO DE DADOS
# ==========================================================
class Atendimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origem = db.Column(db.String(50))
    numero_laudo = db.Column(db.String(50), unique=True)
    bairro = db.Column(db.String(100))
    latitude = db.Column(db.String(50))
    longitude = db.Column(db.String(50))
    data_vistoria = db.Column(db.String(50))
    grau_risco = db.Column(db.String(50))
    arquivo = db.Column(db.String(200))
    data_registro = db.Column(db.String(50))

with app.app_context():
    db.create_all()

# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================
def gerar_mapa(lat, lon, caminho_saida):
    """Gera imagem de mapa a partir de latitude e longitude."""
    try:
        m = StaticMap(600, 400)
        marker = CircleMarker((float(lon), float(lat)), 'red', 12)
        m.add_marker(marker)
        image = m.render(zoom=16)
        image.save(caminho_saida)
        return caminho_saida
    except Exception as e:
        print(f"❌ Erro ao gerar mapa: {e}")
        return None


def salvar_no_banco(contexto, tipo, nome_arquivo):
    """Salva o atendimento no banco de dados SQLite."""
    try:
        numero_laudo = contexto.get("numero_laudo")
        existente = Atendimento.query.filter_by(numero_laudo=numero_laudo).first()
        if existente:
            print(f"⚠️ Laudo {numero_laudo} já existe no banco.")
            return

        novo = Atendimento(
            origem=tipo.capitalize(),
            numero_laudo=numero_laudo,
            bairro=contexto.get("bairro", ""),
            latitude=contexto.get("latitude", ""),
            longitude=contexto.get("longitude", ""),
            data_vistoria=contexto.get("data_vistoria", ""),
            grau_risco=contexto.get("grau_risco", ""),
            arquivo=nome_arquivo,
            data_registro=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        )
        db.session.add(novo)
        db.session.commit()
        print(f"✅ Atendimento {numero_laudo} salvo com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao salvar no banco: {e}")


def processar_laudo(contexto, tipo, modelo_docx):
    """Gera o DOCX e registra o atendimento no banco."""
    try:
        doc = DocxTemplate(modelo_docx)
        numero_laudo = contexto.get("numero_laudo") or datetime.now().strftime("%Y%m%d%H%M%S")
        contexto["numero_laudo"] = numero_laudo
        contexto["ano"] = date.today().year

        # Gera mapa se houver coordenadas
        lat, lon = contexto.get("latitude"), contexto.get("longitude")
        if lat and lon:
            caminho_mapa = os.path.join(UPLOAD_FOLDER, f"mapa_{numero_laudo}.png")
            gerar_mapa(lat, lon, caminho_mapa)
            contexto["imagem1"] = InlineImage(doc, caminho_mapa, width=Mm(100))
            contexto["descricao1"] = "Localização Geográfica"
        else:
            contexto["imagem1"] = ""
            contexto["descricao1"] = ""

        # Imagens adicionais (2–7)
        for i in range(2, 8):
            arquivo = request.files.get(f"imagem{i}")
            desc = request.form.get(f"descricao{i}", "")
            contexto[f"descricao{i}"] = desc

            if arquivo and arquivo.filename:
                caminho = os.path.join(UPLOAD_FOLDER, f"{tipo}_img{i}_{numero_laudo}.jpg")
                arquivo.save(caminho)
                contexto[f"imagem{i}"] = InlineImage(doc, caminho, width=Mm(100))
            else:
                contexto[f"imagem{i}"] = ""

        # Gera e salva o documento
        nome_arquivo = f"{tipo.capitalize()}_{numero_laudo}.docx"
        caminho_saida = os.path.join(UPLOAD_FOLDER, nome_arquivo)
        doc.render(contexto)
        doc.save(caminho_saida)

        # Registra no banco
        salvar_no_banco(contexto, tipo, nome_arquivo)

        return numero_laudo
    except Exception as e:
        print(f"❌ Erro ao processar laudo ({tipo}): {e}")
        return None

# ==========================================================
# AUTENTICAÇÃO
# ==========================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username")
        pw = request.form.get("password")
        if user == "defesacivil" and pw == "DC_g&rad0r":
            session["logado"] = True
            return redirect(url_for("home"))
        else:
            return render_template("login.html", erro="Usuário ou senha incorretos.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logado", None)
    return redirect(url_for("login"))

# ==========================================================
# ROTAS PRINCIPAIS
# ==========================================================
@app.route("/home")
def home():
    if not session.get("logado"):
        return redirect(url_for("login"))
    return render_template("home.html")

@app.route("/equipes")
def equipes():
    if not session.get("logado"):
        return redirect(url_for("login"))
    return "📋 Página de Equipes (em construção)"

@app.route("/dashboard")
def dashboard():
    if not session.get("logado"):
        return redirect(url_for("login"))
    return "📊 Página de Dashboard (em construção)"

# ==========================================================
# ROTAS DE LAUDOS
# ==========================================================
campos_base = [
    ("Nº do Laudo", "numero_laudo"),
    ("Solicitação (n° Processo, Ofício, OS, etc)", "n_processo"),
    ("Endereço (Rua, Quadra, Lote)", "endereco"),
    ("Bairro", "bairro"),
    ("Latitude", "latitude"),
    ("Longitude", "longitude"),
    ("Data da Vistoria", "data_vistoria"),
    ("Data do relatório", "data_relatorio")
]

campos_chuvas = [
    ("Nome", "nome"),
    ("CPF", "cpf"),
    ("Telefone", "telefone")
] + campos_base


@app.route("/chuvas", methods=["GET", "POST"])
def chuvas():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        contexto = {campo[1]: request.form.get(campo[1], "") for campo in campos_chuvas}
        contexto["grau_risco"] = request.form.get("grau_risco", "")
        processar_laudo(contexto, "chuvas", "modelo_laudo_chuvas.docx")
        return redirect(url_for("atendimentos"))
    return render_template("chuvas.html", campos=campos_chuvas)


@app.route("/regularizacao", methods=["GET", "POST"])
def regularizacao():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        contexto = {campo[1]: request.form.get(campo[1], "") for campo in campos_base}
        contexto["grau_risco"] = request.form.get("grau_risco", "")
        processar_laudo(contexto, "regularizacao", "modelo_laudo_reg.docx")
        return redirect(url_for("atendimentos"))
    return render_template("regularizacao.html", campos=campos_base)


@app.route("/incendios", methods=["GET", "POST"])
def incendios():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        contexto = {k: request.form.get(k, "") for k in request.form.keys()}
        contexto.setdefault("grau_risco", "")
        processar_laudo(contexto, "incendios", "modelo_laudo_incendio.docx")
        return redirect(url_for("atendimentos"))
    return render_template("incendios.html")

# ==========================================================
# ROTAS DE DOWNLOAD E EXCLUSÃO
# ==========================================================
@app.route("/download/<nome_arquivo>")
def download_arquivo(nome_arquivo):
    try:
        caminho = os.path.join(UPLOAD_FOLDER, nome_arquivo)
        if os.path.exists(caminho):
            return send_file(caminho, as_attachment=True)
        return "Arquivo não encontrado", 404
    except Exception as e:
        return f"Erro ao baixar arquivo: {e}", 500


@app.route("/excluir_atendimento/<numero_laudo>", methods=["POST"])
def excluir_atendimento(numero_laudo):
    try:
        atendimento = Atendimento.query.filter_by(numero_laudo=numero_laudo).first()
        if atendimento:
            db.session.delete(atendimento)
            db.session.commit()
            print(f"🗑️ Atendimento {numero_laudo} removido do banco.")
        return redirect(url_for("atendimentos"))
    except Exception as e:
        print(f"❌ Erro ao excluir: {e}")
        return "Erro ao excluir atendimento", 500

# ==========================================================
# PÁGINA DE ATENDIMENTOS (MAPA + TABELA)
# ==========================================================
@app.route("/atendimentos")
def atendimentos():
    if not session.get("logado"):
        return redirect(url_for("login"))
    lista = Atendimento.query.all()
    dados_json = [
        {
            "origem": a.origem,
            "numero_laudo": a.numero_laudo,
            "bairro": a.bairro,
            "latitude": a.latitude,
            "longitude": a.longitude,
            "data_vistoria": a.data_vistoria,
            "grau_risco": a.grau_risco,
            "arquivo": a.arquivo,
            "data_registro": a.data_registro,
        } for a in lista
    ]
    import json
    return render_template("atendimentos.html", atendimentos=lista, atendimentos_json=json.dumps(dados_json, ensure_ascii=False))

# ==========================================================
# EXECUÇÃO
# ==========================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)










































