from flask import Flask, render_template, request, redirect, url_for, session, send_file
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


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================

def salvar_atendimento(atendimento):
    """Salva um novo atendimento no JSON"""
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


def gerar_mapa(lat, lon, caminho_saida):
    """Gera uma imagem de mapa com base na latitude/longitude"""
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


# ==========================================================
# ROTAS DE AUTENTICAÇÃO
# ==========================================================

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


# ==========================================================
# PÁGINA INICIAL
# ==========================================================

@app.route("/home")
def home():
    if not session.get("logado"):
        return redirect(url_for("login"))
    return render_template("home.html")


# ==========================================================
# CAMPOS BASE
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


# ==========================================================
# FUNÇÃO GENÉRICA DE GERAÇÃO DE LAUDO
# ==========================================================

def gerar_e_salvar_laudo(tipo, modelo_docx, contexto, imagens):
    """Gera o .docx, salva e registra o atendimento"""
    doc = DocxTemplate(modelo_docx)
    doc.render(contexto)

    numero_laudo = contexto.get("numero_laudo") or datetime.now().strftime("%Y%m%d%H%M%S")
    nome_arquivo = f"{tipo}_{numero_laudo}.docx"
    caminho_saida = os.path.join(UPLOAD_FOLDER, nome_arquivo)
    doc.save(caminho_saida)

    atendimento = {
        "tipo": tipo.capitalize(),
        "numero_laudo": numero_laudo,
        "bairro": contexto.get("bairro", ""),
        "latitude": contexto.get("latitude", ""),
        "longitude": contexto.get("longitude", ""),
        "grau_risco": contexto.get("grau_risco", ""),
        "arquivo": caminho_saida,
        "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }

    salvar_atendimento(atendimento)
    return caminho_saida


# ==========================================================
# ROTAS DE LAUDOS
# ==========================================================

@app.route("/chuvas", methods=["GET", "POST"])
def chuvas():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            contexto = {campo[1]: request.form.get(campo[1]) for campo in campos_chuvas}
            contexto["ano"] = date.today().year
            contexto["grau_risco"] = request.form.get("grau_risco")

            # Solo
            problemas = request.form.getlist("problemas_solo")
            outro = request.form.get("problemas_solo_outro", "").strip()
            if outro: problemas.append(outro)
            contexto["problemas_solo"] = ", ".join(problemas)

            # Presença cursos
            presenca = request.form.getlist("presenca_cursos")
            cursos = request.form.get("presenca_cursos_outro", "").strip()
            if cursos: presenca.append(cursos)
            contexto["presenca_cursos"] = ", ".join(presenca)

            contexto["sinais_instabilidade"] = ", ".join(request.form.getlist("sinais_instabilidade"))
            contexto["fatores_risco"] = ", ".join(request.form.getlist("fatores_risco"))

            imagens = []

            # Gerar mapa
            lat, lon = request.form.get("latitude"), request.form.get("longitude")
            if lat and lon:
                mapa_path = gerar_mapa(lat, lon, os.path.join(UPLOAD_FOLDER, "mapa.png"))
                if mapa_path:
                    contexto["imagem1"] = InlineImage(DocxTemplate("modelo_laudo_chuvas.docx"), mapa_path, width=Mm(100))
                    contexto["descricao1"] = "Localização Geográfica"

            caminho_saida = gerar_e_salvar_laudo("chuvas", "modelo_laudo_chuvas.docx", contexto, imagens)
            return redirect(url_for("atendimentos"))

        except Exception as e:
            return f"Erro interno: {e}", 500

    return render_template("chuvas.html", campos=campos_chuvas)


@app.route("/regularizacao", methods=["GET", "POST"])
def regularizacao():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            contexto = {campo[1]: request.form.get(campo[1]) for campo in campos_base}
            contexto["ano"] = date.today().year
            contexto["grau_risco"] = request.form.get("grau_risco")

            caminho_saida = gerar_e_salvar_laudo("regularizacao", "modelo_laudo_reg.docx", contexto, [])
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
                "n_ocorrencia": request.form.get("n_ocorrencia"),
                "bairro": request.form.get("bairro"),
                "latitude": request.form.get("latitude"),
                "longitude": request.form.get("longitude"),
                "data_vistoria": request.form.get("data_vistoria"),
            }

            caminho_saida = gerar_e_salvar_laudo("incendios", "modelo_laudo_incendio.docx", contexto, [])
            return redirect(url_for("atendimentos"))

        except Exception as e:
            return f"Erro interno: {e}", 500

    return render_template("incendios.html")


# ==========================================================
# ROTA DE ATENDIMENTOS
# ==========================================================

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
        atendimentos = []
        print("❌ Erro ao ler atendimentos:", e)

    return render_template("atendimentos.html", atendimentos=atendimentos)


@app.route("/download/<path:filename>")
def download(filename):
    """Permite baixar o DOCX pelo botão da lista"""
    try:
        return send_file(filename, as_attachment=True)
    except Exception as e:
        return f"Erro ao baixar arquivo: {e}", 500


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)








































