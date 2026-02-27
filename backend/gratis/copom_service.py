import requests
from datetime import datetime, date
from collections import defaultdict


# Reuniões COPOM 2026 - segunda data é o último dia (lastTradeDt usado na URL)
REUNIOES_COPOM = [
    {"label": "17 e 18 de março de 2026",  "data_reuniao": "2026-03-18", "data_inicio": "2026-01-19"},
    {"label": "28 e 29 de abril de 2026",  "data_reuniao": "2026-04-29", "data_inicio": "2026-03-19"},
    {"label": "16 e 17 de junho de 2026",  "data_reuniao": "2026-06-17", "data_inicio": "2026-04-30"},
    {"label": "04 e 05 de agosto de 2026", "data_reuniao": "2026-08-05", "data_inicio": "2026-06-18"},
    {"label": "15 e 16 de setembro de 2026","data_reuniao": "2026-09-16","data_inicio": "2026-08-06"},
    {"label": "03 e 04 de novembro de 2026","data_reuniao": "2026-11-04", "data_inicio": "2026-09-17"},
    {"label": "08 e 09 de dezembro de 2026","data_reuniao": "2026-12-09", "data_inicio": "2026-11-05"},
]


B3_COPOM_URL = "https://arquivos.b3.com.br/charts/chart/copom/{ref_date}/{meeting_date}?qt={days}"
B3_SELIC_URL = "https://arquivos.b3.com.br/charts/chart/selic/{ref_date}"

# Ordem dos cenários para exibição no gráfico
SCENARIO_ORDER = [
    "Queda de 2%", "Queda de 1,75%", "Queda de 1,5%", "Queda de 1,25%",
    "Queda de 1%", "Queda de 0,75%", "Queda de 0,5%", "Queda de 0,25%",
    "Manutenção",
    "Aumento de 0,25%", "Aumento de 0,5%", "Aumento de 0,75%", "Aumento de 1%"
]


def get_proxima_reuniao():
    """Retorna a próxima reunião COPOM a partir de hoje."""
    hoje = date.today()
    for r in REUNIOES_COPOM:
        dt = datetime.strptime(r["data_reuniao"], "%Y-%m-%d").date()
        if dt >= hoje:
            return r
    return REUNIOES_COPOM[-1]


def get_selic_atual(ref_date=None):
    """Busca taxa Selic Meta atual da B3."""
    if not ref_date:
        ref_date = date.today().strftime("%Y-%m-%d")
    try:
        url = B3_SELIC_URL.format(ref_date=ref_date)
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        valor = float(r.text.strip())
        return valor
    except Exception as e:
        print(f"Erro ao buscar Selic: {e}")
        return None


def get_dados_copom(ref_date=None, meeting_date=None, days=60):
    """
    Busca dados históricos do COPOM da B3.
    
    ref_date: data de referência (D-1), padrão = hoje
    meeting_date: data da reunião COPOM
    days: quantidade de dias úteis históricos
    """
    if not ref_date:
        ref_date = date.today().strftime("%Y-%m-%d")
    if not meeting_date:
        reuniao = get_proxima_reuniao()
        meeting_date = reuniao["data_reuniao"]

    try:
        url = B3_COPOM_URL.format(
            ref_date=ref_date,
            meeting_date=meeting_date,
            days=days
        )
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data
    except Exception as e:
        print(f"Erro ao buscar dados COPOM: {e}")
        return []


def processar_probabilidades_d1(dados, ref_date=None):
    """
    Retorna as probabilidades do último rptDt disponível (D-1).
    Retorna lista de {cenario, probabilidade} ordenada por SCENARIO_ORDER.
    """
    if not ref_date:
        ref_date = date.today().strftime("%Y-%m-%d")

    # Filtra pelo rptDt mais recente <= ref_date
    datas_disponiveis = sorted(set(
        d["rptDt"] for d in dados if d["rptDt"] <= ref_date
    ), reverse=True)

    if not datas_disponiveis:
        return []

    ultimo_rpt = datas_disponiveis[0]
    registros_d1 = [d for d in dados if d["rptDt"] == ultimo_rpt]

    # Monta dict cenario -> refPric
    mapa = {r["scnroNm"]: r["refPric"] for r in registros_d1}

    resultado = []
    for cenario in SCENARIO_ORDER:
        if cenario in mapa:
            resultado.append({
                "cenario": cenario,
                "probabilidade": mapa[cenario]
            })

    return resultado, ultimo_rpt


def processar_historico_probabilidades(dados):
    """
    Retorna série histórica de probabilidades por cenário.
    Formato: {datas: [...], series: [{cenario: x, valores: [...]}]}
    """
    # Agrupa por rptDt
    por_data = defaultdict(dict)
    for d in dados:
        por_data[d["rptDt"]][d["scnroNm"]] = d["refPric"]

    datas = sorted(por_data.keys())

    # Monta series apenas com cenários que tiveram algum valor > 0
    series = []
    for cenario in SCENARIO_ORDER:
        valores = [por_data[dt].get(cenario, 0) for dt in datas]
        if any(v > 0 for v in valores):
            series.append({
                "cenario": cenario,
                "valores": valores
            })

    return {"datas": datas, "series": series}


def processar_historico_volume(dados):
    """
    Retorna série histórica de volume negociado por cenário.
    Formato: {datas: [...], series: [{cenario: x, valores: [...]}]}
    """
    por_data = defaultdict(dict)
    for d in dados:
        por_data[d["rptDt"]][d["scnroNm"]] = d["rglrTraddCtrcts"]

    datas = sorted(por_data.keys())

    series = []
    for cenario in SCENARIO_ORDER:
        valores = [por_data[dt].get(cenario, 0) for dt in datas]
        if any(v > 0 for v in valores):
            series.append({
                "cenario": cenario,
                "valores": valores
            })

    # Totais por data
    totais = [sum(por_data[dt].values()) for dt in datas]

    return {"datas": datas, "series": series, "totais": totais}


def get_dados_completos(ref_date=None, meeting_date=None, days=60):
    """
    Função principal: retorna tudo que o frontend precisa.
    """
    today_str = date.today().strftime("%Y-%m-%d")
    if not ref_date:
        ref_date = today_str

    # Identifica reunião
    reuniao = None
    if meeting_date:
        reuniao = next((r for r in REUNIOES_COPOM if r["data_reuniao"] == meeting_date), None)
    if not reuniao:
        reuniao = get_proxima_reuniao()
        meeting_date = reuniao["data_reuniao"]

    # Busca dados
    dados = get_dados_copom(ref_date=ref_date, meeting_date=meeting_date, days=days)
    selic = get_selic_atual(ref_date=ref_date)

    if not dados:
        return {
            "erro": "Não foram encontrados dados para o período selecionado.",
            "reuniao": reuniao,
            "selic": selic,
            "ref_date": ref_date
        }

    # Processa
    prob_result = processar_probabilidades_d1(dados, ref_date)
    if prob_result:
        probabilidades_d1, ultimo_rpt = prob_result
    else:
        probabilidades_d1, ultimo_rpt = [], None

    historico_prob = processar_historico_probabilidades(dados)
    historico_vol = processar_historico_volume(dados)

    return {
        "reuniao": reuniao,
        "reunioes": REUNIOES_COPOM,
        "ref_date": ref_date,
        "ultimo_rpt": ultimo_rpt,
        "selic": selic,
        "probabilidades_d1": probabilidades_d1,
        "historico_probabilidades": historico_prob,
        "historico_volume": historico_vol,
    }