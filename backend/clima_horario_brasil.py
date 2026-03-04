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
MAX_ESTACOES = 2000


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
            "codigo": e.get("CD_ESTACAO"),
            "nome": e.get("DC_NOME"),
            "uf": e.get("UF"),
            "lat": lat,
            "lon": lon,
            "temperatura": temp,
            "temperatura_maxima": to_float(e.get("TEM_MAX")),
            "temperatura_minima": to_float(e.get("TEM_MIN")),
            "umidade": to_float(e.get("UMD_INS")),
            "vento": to_float(e.get("VEN_VEL")),
            "vento_rajada": to_float(e.get("VEN_RAJ")),
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
    registros_umidade_max = []
    registros_umidade_min = []
    registros_vento = []

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
            umidade = to_float(e.get("UMD_INS"))
            chuva = to_float(e.get("CHUVA"))
            vento = to_float(e.get("VEN_RAJ"))

            if vento is not None:
                registros_vento.append((chave, hora, vento))

            if temp_max is not None:
                registros_temp_max.append((chave, hora, temp_max))

            if temp_min is not None:
                registros_temp_min.append((chave, hora, temp_min))
            umidade = to_float(e.get("UMD_INS"))

            if umidade is not None:
                registros_umidade_max.append((chave, hora, umidade))
                registros_umidade_min.append((chave, hora, umidade))

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
    )[:15]

    top_frias = sorted(
        extremos_por_estacao(registros_temp_min, maior=False),
        key=lambda x: x[3]
    )[:15]

    top_umidade_max = sorted(
        extremos_por_estacao(registros_umidade_max, maior=True),
        key=lambda x: x[3],
        reverse=True
    )[:15]

    top_umidade_min = sorted(
        extremos_por_estacao(registros_umidade_min, maior=False),
        key=lambda x: x[3]
    )[:15]

    top_chuva = sorted(
        extremos_por_estacao(registros_chuva, maior=True),
        key=lambda x: x[3],
        reverse=True
    )[:15]

    top_chuva_acumulada = sorted(
        [(k.split("/")[0], k.split("/")[1], v) for k, v in acumulado_chuva.items()],
        key=lambda x: x[2],
        reverse=True
    )[:15]

    Top_vento = sorted(
        extremos_por_estacao(registros_vento, maior=True),
        key=lambda x: x[3],
        reverse=True
    )[:15]

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
.top-umidade-max {{ background:#fff3e0; }}
.top-umidade-min {{ background:#fff3e0; }}
.top-vento {{ background:#f0f0f0; }}

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

<div class="section top-umidade-max">
<h2>💧💧 Maiores Umidades do Dia</h2>
<table>
<tr><th>Hora</th><th>Estação</th><th>%</th></tr>
{linha(top_umidade_max)}
</table>
</div>

<div class="section top-umidade-min">
<h2>💧 Menores Umidades do Dia</h2>
<table>
<tr><th>Hora</th><th>Estação</th><th>%</th></tr>
{linha(top_umidade_min)}
</table>
</div>

<div class="section top-vento">
<h2>💨 Maiores Velocidades de Vento do Dia</h2>
<table>
<tr><th>Hora</th><th>Estação</th><th>m/s</th></tr>
{linha(Top_vento)}
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
<h2>🌧️🌧️ Acumulados de Chuva do Dia</h2>
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

@app.route("/diario/<codigo>")
def diario_estacao(codigo):

    data, horarios = buscar_horarios_disponiveis()
    registros = []
    nome_estacao = None

    for hora in horarios:
        url = f"https://apitempo.inmet.gov.br/token/estacao/dados/{data}/{hora}/{TOKEN}"

        try:
            estacoes = requests.get(url, timeout=TIMEOUT).json()
        except:
            continue

        for e in estacoes:
            if e.get("CD_ESTACAO") == codigo:

                if not nome_estacao:
                    nome_estacao = f"{e.get('DC_NOME')} - {e.get('UF')}"

                registros.append({
                    "hora": hora,
                    "temp": to_float(e.get("TEM_INS")),
                    "temp_max": to_float(e.get("TEM_MAX")),
                    "temp_min": to_float(e.get("TEM_MIN")),
                    "umidade": to_float(e.get("UMD_INS")),
                    "umidade_max": to_float(e.get("UMD_MAX")),
                    "umidade_min": to_float(e.get("UMD_MIN")),
                    "orvalho": to_float(e.get("PTO_INS")),
                    "orvalho_max": to_float(e.get("PTO_MAX")),
                    "orvalho_min": to_float(e.get("PTO_MIN")),
                    "pressao": to_float(e.get("PRE_INS")),
                    "pressao_max": to_float(e.get("PRE_MAX")),
                    "pressao_min": to_float(e.get("PRE_MIN")),
                    "vento": to_float(e.get("VEN_VEL")),
                    "vento_direcao": e.get("VEN_DIR"),
                    "vento_rajada": to_float(e.get("VEN_RAJ")),
                    "radiacao": to_float(e.get("RAD_GLO")),
                    "chuva": to_float(e.get("CHUVA")),
                })

    if not registros:
        return f"Nenhum dado encontrado para estação {codigo}"

    if not nome_estacao:
        nome_estacao = "Nome não disponível"

    linhas = "".join(
        f"<tr>"
        f"<td>{r['hora']}</td>"

        f"<td>{r['temp'] if r['temp'] is not None else '-'}</td>"
        f"<td>{r['temp_max'] if r['temp_max'] is not None else '-'}</td>"
        f"<td>{r['temp_min'] if r['temp_min'] is not None else '-'}</td>"

        f"<td>{r['umidade'] if r['umidade'] is not None else '-'}</td>"
        f"<td>{r['umidade_max'] if r['umidade_max'] is not None else '-'}</td>"
        f"<td>{r['umidade_min'] if r['umidade_min'] is not None else '-'}</td>"

        f"<td>{r['orvalho'] if r['orvalho'] is not None else '-'}</td>"
        f"<td>{r['orvalho_max'] if r['orvalho_max'] is not None else '-'}</td>"
        f"<td>{r['orvalho_min'] if r['orvalho_min'] is not None else '-'}</td>"

        f"<td>{r['pressao'] if r['pressao'] is not None else '-'}</td>"
        f"<td>{r['pressao_max'] if r['pressao_max'] is not None else '-'}</td>"
        f"<td>{r['pressao_min'] if r['pressao_min'] is not None else '-'}</td>"

        f"<td>{r['vento'] if r['vento'] is not None else '-'}</td>"
        f"<td>{r['vento_direcao'] if r['vento_direcao'] else '-'}</td>"
        f"<td>{r['vento_rajada'] if r['vento_rajada'] is not None else '-'}</td>"

        f"<td>{format(r['radiacao'], '.1f') if r['radiacao'] is not None else '-'}</td>"
        f"<td>{format(r['chuva'], '.1f') if r['chuva'] is not None else '-'}</td>"

        f"</tr>"
        for r in registros
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório Diário - {codigo}</title>

    <style>
    body {{
        font-family: Arial, sans-serif;
        background: #f4f6f9;
        padding: 20px;
    }}

    .container {{
        background: white;
        padding: 25px;
        border-radius: 12px;
        max-width: 100%;
        margin: auto;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }}

    h1 {{
        text-align: center;
        margin-bottom: 5px;
    }}

    .subtitulo {{
        text-align: center;
        font-size: 18px;
        color: #555;
        margin-bottom: 20px;
    }}

    .table-wrapper {{
        width: 100%;
        overflow-x: auto;
    }}

    table {{
        border-collapse: collapse;
        width: 100%;
        min-width: 1500px;
    }}

    th, td {{
        padding: 8px;
        border-bottom: 1px solid #e0e0e0;
        text-align: center;
        font-size: 14px;
        white-space: nowrap;
    }}

    thead th {{
        background: #1976d2;
        color: white;
        position: sticky;
        top: 0;
        z-index: 2;
    }}

    /* 🔥 Separação branca vertical - primeira linha */
    thead tr:first-child th[colspan],
    thead tr:first-child th[rowspan] {{
        border-right: 2px solid white;
    }}

    /* 🔥 Separação branca - segunda linha */
    thead tr:nth-child(2) th:nth-child(3),
    thead tr:nth-child(2) th:nth-child(6),
    thead tr:nth-child(2) th:nth-child(9),
    thead tr:nth-child(2) th:nth-child(12),
    thead tr:nth-child(2) th:nth-child(15),
    thead tr:nth-child(2) th:nth-child(16),
    thead tr:nth-child(2) th:nth-child(17) {{
        border-right: 2px solid white;
    }}

    /* 🔥 Separação branca no corpo */
    tbody td:nth-child(4),
    tbody td:nth-child(7),
    tbody td:nth-child(10),
    tbody td:nth-child(13),
    tbody td:nth-child(16),
    tbody td:nth-child(17),
    tbody td:nth-child(18) {{
        border-right: 2px solid white;
    }}

    tr:nth-child(even) {{
        background: #f9f9f9;
    }}

    tr:hover {{
        background: #eef4ff;
    }}

    </style>
    </head>

    <body>
        <div class="container">
            <h1>📊 Relatório Diário</h1>
            <div class="subtitulo">
                Estação {codigo} - {nome_estacao}
            </div>

            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th rowspan="2">Hora</th>
                            <th colspan="3">Temperatura</th>
                            <th colspan="3">Umidade</th>
                            <th colspan="3">Orvalho</th>
                            <th colspan="3">Pressão</th>
                            <th colspan="3">Vento</th>
                            <th colspan="1">Radiação</th>
                            <th colspan="1">Chuva</th>
                        </tr>

                        <tr>
                            <th>Inst.</th><th>Máx</th><th>Min</th>
                            <th>Inst.</th><th>Máx</th><th>Min</th>
                            <th>Inst.</th><th>Máx</th><th>Min</th>
                            <th>Inst.</th><th>Máx</th><th>Min</th>
                            <th>Vel.</th><th>Dir.(°)</th><th>Raj.</th>
                            <th>(kJ/m²)</th>
                            <th>(mm)</th>
                        </tr>
                    </thead>

                    <tbody>
                        {linhas}
                    </tbody>
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