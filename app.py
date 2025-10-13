from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify, send_file
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
    try:
        os.makedirs("data", exist_ok=True)
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                try:
                    dados = json.load(f)
                except json.JSONDecodeError:
                    dados = []
        else:
            dados = []

        dados.append(atendimento)

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

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
    """Gera o arquivo DOCX, salva no diretório uploads e registra o atendimento"""
    try:
        doc = DocxTemplate(modelo_docx)
        os.makedirs("uploads", exist_ok=True)

        # Número do laudo (gera automático se vazio)
        numero_laudo = contexto.get("numero_laudo")
        if not numero_laudo or numero_laudo.strip() == "":
            numero_laudo = datetime.now().strftime("%Y%m%d%H%M%S")
            contexto["numero_laudo"] = numero_laudo

        # Gera mapa se houver lat/lon
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

        # Gera o documento final
        contexto["ano"] = date.today().year
        nome_arquivo = f"{tipo.capitalize()}_{numero_laudo}.docx"
        caminho_saida = os.path.join("uploads", nome_arquivo)
        doc.render(contexto)
        doc.save(caminho_saida)

        # --- NOVO: salvar registro em atendimentos.json ---
        atendimento = {
            "origem": tipo.capitalize(),
            "numero_laudo": numero_laudo,
            "bairro": contexto.get("bairro"),
            "latitude": contexto.get("latitude"),
            "longitude": contexto.get("longitude"),
            "data_vistoria": contexto.get("data_vistoria"),
            "grau_risco": contexto.get("grau_risco"),
            "arquivo": nome_arquivo,
            "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }

        salvar_atendimento(atendimento)
        print(f"✅ Atendimento salvo: {numero_laudo}")

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
            contexto = {campo[1]: request.form.get(campo[1], "") for campo in campos_base}
            contexto["ano"] = date.today().year
            contexto["grau_risco"] = request.form.get("grau_risco", "")

            numero_laudo = processar_laudo(contexto, "regularizacao", "modelo_laudo_reg.docx")

            if numero_laudo:
                atendimento = {
                    "origem": "Regularização Fundiária",
                    "numero_laudo": numero_laudo,
                    "bairro": contexto.get("bairro", ""),
                    "latitude": contexto.get("latitude", ""),
                    "longitude": contexto.get("longitude", ""),
                    "data_vistoria": contexto.get("data_vistoria", ""),
                    "grau_risco": contexto.get("grau_risco", ""),
                    "arquivo": f"Regularizacao_{numero_laudo}.docx",
                    "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M")
                }

                os.makedirs("data", exist_ok=True)
                if not os.path.exists(DATA_FILE):
                    with open(DATA_FILE, "w", encoding="utf-8") as f:
                        json.dump([], f, ensure_ascii=False, indent=2)

                try:
                    with open(DATA_FILE, "r", encoding="utf-8") as f:
                        conteudo = f.read().strip()
                        dados = json.loads(conteudo) if conteudo else []
                except json.JSONDecodeError:
                    dados = []

                dados.append(atendimento)
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(dados, f, ensure_ascii=False, indent=2)

                return redirect(url_for("atendimentos"))
            else:
                return "Erro ao gerar o laudo de regularização", 500

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
                "n_ocorrencia": request.form.get("n_ocorrencia", ""),
                "bairro": request.form.get("bairro", ""),
                "latitude": request.form.get("latitude", ""),
                "longitude": request.form.get("longitude", ""),
                "data_vistoria": request.form.get("data_vistoria", ""),
                "grau_risco": request.form.get("grau_risco", "")
            }

            numero_laudo = processar_laudo(contexto, "incendios", "modelo_laudo_incendio.docx")

            if numero_laudo:
                atendimento = {
                    "origem": "Incêndios",
                    "numero_laudo": numero_laudo,
                    "bairro": contexto.get("bairro", ""),
                    "latitude": contexto.get("latitude", ""),
                    "longitude": contexto.get("longitude", ""),
                    "data_vistoria": contexto.get("data_vistoria", ""),
                    "grau_risco": contexto.get("grau_risco", ""),
                    "arquivo": f"Incendios_{numero_laudo}.docx",
                    "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M")
                }

                os.makedirs("data", exist_ok=True)
                if not os.path.exists(DATA_FILE):
                    with open(DATA_FILE, "w", encoding="utf-8") as f:
                        json.dump([], f, ensure_ascii=False, indent=2)

                try:
                    with open(DATA_FILE, "r", encoding="utf-8") as f:
                        conteudo = f.read().strip()
                        dados = json.loads(conteudo) if conteudo else []
                except json.JSONDecodeError:
                    dados = []

                dados.append(atendimento)
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(dados, f, ensure_ascii=False, indent=2)

                return redirect(url_for("atendimentos"))
            else:
                return "Erro ao gerar o laudo de incêndios", 500

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
        print("❌ Erro ao ler atendimentos:", e)
        atendimentos = []

    return render_template(
    "atendimentos.html",
    atendimentos=atendimentos,
    atendimentos_json=json.dumps(atendimentos, ensure_ascii=False)
)


@app.route("/download/<nome_arquivo>")
def download_arquivo(nome_arquivo):
    """Permite baixar qualquer laudo salvo em /uploads"""
    try:
        caminho = os.path.join("uploads", nome_arquivo)
        if not os.path.exists(caminho):
            return f"Arquivo {nome_arquivo} não encontrado.", 404
        return send_file(caminho, as_attachment=True)
    except Exception as e:
        print(f"❌ Erro ao baixar arquivo: {e}")
        return f"Erro ao baixar arquivo: {e}", 500

@app.route("/excluir_atendimento/<numero_laudo>", methods=["POST"])
def excluir_atendimento(numero_laudo):
    """Exclui um atendimento do arquivo JSON com base no número do laudo"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
        else:
            dados = []

        # Filtra todos que NÃO têm o número_laudo informado
        novos_dados = [a for a in dados if str(a.get("numero_laudo")) != str(numero_laudo)]

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(novos_dados, f, ensure_ascii=False, indent=2)

        print(f"🗑️ Atendimento {numero_laudo} removido com sucesso.")
        return redirect(url_for("atendimentos"))

    except Exception as e:
        print(f"❌ Erro ao excluir atendimento: {e}")
        return "Erro ao excluir atendimento", 500

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



















































