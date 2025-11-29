from flask import (
    Flask, render_template, request, redirect, url_for, session, send_file, jsonify
)
import requests
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import date, datetime
from staticmap import StaticMap, CircleMarker
from github import Github
import base64
import os, json

# Lista em memória para armazenar alertas emitidos
alertas_enviados = []

# ==========================================================
# CONFIG BÁSICA
# ==========================================================
app = Flask(__name__)
app.secret_key = "DC_g&rad0r"


# Config WhatsApp Cloud API (Meta)
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "SEU_TOKEN_AQUI")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "SEU_PHONE_NUMBER_ID")
WHATSAPP_API_VERSION = "v21.0"  # ou a versão que você estiver usando

# Arquivo com a lista de números que receberão os alertas
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
TELEFONES_ALERTA_FILE = os.path.join(DATA_DIR, "telefones_alerta.json")

# Paths efêmeros (Render permite /tmp com escrita)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TMP_DIR = "/tmp"
UPLOAD_FOLDER = os.path.join(TMP_DIR, "uploads")
DATA_DIR = TMP_DIR  # manter o json no /tmp
DATA_FILE = os.path.join(DATA_DIR, "atendimentos.json")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ==========================================================
# CONFIG GITHUB
# ==========================================================
# Repositório destino (SEM /tree/main)
GITHUB_REPO = "jpauloasx/gerador-laudos"
GITHUB_BRANCH = "main"
GITHUB_UPLOADS_PATH = "uploads"  # pasta no repo para DOCX
GITHUB_DATA_PATH = "data/atendimentos.json"  # histórico no repo

def _get_github():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("⚠️  GITHUB_TOKEN ausente. Subida para GitHub será ignorada.")
        return None
    try:
        gh = Github(token)
        repo = gh.get_repo(GITHUB_REPO)
        return repo
    except Exception as e:
        print(f"❌ Erro ao autenticar no GitHub: {e}")
        return None

def upload_or_update_github_file(repo, remote_path, binary_content, message):
    """
    Cria/atualiza um arquivo no GitHub (branch main) com conteúdo binário (bytes).
    """
    if not repo:
        return False
    try:
        # Tenta buscar o arquivo para decidir se cria ou atualiza
        try:
            file = repo.get_contents(remote_path, ref=GITHUB_BRANCH)
            repo.update_file(
                path=file.path,
                message=message,
                content=binary_content,
                sha=file.sha,
                branch=GITHUB_BRANCH
            )
            print(f"♻️ Atualizado no GitHub: {remote_path}")
        except Exception:
            repo.create_file(
                path=remote_path,
                message=message,
                content=binary_content,
                branch=GITHUB_BRANCH
            )
            print(f"📤 Criado no GitHub: {remote_path}")
        return True
    except Exception as e:
        print(f"❌ Falha ao enviar {remote_path} para GitHub: {e}")
        return False

def fetch_github_json(remote_path):
    """
    Busca um JSON no GitHub e retorna o objeto (lista/dict).
    Se não existir, retorna [].
    """
    repo = _get_github()
    if not repo:
        return []
    try:
        file = repo.get_contents(remote_path, ref=GITHUB_BRANCH)
        content = base64.b64decode(file.content).decode("utf-8")
        return json.loads(content) if content.strip() else []
    except Exception as e:
        print(f"⚠️  Não foi possível ler {remote_path} do GitHub: {e}")
        return []

def github_raw_url(remote_path):
    """
    Monta URL raw do GitHub para download direto.
    Ex: uploads/Chuvas_20251010112233.docx
    """
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{remote_path}"

# ==========================================================
# FUNÇÕES AUXILIARES (MAPA e JSON local + GitHub)
# ==========================================================
def gerar_mapa(lat, lon, caminho_saida):
    """Gera imagem PNG de mapa estático com marcador nas coordenadas."""
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

def carregar_atendimentos_local():
    """Tenta ler o JSON de atendimentos do /tmp."""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                txt = f.read().strip()
                return json.loads(txt) if txt else []
        return []
    except Exception as e:
        print(f"⚠️  Erro ao ler {DATA_FILE}: {e}")
        return []

