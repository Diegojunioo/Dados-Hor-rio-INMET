from flask import Flask, jsonify, Response
from flask_cors import CORS
import requests
import os
import time
from datetime import datetime

app = Flask(__name__)
CORS(app)

TOKEN = os.getenv("INMET_TOKEN") or "bEhBU0szRjV4TGhic2E3ZHpndEVTVENrSkN4NjJxZm0=lHASK3F5xLhbsa7dzgtESTCkJCx62qfm"

TIMEOUT = 4
MAX_ESTACOES = 600

# =====================================================
# 🏠 ROTA RAIZ — NECESSÁRIA PARA O RENDER
# =====================================================
@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "projeto": "Clima Horário Brasil - INMET",
        "descricao": "API de dados meteorológicos horários do INMET",
        "endpoints": {
            "clima": "/api/clima",
            "relatorio_diario": "/relatorio/diario"
        }
    })

def to_float(v):
    try:
        return float(v)
    except:
        return None

def buscar_horarios_disponiveis():
    agora = time.gmtime()
    data = time.strftime("%Y-%m-%d", agora)
    hora_atual = int(time.strftime("%H", agora))

    horarios = []
    for h in range(hora_atual + 1):
        horarios.append(f"{h:02d}00")

    return data, horarios

@app.route("/api/clima")
def api_clima():
    data, horarios = buscar_horarios_disponiveis()
    hora = horarios[-1]

    url = f"https://apitempo.inmet.gov.br/token/estacao/dados/{data}/{hora}/{TOKEN}"

    try:
        estacoes = requests.get(url, timeout=TIMEOUT).json()
    except:
        return jsonify({"dados": []})

    resultado = []

    for e in estacoes[:MAX_ESTACOES]:
        lat = to_float(e.get("VL_LATITUDE"))
        lon = to_float(e.get("VL_LONGITUDE"))
        temp = to_float(e.get("TEM_INS"))

        if not e.get("DC_NOME") or lat is None or lon is None or temp is None:
            continue

        resultado.append({
            "nome": e.get("DC_NOME"),
            "uf": e.get("UF"),
            "lat": lat,
            "lon": lon,
            "temperatura": temp,
            "temperatura_maxima": to_float(e.get("TEM_MAX")),
            "temperatura_minima": to_float(e.get("TEM_MIN")),
            "umidade": to_float(e.get("UMD_INS")),
            "vento": to_float(e.get("VEN_VEL")),
            "precipitacao": to_float(e.get("CHUVA")),
            "data": e.get("DT_MEDICAO"),
            "hora": e.get("HR_MEDICAO")
        })

    return jsonify({
        "total_estacoes": len(resultado),
        "ultima_atualizacao": f"{data} {hora}",
        "dados": resultado
    })

# 📄 RELATÓRIO DIÁRIO COM TODOS OS HORÁRIOS
@app.route("/relatorio/diario")
def relatorio_diario():

    data, horarios = buscar_horarios_disponiveis()

    registros_temp_max = []
    registros_temp_min = []
    registros_chuva = []

    for hora in horarios:
        url = f"https://apitempo.inmet.gov.br/token/estacao/dados/{data}/{hora}/{TOKEN}"

        try:
            estacoes = requests.get(url, timeout=TIMEOUT).json()
        except:
            continue

        for e in estacoes[:MAX_ESTACOES]:
            temp = to_float(e.get("TEM_INS"))
            chuva = to_float(e.get("CHUVA"))

            if temp is not None:
                registros_temp_max.append((hora, e.get("DC_NOME"), e.get("UF"), temp))
                registros_temp_min.append((hora, e.get("DC_NOME"), e.get("UF"), temp))

            if chuva and chuva > 0:
                registros_chuva.append((hora, e.get("DC_NOME"), e.get("UF"), chuva))

    top_quentes = sorted(registros_temp_max, key=lambda x: x[3], reverse=True)[:10]
    top_frias = sorted(registros_temp_min, key=lambda x: x[3])[:10]
    top_chuva = sorted(registros_chuva, key=lambda x: x[3], reverse=True)[:10]

    hoje = datetime.utcnow().strftime("%d/%m/%Y")

    def linha(l):
        return "".join(
            f"<tr><td>{h}</td><td>{c}/{u}</td><td><b>{v}</b></td></tr>"
            for h, c, u, v in l
        )

    html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Relatório Diário – Extremos Horários</title>
<style>
body {{ font-family: Arial; background:#f4f6f8; padding:20px; }}
.container {{ background:#fff; max-width:900px; margin:auto; padding:25px; border-radius:8px; }}
h1 {{ text-align:center; }}
table {{ width:100%; border-collapse:collapse; margin-top:10px; }}
th,td {{ padding:8px; border-bottom:1px solid #ddd; }}
th {{ background:#eee; }}
.section {{ margin-top:30px; }}
</style>
</head>
<body>
<div class="container">
<h1>📊 Relatório Diário – Extremos por Horário</h1>
<p style="text-align:center">📅 {hoje}</p>

<div class="section">
<h2>🔥 Maiores Temperaturas do Dia</h2>
<table>
<tr><th>Hora</th><th>Estação</th><th>°C</th></tr>
{linha(top_quentes)}
</table>
</div>

<div class="section">
<h2>❄️ Menores Temperaturas do Dia</h2>
<table>
<tr><th>Hora</th><th>Estação</th><th>°C</th></tr>
{linha(top_frias)}
</table>
</div>

<div class="section">
<h2>🌧️ Maiores Precipitações do Dia</h2>
<table>
<tr><th>Hora</th><th>Estação</th><th>mm</th></tr>
{linha(top_chuva) if top_chuva else "<tr><td colspan='3'>Sem registros</td></tr>"}
</table>
</div>

</div>
</body>
</html>
"""

    return Response(html, mimetype="text/html")

if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
