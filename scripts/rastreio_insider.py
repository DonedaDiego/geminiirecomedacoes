#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rastreio de volume anormal em opcoes (Hunter Walls em lote).

    python scripts/rastreio_insider.py
    python scripts/rastreio_insider.py --min-vol 50000 --mult 3
    python scripts/rastreio_insider.py --ativos ABEV3,VALE3
    python scripts/rastreio_insider.py --balanco-ate 7
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv


VENCIMENTOS = ["2026-08-21", "2026-09-18"]

BALANCOS = {
    "ALOS3":  ("2026-08-06", "depois"),
    "ALPA4":  ("2026-08-06", "depois"),
    "ABEV3":  ("2026-07-30", "antes"),
    "AMBP3":  ("2026-08-14", "depois"),
    "AMER3":  ("2026-08-12", "depois"),
    "ANIM3":  ("2026-08-05", "depois"),
    "ASAI3":  ("2026-08-06", "depois"),
    "AURE3":  ("2026-08-05", "depois"),
    "AXIA3":  ("2026-08-05", "depois"),
    "AZUL53": ("2026-08-12", "antes"),
    "AZZA3":  ("2026-08-12", "depois"),
    "B3SA3":  ("2026-08-11", "depois"),
    "BBAS3":  ("2026-08-12", "depois"),
    "BRSR6":  ("2026-08-13", "antes"),
    "BBSE3":  ("2026-08-03", "depois"),
    "BBDC4":  ("2026-08-05", "depois"),
    "BRAP4":  ("2026-08-13", "antes"),
    "BRKM5":  ("2026-08-12", "depois"),
    "BRAV3":  ("2026-08-05", "depois"),
    "BPAC11": ("2026-08-11", "antes"),
    "CEAB3":  ("2026-08-04", "depois"),
    "CAML3":  ("2026-07-14", "depois"),
    "CMIG4":  ("2026-08-13", "depois"),
    "COGN3":  ("2026-08-12", "depois"),
    "CPLE6":  ("2026-08-05", "depois"),
    "CSAN3":  ("2026-08-14", "depois"),
    "CPFE3":  ("2026-08-13", "depois"),
    "CSNA3":  ("2026-08-05", "depois"),
    "CMIN3":  ("2026-08-05", "depois"),
    "CVCB3":  ("2026-08-12", "depois"),
    "CYRE3":  ("2026-08-13", "depois"),
    "DASA3":  ("2026-08-13", "depois"),
    "DXCO3":  ("2026-08-05", "depois"),
    "DIRR3":  ("2026-08-11", "depois"),
    "ECOR3":  ("2026-07-30", "depois"),
    "EMBR3":  ("2026-08-10", "antes"),
    "ENGI11": ("2026-08-06", "depois"),
    "ENEV3":  ("2026-08-12", "depois"),
    "EGIE3":  ("2026-08-05", "depois"),
    "EQTL3":  ("2026-08-12", "depois"),
    "EZTC3":  ("2026-08-06", "depois"),
    "FLRY3":  ("2026-08-06", "depois"),
    "FRAS3":  ("2026-08-11", "depois"),
    "GGBR4":  ("2026-08-04", "depois"),
    "BHIA3":  ("2026-08-12", "depois"),
    "GMAT3":  ("2026-08-13", "depois"),
    "GUAR3":  ("2026-08-05", "depois"),
    "HAPV3":  ("2026-08-12", "depois"),
    "HYPE3":  ("2026-08-06", "depois"),
    "IGTI11": ("2026-08-04", "depois"),
    "INBR32": ("2026-08-06", "depois"),
    "MYPK3":  ("2026-08-05", "depois"),
    "IRBR3":  ("2026-08-13", "depois"),
    "ISAE4":  ("2026-08-03", "depois"),
    "ITUB4":  ("2026-08-04", "depois"),
    "ITSA4":  ("2026-08-10", "depois"),
    "JBSS32": ("2026-08-10", "depois"),
    "JHSF3":  ("2026-08-13", "depois"),
    "KEPL3":  ("2026-08-12", "depois"),
    "KLBN11": ("2026-08-05", "antes"),
    "LIGT3":  ("2026-08-13", "depois"),
    "RENT3":  ("2026-08-06", "depois"),
    "LWSA3":  ("2026-08-13", "depois"),
    "LREN3":  ("2026-08-06", "depois"),
    "MDIA3":  ("2026-08-13", "depois"),
    "MGLU3":  ("2026-08-06", "depois"),
    "LEVE3":  ("2026-08-12", "depois"),
    "POMO4":  ("2026-08-03", "depois"),
    "MBRF3":  ("2026-08-13", "depois"),
    "CASH3":  ("2026-08-05", "depois"),
    "MELI34": ("2026-08-05", "depois"),
    "GOAU4":  ("2026-08-04", "depois"),
    "BEEF3":  ("2026-08-12", "depois"),
    "MOTV3":  ("2026-07-29", "depois"),
    "MOVI3":  ("2026-08-12", "depois"),
    "MRVE3":  ("2026-08-12", "depois"),
    "MULT3":  ("2026-07-30", "depois"),
    "NATU3":  ("2026-08-10", "depois"),
    "ROXO34": ("2026-08-13", "depois"),
    "OIBR3":  ("2026-08-12", "depois"),
    "PGMN3":  ("2026-08-03", "depois"),
    "PNVL3":  ("2026-08-06", "depois"),
    "PCAR3":  ("2026-08-04", "depois"),
    "PETR4":  ("2026-08-06", "depois"),
    "PETR3":  ("2026-08-06", "depois"),
    "PRIO3":  ("2026-08-04", "depois"),
    "AUAU3":  ("2026-08-13", "depois"),
    "PSSA3":  ("2026-08-07", "antes"),
    "QUAL3":  ("2026-08-12", "depois"),
    "RADL3":  ("2026-08-04", "depois"),
    "RAPT4":  ("2026-08-13", "depois"),
    "RDOR3":  ("2026-08-12", "depois"),
    "RAIL3":  ("2026-08-12", "depois"),
    "SBSP3":  ("2026-08-12", "depois"),
    "SAPR11": ("2026-08-13", "depois"),
    "SANB11": ("2026-07-29", "antes"),
    "SMTO3":  ("2026-08-10", "depois"),
    "SEER3":  ("2026-08-12", "antes"),
    "SIMH3":  ("2026-08-14", "depois"),
    "SLCE3":  ("2026-08-12", "depois"),
    "SMFT3":  ("2026-08-05", "antes"),
    "SUZB3":  ("2026-08-12", "depois"),
    "TAEE11": ("2026-08-11", "depois"),
    "VIVT3":  ("2026-07-27", "antes"),
    "TEND3":  ("2026-08-04", "depois"),
    "TIMS3":  ("2026-07-27", "depois"),
    "TOTS3":  ("2026-08-05", "depois"),
    "TUPY3":  ("2026-08-06", "depois"),
    "UGPA3":  ("2026-08-12", "depois"),
    "USIM5":  ("2026-07-31", "antes"),
    "VALE3":  ("2026-07-30", "depois"),
    "VAMO3":  ("2026-08-13", "depois"),
    "VBBR3":  ("2026-08-14", "depois"),
    "VIVA3":  ("2026-08-05", "depois"),
    "WEGE3":  ("2026-07-22", "antes"),
    "XPBR31": (None, "a definir"),
    "YDUQ3":  ("2026-08-13", "depois"),
}