def salvar_atendimentos_local(lista):
    """Grava a lista no /tmp (cache local)."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Erro ao salvar {DATA_FILE}: {e}")

def carregar_atendimentos():
    """
    Carrega atendimentos para exibir no painel:
    1) Tenta usar o cache local (/tmp/atendimentos.json)
    2) Se não houver, lê do GitHub (data/atendimentos.json) e salva cache.
    """
    lista = carregar_atendimentos_local()
    if lista:
        return lista
    # cache vazio -> lê do GitHub
    lista = fetch_github_json(GITHUB_DATA_PATH)
    if lista:
        salvar_atendimentos_local(lista)  # popula o cache
    return lista

def adicionar_atendimento_e_sincronizar(atendimento):
    """
    Adiciona atendimento:
    - Atualiza cache local /tmp/atendimentos.json
    - Sobe o JSON atualizado pro GitHub (data/atendimentos.json)
    """
    # 1) lê existente (local ou GitHub)
    lista = carregar_atendimentos()
    num = str(atendimento.get("numero_laudo"))
    if any(str(a.get("numero_laudo")) == num for a in lista):
        print(f"⚠️ Atendimento {num} já existe. Ignorando duplicado.")
        return

    # 2) adiciona e salva local
    lista.append(atendimento)
    salvar_atendimentos_local(lista)

    # 3) envia JSON pro GitHub
    repo = _get_github()
    try:
        json_bytes = json.dumps(lista, ensure_ascii=False, indent=2).encode("utf-8")
        ok = upload_or_update_github_file(repo, GITHUB_DATA_PATH, json_bytes, "Atualização de atendimentos")
        if ok:
            print("✅ atendimentos.json sincronizado no GitHub")
    except Exception as e:
        print(f"❌ Erro ao enviar atendimentos.json: {e}")

def carregar_telefones_alerta():
    """Lê a lista de telefones que receberão os alertas de WhatsApp."""
    if not os.path.exists(TELEFONES_ALERTA_FILE):
        # Se não existir, retorna lista vazia (ou você pode retornar um exemplo)
        return []

    try:
        with open(TELEFONES_ALERTA_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
            # Garante que seja uma lista de strings
            if isinstance(dados, list):
                return [str(t).strip() for t in dados if str(t).strip()]
            return []
    except Exception as e:
        print(f"❌ Erro ao ler telefones_alerta.json: {e}")
        return []

# ==========================================================
# CAMPOS E PROCESSAMENTO DE LAUDO
# ==========================================================
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

def processar_laudo(contexto, tipo, modelo_docx):
    """
    Gera DOCX em /tmp/uploads, faz upload p/ GitHub (uploads/),
    registra/atualiza data/atendimentos.json no GitHub.
    """
    try:
        doc = DocxTemplate(modelo_docx)

        numero_laudo = (contexto.get("numero_laudo") or "").strip()
        if not numero_laudo:
            numero_laudo = datetime.now().strftime("%Y%m%d%H%M%S")
            contexto["numero_laudo"] = numero_laudo

        contexto["ano"] = date.today().year

        # Mapa (imagem1)
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

        # Renderiza DOCX local
        nome_arquivo = f"{tipo.capitalize()}_{numero_laudo}.docx"
        caminho_saida = os.path.join(UPLOAD_FOLDER, nome_arquivo)
        doc.render(contexto)
        doc.save(caminho_saida)
        print(f"✅ Laudo gerado local: {caminho_saida}")

        # === Upload DOCX para GitHub (uploads/) ===
        repo = _get_github()
        try:
            with open(caminho_saida, "rb") as f:
                content = f.read()
            remote_path = f"{GITHUB_UPLOADS_PATH}/{nome_arquivo}"
            ok = upload_or_update_github_file(
                repo, remote_path, content, f"Laudo {numero_laudo} - {tipo.capitalize()}"
            )
            if ok:
                print(f"✅ DOCX sincronizado no GitHub: {remote_path}")
        except Exception as e:
            print(f"❌ Erro ao enviar DOCX p/ GitHub: {e}")

        # === Registra atendimento e sincroniza JSON no GitHub ===
        atendimento = {
            "origem": tipo.capitalize(),
            "numero_laudo": numero_laudo,
            "bairro": contexto.get("bairro", ""),
            "latitude": contexto.get("latitude", ""),
            "longitude": contexto.get("longitude", ""),
            "data_vistoria": contexto.get("data_vistoria", ""),
            "grau_risco": contexto.get("grau_risco", ""),
            "arquivo": nome_arquivo,
            "arquivo_github": f"https://github.com/{GITHUB_REPO}/blob/{GITHUB_BRANCH}/{remote_path}",
            "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
        adicionar_atendimento_e_sincronizar(atendimento)

        return numero_laudo

    except Exception as e:
        print(f"❌ Erro ao processar laudo ({tipo}): {e}")
        return None

# ==========================================================
# AUTENTICAÇÃO E PÁGINAS BÁSICAS
# ==========================================================
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

@app.route("/equipes", methods=["GET", "POST"])
def equipes():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        # Aqui pode salvar equipe no banco ou JSON
        nome = request.form.get("nome")
        matricula = request.form.get("matricula")
        funcao = request.form.get("funcao")
        print(f"👨‍🚒 Nova equipe cadastrada: {nome} ({funcao})")
    return render_template("equipes.html")

@app.route("/viaturas", methods=["GET", "POST"])
def viaturas():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        tipo = request.form.get("tipo")
        marca = request.form.get("marca")
        modelo = request.form.get("modelo")
        prefixo = request.form.get("prefixo")
        placa = request.form.get("placa")
        print(f"🚓 Nova viatura cadastrada: {prefixo} - {placa}")
    return render_template("viaturas.html")

@app.route("/alerta", methods=["GET", "POST"])
def alerta():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        # Campos básicos do alerta – podemos refinar depois
        tipo = request.form.get("tipo", "Chuvas")
        titulo = request.form.get("titulo", "").strip()
        mensagem = request.form.get("mensagem", "").strip()
        regiao = request.form.get("regiao", "").strip()
        chuva_mm = request.form.get("chuva_mm", "").strip()
        validade = request.form.get("validade", "").strip()  # data/hora fim do alerta
        temperatura = request.form.get("temperatura", "").strip()
        umidade = request.form.get("umidade", "").strip()

        alerta_data = {
            "tipo": tipo,
            "titulo": titulo or f"Alerta de {tipo}",
            "mensagem": mensagem,
            "regiao": regiao,
            "chuva_mm": chuva_mm,
            "temperatura": temperatura,
            "umidade": umidade,
            "validade": validade,
            "data_emissao": datetime.now().strftime("%d/%m/%Y %H:%M")
            }


        # Guarda em memória por enquanto
        alertas_enviados.append(alerta_data)

        # Depois, quando integrar WhatsApp, é aqui que vamos disparar a mensagem
        # (ex: chamar função enviar_alerta_whatsapp(alerta_data))

        return render_template("alerta.html", alerta_emitido=True, alertas=alertas_enviados)

    # GET – só mostra a tela de emissão
    return render_template("alerta.html", alerta_emitido=False, alertas=alertas_enviados)

@app.route("/dashboard")
def dashboard():
    if not session.get("logado"):
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app.route("/painel")
def painel():
    if not session.get("logado"):
        return redirect(url_for("login"))
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            atendimentos = json.load(f)
    except Exception:
        atendimentos = []
    return render_template("painel.html", atendimentos=atendimentos)

@app.route("/painel_dados")
def painel_dados():
    """Retorna os atendimentos em JSON para atualização automática do mapa"""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            atendimentos = json.load(f)
    except Exception:
        atendimentos = []
    return jsonify(atendimentos)


# ==========================================================
# ROTAS DE LAUDO
# ==========================================================
@app.route("/chuvas", methods=["GET", "POST"])
def chuvas():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        contexto = {campo[1]: request.form.get(campo[1], "") for campo in campos_chuvas}
        contexto["grau_risco"] = request.form.get("grau_risco", "")

        numero = processar_laudo(contexto, "chuvas", "modelo_laudo_chuvas.docx")
        if not numero:
            return "Erro ao gerar laudo de Chuvas.", 500
        return redirect(url_for("atendimentos"))

    return render_template("chuvas.html", campos=campos_chuvas)

@app.route("/regularizacao", methods=["GET", "POST"])
def regularizacao():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        contexto = {campo[1]: request.form.get(campo[1], "") for campo in campos_base}
        contexto["grau_risco"] = request.form.get("grau_risco", "")

        numero = processar_laudo(contexto, "regularizacao", "modelo_laudo_reg.docx")
        if not numero:
            return "Erro ao gerar laudo de Regularização.", 500
        return redirect(url_for("atendimentos"))

    return render_template("regularizacao.html", campos=campos_base)

@app.route("/incendios", methods=["GET", "POST"])
def incendios():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        # Para incêndios, leia tudo do form; garanta chaves mínimas:
        contexto = {k: request.form.get(k, "") for k in request.form.keys()}
        for key in ["bairro", "latitude", "longitude", "data_vistoria", "grau_risco"]:
            contexto.setdefault(key, "")

        numero = processar_laudo(contexto, "incendios", "modelo_laudo_incendio.docx")
        if not numero:
            return "Erro ao gerar laudo de Incêndios.", 500
        return redirect(url_for("atendimentos"))

    return render_template("incendios.html")

# ==========================================================
# LISTAGEM / MAPA / DOWNLOAD / EXCLUIR / INSERIR 
# ==========================================================
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

@app.route("/download/<nome_arquivo>")
def download_arquivo(nome_arquivo):
    """
    Redireciona para o RAW do GitHub (baixa direto do repositório).
    """
    remote_path = f"{GITHUB_UPLOADS_PATH}/{nome_arquivo}"
    return redirect(github_raw_url(remote_path))

@app.route("/excluir_atendimento/<numero_laudo>", methods=["POST"])
def excluir_atendimento(numero_laudo):
    """
    Remove o atendimento do cache local e do JSON no GitHub.
    (NÃO remove o DOCX do GitHub para manter histórico — podemos mudar se quiser.)
    """
    try:
        lista = carregar_atendimentos()
        nova = [a for a in lista if str(a.get("numero_laudo")) != str(numero_laudo)]
        salvar_atendimentos_local(nova)

        # Sincroniza JSON atualizado no GitHub
        repo = _get_github()
        json_bytes = json.dumps(nova, ensure_ascii=False, indent=2).encode("utf-8")
        upload_or_update_github_file(repo, GITHUB_DATA_PATH, json_bytes, f"Remoção {numero_laudo}")

        print(f"🗑️ Atendimento {numero_laudo} removido do painel/JSON.")
        return redirect(url_for("atendimentos"))

    except Exception as e:
        print(f"❌ Erro ao excluir {numero_laudo}: {e}")
        return "Erro ao excluir atendimento.", 500

@app.route("/inserir_atendimento", methods=["POST"])
def inserir_atendimento():
    """
    Insere manualmente um atendimento já realizado (sem gerar laudo).
    """
    try:
        dados = request.get_json()
        numero_laudo = dados.get("numero_laudo", "").strip()
        if not numero_laudo:
            return "Número de laudo obrigatório.", 400

        atendimento = {
            "origem": dados.get("origem", "Manual"),
            "numero_laudo": numero_laudo,
            "bairro": dados.get("bairro", ""),
            "latitude": dados.get("latitude", ""),
            "longitude": dados.get("longitude", ""),
            "data_vistoria": dados.get("data_vistoria", ""),
            "grau_risco": dados.get("grau_risco", ""),
            "arquivo": "",
            "arquivo_github": "",
            "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }

        adicionar_atendimento_e_sincronizar(atendimento)
        return {"status": "ok"}, 200

    except Exception as e:
        print(f"❌ Erro ao inserir atendimento manual: {e}")
        return "Erro interno.", 500


# ==========================================================
# RUN
# ==========================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)























































