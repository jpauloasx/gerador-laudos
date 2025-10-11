from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import date, datetime
import os, json
from staticmap import StaticMap, CircleMarker 

app = Flask(__name__)
app.secret_key = "DC_g&rad0r"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATA_FILE = "data/atendimentos.json"
os.makedirs("data", exist_ok=True)


# =====================================================
# 🔹 Funções auxiliares
# =====================================================
def salvar_atendimento(atendimento):
    """Salva o registro do atendimento em atendimentos.json"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
        else:
            dados = []

        dados.append(atendimento)

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

        print(f"✅ Atendimento salvo: {atendimento.get('numero_laudo', 'sem número')}")
    except Exception as e:
        print(f"❌ Erro ao salvar atendimento: {e}")


def gerar_mapa(lat, lon, caminho_saida):
    """Gera imagem de mapa estático com marcador"""
    try:
        m = StaticMap(600, 400)
        marker = CircleMarker((float(lon), float(lat)), 'red', 12)
        m.add_marker(marker)
        image = m.render(zoom=16)
        image.save(caminho_saida)
        return caminho_saida
    except Exception as e:
        print(f"❌ Erro ao gerar mapa OSM: {e}")
        return None


def processar_laudo(contexto, tipo, modelo_docx):
    """Gera o arquivo DOCX e salva no diretório uploads"""
    try:
        doc = DocxTemplate(modelo_docx)
        os.makedirs("uploads", exist_ok=True)

        # Número do laudo (gera automático se vazio)
        numero_laudo = contexto.get("numero_laudo")
        if not numero_laudo or numero_laudo.strip() == "":
            numero_laudo = datetime.now().strftime("%Y%m%d%H%M%S")
            contexto["numero_laudo"] = numero_laudo

        # Mapa
        lat, lon = contexto.get("latitude"), contexto.get("longitude")
        if lat and lon:
            caminho_mapa = os.path.join("uploads", f"mapa_{numero_laudo}.png")
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
                caminho = os.path.join("uploads", f"{tipo}_img{i}_{numero_laudo}.jpg")
                arquivo.save(caminho)
                contexto[f"imagem{i}"] = InlineImage(doc, caminho, width=Mm(100))
            else:
                contexto[f"imagem{i}"] = ""

        # Finaliza documento
        contexto["ano"] = date.today().year
        nome_arquivo = f"{tipo.capitalize()}_{numero_laudo}.docx"
        caminho_saida = os.path.join("uploads", nome_arquivo)
        doc.render(contexto)
        doc.save(caminho_saida)

        print(f"✅ Laudo gerado: {caminho_saida}")
        return numero_laudo

    except Exception as e:
        print(f"❌ Erro ao processar laudo ({tipo}): {e}")
        return None


# =====================================================
# 🔹 Login / Sessão
# =====================================================
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


@app.route("/logout")
def logout():
    session.pop("logado", None)
    return redirect(url_for("login"))


@app.route("/home")
def home():
    if not session.get("logado"):
        return redirect(url_for("login"))
    return render_template("home.html")


# =====================================================
# 🔹 Campos
# =====================================================
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


# =====================================================
# 🔹 Rotas principais
# =====================================================
@app.route("/chuvas", methods=["GET", "POST"])
def chuvas():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            contexto = {campo[1]: request.form.get(campo[1], "") for campo in campos_chuvas}
            contexto["ano"] = date.today().year
            contexto["grau_risco"] = request.form.get("grau_risco", "")

            numero_laudo = processar_laudo(contexto, "chuvas", "modelo_laudo_chuvas.docx")

            if numero_laudo:
                atendimento = {
                    "origem": "Chuvas",
                    "numero_laudo": numero_laudo,
                    "bairro": contexto.get("bairro", ""),
                    "latitude": contexto.get("latitude", ""),
                    "longitude": contexto.get("longitude", ""),
                    "data_vistoria": contexto.get("data_vistoria", ""),
                    "grau_risco": contexto.get("grau_risco", ""),
                    "arquivo": f"Chuvas_{numero_laudo}.docx",
                    "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M")
                }

                # Garante que o arquivo JSON existe
                os.makedirs("data", exist_ok=True)
                if not os.path.exists(DATA_FILE):
                    with open(DATA_FILE, "w", encoding="utf-8") as f:
                        json.dump([], f, ensure_ascii=False, indent=2)

                # Salva o atendimento
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    dados = json.load(f)

                dados.append(atendimento)

                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(dados, f, ensure_ascii=False, indent=2)

                print(f"✅ Atendimento salvo no JSON: {atendimento}")

                return redirect(url_for("atendimentos"))
            else:
                return "Erro ao gerar o laudo", 500

        except Exception as e:
            print(f"❌ Erro interno em /chuvas: {e}")
            return f"Erro interno: {e}", 500

    return render_template("chuvas.html", campos=campos_chuvas)



@app.route("/regularizacao", methods=["GET", "POST"])
def regularizacao():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        try:
            contexto = {campo[1]: request.form.get(campo[1]) for campo in campos_base}
            contexto["grau_risco"] = request.form.get("grau_risco", "")

            numero_laudo = processar_laudo(contexto, "regularizacao", "modelo_laudo_reg.docx")

            if numero_laudo:
                salvar_atendimento({
                    "origem": "Regularização Fundiária",
                    "numero_laudo": numero_laudo,
                    "bairro": contexto.get("bairro"),
                    "latitude": contexto.get("latitude"),
                    "longitude": contexto.get("longitude"),
                    "data_vistoria": contexto.get("data_vistoria"),
                    "grau_risco": contexto.get("grau_risco"),
                    "arquivo": f"uploads/Regularizacao_{numero_laudo}.docx",
                    "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M")
                })

            return redirect(url_for("atendimentos"))

        except Exception as e:
            return f"Erro interno: {e}", 500
    return render_template("regularizacao.html", campos=campos_base)


@app.route("/incendios", methods=["GET", "POST"])
def incendios():
    if not session.get("logado"):
        return redirect(url_for("login"))
    if request.method == "POST":
        try:
            contexto = {
                "n_os": request.form.get("n_os"),
                "origem_ocorrencia": request.form.get("origem_ocorrencia"),
                "n_ocorrencia": request.form.get("n_ocorrencia"),
                "bairro": request.form.get("bairro"),
                "descricao": request.form.get("descricao"),
                "data_vistoria": request.form.get("data_vistoria")
            }

            numero_laudo = processar_laudo(contexto, "incendios", "modelo_laudo_incendio.docx")

            if numero_laudo:
                salvar_atendimento({
                    "origem": "Incêndios",
                    "numero_laudo": numero_laudo,
                    "bairro": contexto.get("bairro"),
                    "latitude": contexto.get("latitude", ""),
                    "longitude": contexto.get("longitude", ""),
                    "data_vistoria": contexto.get("data_vistoria"),
                    "grau_risco": contexto.get("grau_risco", ""),
                    "arquivo": f"uploads/Incendios_{numero_laudo}.docx",
                    "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M")
                })

            return redirect(url_for("atendimentos"))

        except Exception as e:
            return f"Erro interno: {e}", 500
    return render_template("incendios.html")


# =====================================================
# 🔹 Outras páginas
# =====================================================
@app.route("/atendimentos")
def atendimentos():
    if not session.get("logado"):
        return redirect(url_for("login"))

    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                atendimentos = json.load(f)
        else:
            atendimentos = []
    except Exception as e:
        print(f"❌ Erro ao carregar atendimentos: {e}")
        atendimentos = []

    return render_template("atendimentos.html", atendimentos=atendimentos)



@app.route("/equipes")
def equipes():
    return "📌 Página de Equipes (em construção)"


@app.route("/dashboard")
def dashboard():
    return "📊 Página de Dashboard (em construção)"


# =====================================================
# 🔹 Inicialização
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)











