EXTRAS = ["BOVA11", "IBOV11", "BBDC3", "ELET3", "ELET6", "CSAN3"]

ATIVOS = sorted(set(BALANCOS) | set(EXTRAS))

MIN_VOLUME_HOJE = 100_000
MIN_MULTIPLICADOR = 4.0
DIAS_HISTORICO = 7
MAX_DIAS_BUSCA = 12
TOP_POR_ATIVO = 8

VPN_BLOCO = 100_000
VPN_MISTO = 20_000
TOLERANCIA_CASADA = 0.02

MAX_WORKERS_ATIVOS = 10
MAX_WORKERS_DIAS = 4
LOTE_HISTORICO = 40
TIMEOUT = 20

BASE_URL = "https://api.oplab.com.br/v3"

LETRAS_FALLBACK = {
    "2026-08-21": ("H", "T"),
    "2026-09-18": ("I", "U"),
}


def carregar_token():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(dotenv_path=env_path)
    token = os.getenv('OPLAB_TOKEN')
    if not token:
        raise ValueError("Token OPLAB_TOKEN não encontrado no .env")
    return token


class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
    CYAN = "\033[96m"; MAGENTA = "\033[95m"; GRAY = "\033[90m"


if os.name == "nt":
    os.system("")


def br(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return str(n)


def brf(n, casas=2):
    try:
        return f"{float(n):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(n)


def data_br(iso, curta=False):
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return d.strftime("%d/%m") if curta else d.strftime("%d/%m/%Y")
    except Exception:
        return iso or "-"


def info_balanco(ticker):
    data, periodo = BALANCOS.get(ticker, (None, None))
    if not data:
        return None
    try:
        dias = (datetime.strptime(data, "%Y-%m-%d").date() - datetime.now().date()).days
    except Exception:
        return None
    janela = dias - 1 if periodo == "antes" else dias
    return {"data": data, "periodo": periodo, "dias": dias, "janela": janela}


class OpLab:
    def __init__(self, token):
        self.headers = {"Access-Token": token}
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.6,
                      status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=32, pool_maxsize=32)
        self.session.mount("https://", adapter)

    def _get(self, path, **kwargs):
        return self.session.get(f"{BASE_URL}{path}", headers=self.headers,
                                timeout=TIMEOUT, **kwargs)

    def opcoes(self, ticker):
        try:
            r = self._get(f"/market/options/{ticker}")
            if r.status_code != 200:
                return None, None, f"HTTP {r.status_code}"
            dados = r.json()
            if not dados:
                return None, None, "sem opcoes"
            spot = None
            opcoes = []
            for o in dados:
                if spot is None:
                    spot = extrair_spot(o)
                op = normalizar(o)
                if op:
                    opcoes.append(op)
            return opcoes, spot, None
        except Exception as e:
            return None, None, str(e)

    def spot(self, ticker):
        try:
            r = self._get(f"/market/stocks/{ticker}")
            if r.status_code == 200:
                d = r.json()
                d = d[0] if isinstance(d, list) and d else d
                for k in ("close", "last", "price", "market_price"):
                    if d.get(k):
                        return float(d[k])
        except Exception:
            pass
        return None

    def historico_dia(self, symbols, date_str):
        dados = {}
        for i in range(0, len(symbols), LOTE_HISTORICO):
            lote = symbols[i:i + LOTE_HISTORICO]
            try:
                r = self._get("/market/historical/instruments",
                              params={"tickers": ",".join(lote), "date": date_str})
                if r.status_code != 200:
                    continue
                for o in r.json() or []:
                    sym = campo(o, "symbol", "ticker")
                    if not sym:
                        continue
                    atual = dados.setdefault(sym, {"vol": 0, "oi": 0})
                    atual["vol"] += num(campo(o, "volume", "vol"), 0)
                    atual["oi"] = max(atual["oi"], num(campo(o, "open_interest", "oi"), 0))
            except Exception:
                continue
        return date_str, dados


