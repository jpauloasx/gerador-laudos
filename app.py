# app.py
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_file
)
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import date, datetime
import os, json
from staticmap import StaticMap, CircleMarker

# ======================= CONFIG BASE ===========================
app = Flask(__name__)
app.secret_key = "DC_g&rad0r"

UPLOAD_FOLDER = "uploads"
DATA_FOLDER = "data"
DATA_FILE = os.path.join(DATA_FOLDER, "atendimentos.json")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

# ======================= HELPERS JSON ==========================
def carregar_atendimentos():
    """Lê o arquivo JSON de atendimentos (lista) com tolerância a erros."""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                texto = f.read().strip()
                if not texto:
                    return []
                return json.loads(texto)
        return []
    except json.JSONDecodeError:
        print("⚠️ atendimentos.json inválido/corrompido. Recriando lista vazia em memória.")
        return []
    except Exception as e:
        print(f"❌ Erro ao ler atendimentos.json: {e}")
        return []

def salvar_atendimentos(lista):
    """Grava a lista completa de atendimentos no JSON."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Erro ao salvar atendimentos.json: {e}")

def adicionar_atendimento(atendimento):
    """Adiciona um atendimento evitando duplicatas pelo numero_laudo."""
    lista = carregar_atendimentos()
    num = str(atendimento.get("numero_laudo"))
    existe = any(str(a.get("numero_laudo")) == num for a in lista)
    if existe:
        print(f"⚠️ Atendimento {num} já existe. Ignorando inclusão.")
        return
    lista.append(atendimento)
    salvar_atendimentos(lista)
    print(f"✅ Atendimento salvo: {num}")

# ======================= MAPA (StaticMap) ======================
def gerar_mapa(lat, lon, caminho_saida):
    """Gera PNG de mapa estático com marcador nas coordenadas."""
    try:
        m = StaticMap(600, 400)
        marker = CircleMarker((float(lon), float(lat)), 'red', 12)
        m.add_marker(marker)
        img = m.render(zoom=16)
        img.save(caminho_saida)
        return caminho_saida
    except Exception as e:
        print(f"❌ Erro ao gerar mapa estático: {e}")
        return None

# ======================= CAMPOS BASE ===========================
campos_base = [
    ("Nº do Laudo", "numero_laudo"),
    ("Solicitação (n° Processo, Ofício, OS, etc)", "n_processo"),
    ("Endereço (Rua, Quadra, Lote)", "endereco"),
    ("Bairro", "bairro"),
    ("Latitude", "latitude"),
    ("Longitude", "longitude"),
    ("Data da Vistoria", "data_vistoria"),
    ("Data do relatório", "data_relatorio"),
]

campos_chuvas = [
    ("Nome", "nome"),
    ("CPF", "cpf"),
    ("Telefone", "telefone"),
] + campos_base

# ======================= PROCESSAMENTO DE LAUDO ================
def processar_laudo(contexto, tipo, modelo_docx):
    """
    Gera o DOCX a partir do template, salva em uploads,
    registra o atendimento de forma persistente (JSON)
    e retorna o numero_laudo.
    """
    try:
        # Template
        doc = DocxTemplate(modelo_docx)

        # Número do laudo
        numero_laudo = (contexto.get("numero_laudo") or "").strip()
        if not numero_laudo:
            numero_laudo = datetime.now().strftime("%Y%m%d%H%M%S")
            contexto["numero_laudo"] = numero_laudo

        # Ano
        contexto["ano"] = date.today().year

        # Gerar mapa (imagem1) se tiver lat/lon
        lat, lon = contexto.get("latitude"), contexto.get("longitude")
        if lat and lon:
            caminho_mapa = os.path.join(UPLOAD_FOLDER, f"mapa_{numero_laudo}.png")
            if gerar_mapa(lat, lon, caminho_mapa):
                contexto["imagem1"] = InlineImage(doc, caminho_mapa, width=Mm(100))
                contexto["descricao1"] = "Localização Geográfica"
            else:
                contexto["imagem1"] = ""
                contexto["descricao1"] = ""
        else:
            contexto["imagem1"] = ""
            contexto["descricao1"] = ""

        # Imagens 2–7 (uploads opcionais)
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

        # Render/Salvar DOCX
        nome_arquivo = f"{tipo.capitalize()}_{numero_laudo}.docx"
        caminho_saida = os.path.join(UPLOAD_FOLDER, nome_arquivo)

        doc.render(contexto)
        doc.save(caminho_saida)
        print(f"✅ Laudo gerado: {caminho_saida}")

        # Monta e persiste o registro
        atendimento = {
            "origem": tipo.capitalize(),  # Chuvas, Regularizacao, Incendios
            "numero_laudo": numero_laudo,
            "bairro": contexto.get("bairro", ""),
            "latitude": contexto.get("latitude", ""),
            "longitude": contexto.get("longitude", ""),
            "data_vistoria": contexto.get("data_vistoria", ""),
            "grau_risco": contexto.get("grau_risco", ""),
            "arquivo": nome_arquivo,
            "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
        adicionar_atendimento(atendimento)

        return numero_laudo

    except Exception as e:
        print(f"❌ Erro ao processar laudo ({tipo}): {e}")
        return None

# ======================= AUTENTICAÇÃO ==========================
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

# ======================= PÁGINAS BÁSICAS =======================
@app.route("/home")
def home():
    if not session.get("logado"):
        return redirect(url_for("login"))
    return render_template("home.html")

@app.route("/equipes")
def equipes():
    if not session.get("logado"):
        return redirect(url_for("login"))
    # Se quiser, a qualquer momento trocamos para um template.
    return "📌 Página de Equipes (em construção)"

@app.route("/dashboard")
def dashboard():
    if not session.get("logado"):
        return redirect(url_for("login"))
    return "📊 Página de Dashboard (em construção)"

# ======================= ROTAS DE LAUDO ========================
@app.route("/chuvas", methods=["GET", "POST"])
def chuvas():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            contexto = {campo[1]: request.form.get(campo[1], "") for campo in campos_chuvas}
            contexto["grau_risco"] = request.form.get("grau_risco", "")

            numero_laudo = processar_laudo(contexto, "chuvas", "modelo_laudo_chuvas.docx")
            if not numero_laudo:
                return "Erro ao gerar laudo de Chuvas.", 500

            return redirect(url_for("atendimentos"))
        except Exception as e:
            print(f"❌ Erro /chuvas: {e}")
            return f"Erro interno: {e}", 500

    return render_template("chuvas.html", campos=campos_chuvas)

@app.route("/regularizacao", methods=["GET", "POST"])
def regularizacao():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            contexto = {campo[1]: request.form.get(campo[1], "") for campo in campos_base}
            contexto["grau_risco"] = request.form.get("grau_risco", "")

            numero_laudo = processar_laudo(contexto, "regularizacao", "modelo_laudo_reg.docx")
            if not numero_laudo:
                return "Erro ao gerar laudo de Regularização.", 500

            return redirect(url_for("atendimentos"))
        except Exception as e:
            print(f"❌ Erro /regularizacao: {e}")
            return f"Erro interno: {e}", 500

    return render_template("regularizacao.html", campos=campos_base)

@app.route("/incendios", methods=["GET", "POST"])
def incendios():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            # Para incêndios você pode ter campos diferentes; aqui lemos tudo que veio no form.
            contexto = {k: request.form.get(k, "") for k in request.form.keys()}
            # Se você quiser padronizar, pode garantir as chaves abaixo:
            contexto.setdefault("bairro", "")
            contexto.setdefault("latitude", "")
            contexto.setdefault("longitude", "")
            contexto.setdefault("data_vistoria", "")
            contexto.setdefault("grau_risco", "")

            numero_laudo = processar_laudo(contexto, "incendios", "modelo_laudo_incendio.docx")
            if not numero_laudo:
                return "Erro ao gerar laudo de Incêndios.", 500

            return redirect(url_for("atendimentos"))
        except Exception as e:
            print(f"❌ Erro /incendios: {e}")
            return f"Erro interno: {e}", 500

    return render_template("incendios.html")

# ======================= DOWNLOAD & EXCLUIR ====================
@app.route("/download/<nome_arquivo>")
def download_arquivo(nome_arquivo):
    """Baixa o DOCX salvo em /uploads."""
    try:
        caminho = os.path.join(UPLOAD_FOLDER, nome_arquivo)
        if not os.path.exists(caminho):
            return f"Arquivo {nome_arquivo} não encontrado.", 404
        return send_file(caminho, as_attachment=True)
    except Exception as e:
        print(f"❌ Erro download: {e}")
        return f"Erro ao baixar arquivo: {e}", 500

@app.route("/excluir_atendimento/<numero_laudo>", methods=["POST"])
def excluir_atendimento(numero_laudo):
    """Remove um atendimento do JSON (e mantém os arquivos, por segurança)."""
    try:
        lista = carregar_atendimentos()
        antes = len(lista)
        lista = [a for a in lista if str(a.get("numero_laudo")) != str(numero_laudo)]
        salvar_atendimentos(lista)
        depois = len(lista)
        print(f"🗑️ Excluir {numero_laudo}: {antes} -> {depois} registros.")
        return redirect(url_for("atendimentos"))
    except Exception as e:
        print(f"❌ Erro excluir_atendimento: {e}")
        return "Erro ao excluir atendimento.", 500

# ======================= LISTAGEM / MAPA =======================
@app.route("/atendimentos")
def atendimentos():
    if not session.get("logado"):
        return redirect(url_for("login"))

    lista = carregar_atendimentos()
    # Passa a lista normal e também serializada para o JS do Leaflet
    return render_template(
        "atendimentos.html",
        atendimentos=lista,
        atendimentos_json=json.dumps(lista, ensure_ascii=False)
    )

# ======================= RUN ================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)








































