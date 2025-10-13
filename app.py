from flask import Flask, render_template, request, redirect, url_for, session, send_file
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import date, datetime
import os, json
from staticmap import StaticMap, CircleMarker

app = Flask(__name__)
app.secret_key = "DC_g&rad0r"

UPLOAD_FOLDER = "uploads"
DATA_FOLDER = "data"
DATA_FILE = os.path.join(DATA_FOLDER, "atendimentos.json")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

# ======================== UTILITÁRIOS ==========================

def gerar_mapa(lat, lon, caminho_saida):
    """Gera imagem de mapa com marcador de latitude/longitude"""
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


def carregar_atendimentos():
    """Lê o arquivo JSON de atendimentos"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except json.JSONDecodeError:
        print("⚠️ Arquivo JSON corrompido, recriando...")
        return []


def salvar_atendimentos(lista):
    """Grava a lista completa de atendimentos"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Erro ao salvar atendimentos: {e}")


def adicionar_atendimento(atendimento):
    """Adiciona um novo atendimento sem duplicar"""
    lista = carregar_atendimentos()
    ja_existe = any(a.get("numero_laudo") == atendimento.get("numero_laudo") for a in lista)
    if not ja_existe:
        lista.append(atendimento)
        salvar_atendimentos(lista)
        print(f"✅ Atendimento salvo: {atendimento['numero_laudo']}")
    else:
        print(f"⚠️ Atendimento {atendimento['numero_laudo']} já existente, ignorando.")

# ======================== PROCESSADOR DE LAUDOS ==========================

def processar_laudo(contexto, tipo, modelo_docx):
    """Gera o arquivo DOCX, salva e registra no JSON"""
    try:
        doc = DocxTemplate(modelo_docx)

        numero_laudo = contexto.get("numero_laudo") or datetime.now().strftime("%Y%m%d%H%M%S")
        contexto["numero_laudo"] = numero_laudo
        contexto["ano"] = date.today().year

        lat, lon = contexto.get("latitude"), contexto.get("longitude")
        if lat and lon:
            caminho_mapa = os.path.join(UPLOAD_FOLDER, f"mapa_{numero_laudo}.png")
            gerar_mapa(lat, lon, caminho_mapa)
            contexto["imagem1"] = InlineImage(doc, caminho_mapa, width=Mm(100))
            contexto["descricao1"] = "Localização Geográfica"
        else:
            contexto["imagem1"] = ""
            contexto["descricao1"] = ""

        # Imagens 2–7
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

        # Salva documento
        nome_arquivo = f"{tipo.capitalize()}_{numero_laudo}.docx"
        caminho_saida = os.path.join(UPLOAD_FOLDER, nome_arquivo)
        doc.render(contexto)
        doc.save(caminho_saida)

        # Registra atendimento
        atendimento = {
            "origem": tipo.capitalize(),
            "numero_laudo": numero_laudo,
            "bairro": contexto.get("bairro"),
            "latitude": contexto.get("latitude"),
            "longitude": contexto.get("longitude"),
            "data_vistoria": contexto.get("data_vistoria"),
            "grau_risco": contexto.get("grau_risco"),
            "arquivo": nome_arquivo,
            "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }

        adicionar_atendimento(atendimento)
        return numero_laudo

    except Exception as e:
        print(f"❌ Erro ao processar laudo: {e}")
        return None


# ======================== ROTAS DO SISTEMA ==========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username")
        pw = request.form.get("password")
        if user == "defesacivil" and pw == "DC_g&rad0r":
            session["logado"] = True
            return redirect(url_for("home"))
        return render_template("login.html", erro="Usuário ou senha incorretos.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logado", None)
    return redirect(url_for("login"))


@app.route("/home")
def home():
    if not session.get("logado"):
        return redirect(url_for("login"))
    return render_template("home.html")


# Campos comuns
campos_base = [
    ("Nº do Laudo", "numero_laudo"),
    ("Solicitação (n° Processo, Ofício, OS, etc)", "n_processo"),
    ("Endereço", "endereco"),
    ("Bairro", "bairro"),
    ("Latitude", "latitude"),
    ("Longitude", "longitude"),
    ("Data da Vistoria", "data_vistoria"),
    ("Data do relatório", "data_relatorio"),
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
        contexto = {campo[1]: request.form.get(campo[1]) for campo in campos_chuvas}
        contexto["grau_risco"] = request.form.get("grau_risco")
        processar_laudo(contexto, "chuvas", "modelo_laudo_chuvas.docx")
        return redirect(url_for("atendimentos"))
    return render_template("chuvas.html", campos=campos_chuvas)


@app.route("/regularizacao", methods=["GET", "POST"])
def regularizacao():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        contexto = {campo[1]: request.form.get(campo[1]) for campo in campos_base}
        contexto["grau_risco"] = request.form.get("grau_risco")
        processar_laudo(contexto, "regularizacao", "modelo_laudo_reg.docx")
        return redirect(url_for("atendimentos"))
    return render_template("regularizacao.html", campos=campos_base)


@app.route("/incendios", methods=["GET", "POST"])
def incendios():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        contexto = {key: request.form.get(key) for key in request.form.keys()}
        processar_laudo(contexto, "incendios", "modelo_laudo_incendio.docx")
        return redirect(url_for("atendimentos"))
    return render_template("incendios.html")


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
    lista = carregar_atendimentos()
    nova_lista = [a for a in lista if a.get("numero_laudo") != numero_laudo]
    salvar_atendimentos(nova_lista)
    print(f"🗑️ Atendimento {numero_laudo} removido.")
    return redirect(url_for("atendimentos"))


@app.route("/atendimentos")
def atendimentos():
    if not session.get("logado"):
        return redirect(url_for("login"))
    lista = carregar_atendimentos()
    return render_template(
        "atendimentos.html",
        atendimentos=lista,
        atendimentos_json=json.dumps(lista, ensure_ascii=False)
    )


@app.route("/dashboard")
def dashboard():
    return "📊 Dashboard em desenvolvimento"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)





















