def campo(o, *nomes, default=None):
    fontes = [o]
    for k in ("market", "info", "data"):
        if isinstance(o.get(k), dict):
            fontes.append(o[k])
    for f in fontes:
        for n in nomes:
            v = f.get(n)
            if v not in (None, ""):
                return v
    return default


def num(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def extrair_spot(o):
    sp = o.get("spot")
    if isinstance(sp, dict):
        for k in ("price", "close", "last", "market_price"):
            if sp.get(k):
                return num(sp[k], None)
    v = campo(o, "spot_price", "underlying_price", "parent_price")
    return num(v, None) if v else None


def normalizar(o):
    try:
        symbol = campo(o, "symbol", "ticker")
        if not symbol:
            return None
        tipo = str(campo(o, "category", "type", default="")).upper()
        if tipo.startswith("C"):
            tipo = "CALL"
        elif tipo.startswith("P"):
            tipo = "PUT"
        else:
            return None

        volume = int(num(campo(o, "volume", "vol"), 0))
        fin = num(campo(o, "financial_volume", "fin_volume", "volume_financeiro"), 0.0)
        close = num(campo(o, "close", "last", "premium", "market_price"), 0.0)
        bid = num(campo(o, "bid"), 0.0)
        ask = num(campo(o, "ask"), 0.0)
        lote = num(campo(o, "contract_size", "lot"), 1.0) or 1.0

        medio = 0.0
        if volume > 0 and fin > 0:
            medio = fin / volume
            if close > 0 and lote > 1 and abs(medio - close) > abs(medio / lote - close):
                medio /= lote
        if medio <= 0:
            medio = close
        if fin <= 0 and volume > 0 and medio > 0:
            fin = volume * medio

        due = campo(o, "due_date", "maturity_date", "expiration", default="")
        return {
            "symbol": str(symbol).upper(),
            "tipo": tipo,
            "strike": num(campo(o, "strike"), 0.0),
            "volume": volume,
            "fin": fin,
            "medio": medio,
            "close": close,
            "bid": bid,
            "ask": ask,
            "trades": int(num(campo(o, "trades", "number_of_trades"), 0)),
            "oi": int(num(campo(o, "open_interest", "oi", "open_interest_quantity"), 0)),
            "due": str(due)[:10],
        }
    except Exception:
        return None


def vies_agressao(preco, bid, ask):
    if not (bid > 0 and ask > bid and preco > 0):
        return "?", None
    pos = (preco - bid) / (ask - bid)
    pos = max(0.0, min(1.0, pos))
    if pos >= 0.65:
        return "COMPRA", pos
    if pos <= 0.35:
        return "VENDA", pos
    return "MEIO", pos


def letra_vencimento(symbol, base_ticker):
    radical = base_ticker[:4].upper()
    resto = symbol.upper().replace(radical, "", 1)
    for ch in resto:
        if ch.isalpha():
            return ch
    return ""


def moneyness(tipo, strike, spot):
    if not spot:
        return "?"
    dist = (strike - spot) / spot * 100
    if abs(dist) <= 2:
        return "ATM"
    if tipo == "CALL":
        return "OTM" if dist > 0 else "ITM"
    return "ITM" if dist > 0 else "OTM"


def pregoes_anteriores(qtd, max_busca):
    hoje = datetime.now().date()
    dias, i = [], 1
    while len(dias) < qtd and i <= max_busca:
        d = hoje - timedelta(days=i)
        if d.weekday() < 5:
            dias.append(d.strftime("%Y-%m-%d"))
        i += 1
    return dias


def coletar(api, ativos):
    resultado, falhas = {}, []

    def tarefa(t):
        return t, api.opcoes(t)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS_ATIVOS) as ex:
        for fut in as_completed([ex.submit(tarefa, t) for t in ativos]):
            ticker, (opcoes, spot, erro) = fut.result()
            if erro or not opcoes:
                falhas.append(ticker)
                continue

            por_venc = {v: [] for v in VENCIMENTOS}
            usou_due = any(o["due"] in VENCIMENTOS for o in opcoes)

            for o in opcoes:
                if o["volume"] <= 0:
                    continue
                if usou_due:
                    if o["due"] in por_venc:
                        por_venc[o["due"]].append(o)
                else:
                    letra = letra_vencimento(o["symbol"], ticker)
                    for venc, letras in LETRAS_FALLBACK.items():
                        if letra in letras and venc in por_venc:
                            por_venc[venc].append(o)

            if any(por_venc.values()):
                resultado[ticker] = {"spot": spot, "vencimentos": por_venc}
            else:
                falhas.append(ticker)

    return resultado, falhas


