from flask import send_from_directory, Flask, jsonify, Response
from flask_cors import CORS
import requests
import os
import time
from datetime import datetime

app = Flask(__name__, static_folder="static")
CORS(app)

TOKEN = os.getenv("INMET_TOKEN") or "bEhBU0szRjV4TGhic2E3ZHpndEVTVENrSkN4NjJxZm0=lHASK3F5xLhbsa7dzgtESTCkJCx62qfm"

TIMEOUT = 4
MAX_ESTACOES = 600


@app.route("/")
def home():
    return send_from_directory("static", "mapa.html")


def to_float(v):
    try:
        return float(v)
    except:
        return None


def buscar_horarios_disponiveis():
    agora = time.gmtime()
    data = time.strftime("%Y-%m-%d", agora)
    hora_atual = int(time.strftime("%H", agora))
    return data, [f"{h:02d}00" for h in range(hora_atual + 1)]


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


@app.route("/relatorio/diario")
def relatorio_diario():
    data, horarios = buscar_horarios_disponiveis()

    registros_temp_max = []
    registros_temp_min = []
    registros_chuva = []

    acumulado_chuva = {}

    for hora in horarios:
        url = f"https://apitempo.inmet.gov.br/token/estacao/dados/{data}/{hora}/{TOKEN}"

        try:
            estacoes = requests.get(url, timeout=TIMEOUT).json()
        except:
            continue

        for e in estacoes[:MAX_ESTACOES]:
            chave = f"{e.get('DC_NOME')}/{e.get('UF')}"

            temp_max = to_float(e.get("TEM_MAX"))
            temp_min = to_float(e.get("TEM_MIN"))
            chuva = to_float(e.get("CHUVA"))

            if temp_max is not None:
                registros_temp_max.append((chave, hora, temp_max))

            if temp_min is not None:
                registros_temp_min.append((chave, hora, temp_min))

            if chuva is not None and chuva > 0:
                registros_chuva.append((chave, hora, chuva))

                if chave not in acumulado_chuva:
                    acumulado_chuva[chave] = chuva
                else:
                    acumulado_chuva[chave] += chuva


    def extremos_por_estacao(registros, maior=True):
        d = {}
        for chave, hora, valor in registros:
            if chave not in d:
                d[chave] = (hora, valor)
            else:
                if maior and valor > d[chave][1]:
                    d[chave] = (hora, valor)
                elif not maior and valor < d[chave][1]:
                    d[chave] = (hora, valor)

        return [
            (hora, chave.split("/")[0], chave.split("/")[1], valor)
            for chave, (hora, valor) in d.items()
        ]


    top_quentes = sorted(
        extremos_por_estacao(registros_temp_max, maior=True),
        key=lambda x: x[3],
        reverse=True
    )[:10]

    top_frias = sorted(
        extremos_por_estacao(registros_temp_min, maior=False),
        key=lambda x: x[3]
    )[:10]

    top_chuva = sorted(
        extremos_por_estacao(registros_chuva, maior=True),
        key=lambda x: x[3],
        reverse=True
    )[:10]

    top_chuva_acumulada = sorted(
        [(k.split("/")[0], k.split("/")[1], v) for k, v in acumulado_chuva.items()],
        key=lambda x: x[2],
        reverse=True
    )[:10]


    hoje = datetime.utcnow().strftime("%d/%m/%Y")

    def linha(lista):
        return "".join(
            f"<tr><td>{h}</td><td>{c}/{u}</td><td><b>{v}</b></td></tr>"
            for h, c, u, v in lista
        )

    def linha_acumulado(lista):
        return "".join(
            f"<tr><td>{c}/{u}</td><td><b>{v:.1f}</b></td></tr>"
            for c, u, v in lista
        )


    html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Relatório Diário – Extremos Horários</title>
<style>
body {{ font-family: Arial; background:#f0f2f5; padding:20px; }}
.container {{ background:#fff; max-width:950px; margin:auto; padding:25px; border-radius:10px; box-shadow:0 4px 12px rgba(0,0,0,0.1); }}
h1 {{ text-align:center; color:#333; }}
table {{ width:100%; border-collapse:collapse; margin-top:10px; font-size:14px; }}
th,td {{ padding:10px; border-bottom:1px solid #ddd; text-align:center; }}
th {{ background:#eee; }}
.section {{ margin-top:35px; border-radius:8px; padding:15px; }}
.top-quente {{ background:#ffe6e6; }}
.top-frio {{ background:#e6f0ff; }}
.top-chuva {{ background:#e6ffe6; }}
</style>
</head>
<body>

<div class="container">
<h1>📊 Relatório Diário de Extremos</h1>
<p style="text-align:center; font-size:16px;">📅 {hoje}</p>

<div class="section top-quente">
<h2>🔥 Maiores Temperaturas do Dia</h2>
<table>
<tr><th>Hora</th><th>Estação</th><th>°C</th></tr>
{linha(top_quentes)}
</table>
</div>

<div class="section top-frio">
<h2>❄️ Menores Temperaturas do Dia</h2>
<table>
<tr><th>Hora</th><th>Estação</th><th>°C</th></tr>
{linha(top_frias)}
</table>
</div>

<div class="section top-chuva">
<h2>🌧️ Maiores Chuvas Horárias</h2>
<table>
<tr><th>Hora</th><th>Estação</th><th>mm</th></tr>
{linha(top_chuva) if top_chuva else "<tr><td colspan='3'>Sem registros</td></tr>"}
</table>
</div>

<div class="section top-chuva">
<h2>🌧️🌧️ Maiores Acumulados de Chuva do Dia</h2>
<table>
<tr><th>Estação</th><th>mm (acumulado)</th></tr>
{linha_acumulado(top_chuva_acumulada) if top_chuva_acumulada else "<tr><td colspan='2'>Sem registros</td></tr>"}
</table>
</div>

</div>
</body>
</html>
"""

    return Response(html, mimetype="text/html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