def buscar_historico(api, symbols, dias):
    hist = {s: {"vols": [], "oi_ultimo": 0} for s in symbols}
    validos = 0
    coletados = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_DIAS) as ex:
        futs = [ex.submit(api.historico_dia, symbols, d) for d in dias]
        for fut in as_completed(futs):
            data, dia = fut.result()
            if not dia:
                continue
            validos += 1
            coletados.append((data, dia))
            for s in symbols:
                hist[s]["vols"].append(dia.get(s, {}).get("vol", 0))

    if coletados:
        _, ultimo = max(coletados, key=lambda x: x[0])
        for s in symbols:
            hist[s]["oi_ultimo"] = ultimo.get(s, {}).get("oi", 0)

    return hist, validos


def analisar(dados, hist, min_vol, mult_min):
    alertas = {}
    for ticker, info in dados.items():
        spot = info["spot"]
        linhas = []
        for venc, opcoes in info["vencimentos"].items():
            for o in opcoes:
                vol = o["volume"]
                if vol < min_vol:
                    continue
                h = hist.get(o["symbol"], {})
                serie = h.get("vols", [])
                media = (sum(serie) / len(serie)) if serie else 0.0

                if media <= 0:
                    mult, nivel = float("inf"), "SEM HISTORICO"
                else:
                    mult = vol / media
                    if mult < mult_min:
                        continue
                    nivel = "EXTREMO" if mult >= 10 else "ALTO" if mult >= 6 else "ELEVADO"

                oi_ant = h.get("oi_ultimo", 0)
                d_oi = o["oi"] - oi_ant if oi_ant else 0
                if oi_ant and d_oi > 0:
                    posicao = "ABERTURA"
                elif oi_ant and d_oi < 0:
                    posicao = "ZERAGEM"
                else:
                    posicao = "?"

                vpn = vol / o["trades"] if o["trades"] > 0 else 0
                if vpn <= 0:
                    perfil = "?"
                elif vpn >= VPN_BLOCO:
                    perfil = "BLOCO"
                elif vpn >= VPN_MISTO:
                    perfil = "MISTO"
                else:
                    perfil = "PULVERIZADO"

                if perfil in ("BLOCO", "?"):
                    lado, pos_spread = "n/d", None
                else:
                    lado, pos_spread = vies_agressao(o["medio"], o["bid"], o["ask"])

                linhas.append({
                    "venc": venc, "symbol": o["symbol"], "tipo": o["tipo"],
                    "strike": o["strike"], "volume": vol, "oi": o["oi"],
                    "media": media, "mult": mult, "nivel": nivel,
                    "money": moneyness(o["tipo"], o["strike"], spot),
                    "medio": o["medio"], "close": o["close"], "fin": o["fin"],
                    "bid": o["bid"], "ask": o["ask"], "trades": o["trades"],
                    "vpn": vpn, "perfil": perfil,
                    "lado": lado, "spread_pos": pos_spread,
                    "d_oi": d_oi, "posicao": posicao,
                    "casada": [],
                })

        if linhas:
            linhas.sort(key=lambda x: (x["mult"], x["volume"]), reverse=True)
            linhas = linhas[:TOP_POR_ATIVO]
            marcar_casadas(linhas)
            alertas[ticker] = {"spot": spot, "linhas": linhas,
                               "balanco": info_balanco(ticker)}
    return alertas


def marcar_casadas(linhas):
    for i, a in enumerate(linhas):
        for b in linhas[i + 1:]:
            maior = max(a["volume"], b["volume"])
            if maior <= 0:
                continue
            if abs(a["volume"] - b["volume"]) / maior <= TOLERANCIA_CASADA:
                a["casada"].append(b["symbol"])
                b["casada"].append(a["symbol"])


COR_NIVEL = {
    "SEM HISTORICO": C.MAGENTA,
    "EXTREMO": C.RED,
    "ALTO": C.YELLOW,
    "ELEVADO": C.CYAN,
}

COR_PERFIL = {
    "BLOCO": C.MAGENTA,
    "MISTO": C.YELLOW,
    "PULVERIZADO": C.GREEN,
    "?": C.GRAY,
}


def ordenar(alertas):
    def chave(kv):
        bal = kv[1]["balanco"]
        prox = bal["janela"] if bal and 0 <= bal["janela"] <= 20 else 999
        return (prox, -max(l["volume"] for l in kv[1]["linhas"]))
    return sorted(alertas.items(), key=chave)


def imprimir(alertas, dados, falhas, dias_validos, min_vol, mult_min, t0):
    print()
    print(C.BOLD + "=" * 78 + C.RESET)
    print(C.BOLD + "  VOLUME ANORMAL EM OPCOES" + C.RESET)
    print(f"  vencimentos: {' e '.join(data_br(v) for v in VENCIMENTOS)}")
    print(f"  criterio:    volume hoje >= {br(min_vol)} e >= {mult_min:g}x a media de {dias_validos} pregoes")
    print(C.BOLD + "=" * 78 + C.RESET)

    if not alertas:
        print()
        print(C.GRAY + "  Nada fora do padrao nos criterios atuais." + C.RESET)
        print(C.GRAY + f"  Afrouxe com: --min-vol {int(min_vol / 2)} --mult {max(2.0, mult_min - 2):g}" + C.RESET)
        print()
        return

    ordem = ordenar(alertas)

    for ticker, info in ordem:
        cab = f"\n{C.BOLD}{C.GREEN}  {ticker}{C.RESET}"
        if info["spot"]:
            cab += f"   spot R$ {brf(info['spot'])}"

        bal = info["balanco"]
        if bal and bal["dias"] >= 0:
            cor = C.RED if bal["janela"] <= 3 else C.YELLOW if bal["janela"] <= 10 else C.GRAY
            quando = "hoje" if bal["dias"] == 0 else f"em {bal['dias']}d"
            cab += f"   {cor}[balanco {quando} - {data_br(bal['data'], True)} {bal['periodo']} do pregao]{C.RESET}"
        print(cab)
        print(C.GRAY + "  " + "-" * 74 + C.RESET)

        venc_atual = None
        for l in info["linhas"]:
            if l["venc"] != venc_atual:
                venc_atual = l["venc"]
                print(f"  {C.DIM}venc {data_br(venc_atual)}{C.RESET}")

            cor = COR_NIVEL.get(l["nivel"], "")
            mult_txt = "novo" if l["mult"] == float("inf") else f"{l['mult']:.0f}x"
            media_txt = "-" if l["media"] <= 0 else br(round(l["media"]))

            print(f"    {cor}{l['symbol']:<10}{C.RESET} "
                  f"{br(l['volume']):>12}  "
                  f"{l['tipo']:<4} {l['money']:<3} "
                  f"strike {brf(l['strike']):>7}   "
                  f"{C.GRAY}med7d {media_txt:>10}{C.RESET}   "
                  f"{cor}{mult_txt:>5} {l['nivel']}{C.RESET}")

            spread = f"bid {brf(l['bid'])}/{brf(l['ask'])}" if l["ask"] > 0 else "sem book"
            oi_txt = f"oi {br(l['oi'])}"
            if l["posicao"] != "?":
                sinal = "+" if l["d_oi"] > 0 else ""
                oi_txt += f" ({sinal}{br(l['d_oi'])} {l['posicao'].lower()})"

            print(f"      {C.GRAY}R$ {brf(l['medio'], 2)} med | {spread} | "
                  f"fin R$ {br(round(l['fin']))} | {oi_txt}{C.RESET}")

            cor_perfil = COR_PERFIL.get(l["perfil"], C.GRAY)
            neg_txt = f"{br(l['trades'])} neg" if l["trades"] else "neg n/d"
            vpn_txt = f"{br(round(l['vpn']))}/neg" if l["vpn"] else "-"
            extra = ""
            if l["perfil"] == "BLOCO":
                extra = "  provavel negocio direto/mesa"
            elif l["lado"] in ("COMPRA", "VENDA"):
                extra = f"  agressao {'compradora' if l['lado'] == 'COMPRA' else 'vendedora'}"
            if l["casada"]:
                extra += f"  | qtd casada com {', '.join(l['casada'])}"

            print(f"      {cor_perfil}{l['perfil']:<11}{C.RESET} "
                  f"{C.GRAY}{neg_txt} | {vpn_txt}{C.RESET}{C.DIM}{extra}{C.RESET}")

    print()
    print(C.BOLD + "  " + "-" * 74 + C.RESET)
    print(C.BOLD + "  FORMATO PARA COLAR" + C.RESET)
    print()
    for ticker, info in ordem:
        bal = info["balanco"]
        linha = f"  Movimentacao interessante em {ticker} hoje."
        if bal and bal["dias"] >= 0:
            linha += f" Resultado em {data_br(bal['data'], True)}, {bal['periodo']} do pregao."
        print(linha)
        for l in info["linhas"]:
            extra = ""
            if l["perfil"] == "BLOCO":
                extra = " - blocos diretos"
            elif l["lado"] in ("COMPRA", "VENDA"):
                extra = f" - agressao {'compradora' if l['lado'] == 'COMPRA' else 'vendedora'}"
            if l["posicao"] != "?":
                extra += f" - {l['posicao'].lower()} de posicao"
            print(f"  {l['symbol']} - {br(l['volume'])} - "
                  f"{l['tipo'].capitalize()} {l['money']} - strike {brf(l['strike'])} - "
                  f"R$ {brf(l['medio'])} - fin R$ {br(round(l['fin']))}{extra}")
        print()

    print(C.GRAY + "  " + "-" * 74 + C.RESET)
    print(C.GRAY + f"  {len(dados)} ativos com opcoes nos vencimentos | "
                   f"{len(alertas)} com alerta | {time.time() - t0:.1f}s" + C.RESET)
    if falhas:
        nomes = ", ".join(sorted(falhas)[:12])
        extra = f" (+{len(falhas) - 12})" if len(falhas) > 12 else ""
        print(C.GRAY + f"  sem opcoes: {nomes}{extra}" + C.RESET)
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-vol", type=int, default=MIN_VOLUME_HOJE)
    ap.add_argument("--mult", type=float, default=MIN_MULTIPLICADOR)
    ap.add_argument("--dias", type=int, default=DIAS_HISTORICO)
    ap.add_argument("--ativos", type=str, default=None)
    ap.add_argument("--balanco-ate", type=int, default=None)
    args = ap.parse_args()

    if args.ativos:
        ativos = [a.strip().upper() for a in args.ativos.split(",") if a.strip()]
    else:
        ativos = ATIVOS

    if args.balanco_ate is not None:
        ativos = [t for t in ativos
                  if (b := info_balanco(t)) and 0 <= b["janela"] <= args.balanco_ate]
        if not ativos:
            print(f"{C.RED}Nenhum ativo com balanco nos proximos {args.balanco_ate} dias.{C.RESET}")
            return 1

    t0 = time.time()
    api = OpLab(carregar_token())

    print(f"{C.CYAN}> baixando opcoes de {len(ativos)} ativos...{C.RESET}")
    dados, falhas = coletar(api, ativos)
    if not dados:
        print(f"{C.RED}Nenhum ativo retornou opcoes nos vencimentos configurados.{C.RESET}")
        return 1

    faltando = [t for t, i in dados.items() if not i["spot"]]
    if faltando:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS_ATIVOS) as ex:
            for t, fut in [(t, ex.submit(api.spot, t)) for t in faltando]:
                dados[t]["spot"] = fut.result()

    candidatas = sorted({
        o["symbol"]
        for i in dados.values()
        for lst in i["vencimentos"].values()
        for o in lst
        if o["volume"] >= args.min_vol
    })

    if not candidatas:
        imprimir({}, dados, falhas, 0, args.min_vol, args.mult, t0)
        return 0

    dias = pregoes_anteriores(args.dias, MAX_DIAS_BUSCA)
    print(f"{C.CYAN}> {len(candidatas)} series acima de {br(args.min_vol)} hoje "
          f"-> {len(dias)} pregoes de referencia...{C.RESET}")

    hist, dias_validos = buscar_historico(api, candidatas, dias)
    alertas = analisar(dados, hist, args.min_vol, args.mult)
    imprimir(alertas, dados, falhas, dias_validos, args.min_vol, args.mult, t0)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrompido")
        sys.exit(130)
    except Exception as e:
        print(f"{C.RED}erro: {e}{C.RESET}")
        sys.exit(1)
