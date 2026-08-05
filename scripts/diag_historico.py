"""
diag_historico.py — descobre EXATAMENTE em qual etapa a analise historica
descarta cada data (o codigo faz `continue` silencioso, por isso o F12 fica limpo).

Uso:
    python scripts/diag_historico.py BBDC4 20260821 10
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests
from sqlalchemy import text

from backend.pro.historical_service import HistoricalAnalyzer

TICKER = (sys.argv[1] if len(sys.argv) > 1 else "BBDC4").upper()
VENC   = sys.argv[2] if len(sys.argv) > 2 else "20260821"
DAYS   = int(sys.argv[3] if len(sys.argv) > 3 else 10)

symbol = TICKER if TICKER.endswith(".SA") else f"{TICKER}.SA"
clean  = TICKER.replace(".SA", "")

an = HistoricalAnalyzer()
dp = an.data_provider

print("=" * 78)
print(f"DIAGNOSTICO  ticker={clean}  vencimento={VENC}  sessoes={DAYS}")
print("=" * 78)

# ── 1) O que a Oplab realmente devolve no endpoint historico ────────────────
to_date   = datetime.now().strftime("%Y-%m-%d")
from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
url = f"{dp.oplab_url}/market/historical/options/{clean}/{from_date}/{to_date}"
print(f"\n[1] OPLAB  GET {url}")
try:
    r = requests.get(url, headers=dp.headers, timeout=20)
    print(f"    status HTTP: {r.status_code}")
    raw = r.json() if r.status_code == 200 else []
    if raw:
        df = pd.DataFrame(raw)
        df["time"] = pd.to_datetime(df["time"])
        por_dia = df.groupby(df["time"].dt.date).size().sort_index()
        print("    datas devolvidas pela Oplab (linhas por dia):")
        for d, n in por_dia.items():
            print(f"        {d}  ->  {n}")
        print(f"    ULTIMA DATA NA OPLAB: {por_dia.index.max()}")
    else:
        print("    !! Oplab nao devolveu nada")
except Exception as e:
    print(f"    !! ERRO Oplab: {e}")

# ── 2) O que o banco tem ────────────────────────────────────────────────────
print(f"\n[2] BANCO  ultimas datas de {clean} / vencimento {VENC}")
exp_date = datetime.strptime(VENC, "%Y%m%d").date()
with dp.db_engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT data_referencia, COUNT(*) AS n
        FROM opcoes_b3
        WHERE ticker = :t AND vencimento = :v
        GROUP BY data_referencia
        ORDER BY data_referencia DESC
        LIMIT :lim
    """), {"t": clean, "v": exp_date, "lim": DAYS}).fetchall()
for d, n in rows:
    print(f"        {d}  ->  {n} linhas")
if not rows:
    print("        !! nenhuma linha para esse ticker+vencimento")

# ── 3) Replay da malha do analyze_historical, etapa por etapa ───────────────
print(f"\n[3] REPLAY do loop de analyze_historical()")
print(f"    {'DATA':<12} {'SPOT':>9}  {'OPLAB':>6}  {'BANCO':>6}  {'GEX':>5}  {'VIA':<8} RESULTADO")
print("    " + "-" * 76)

business_dates = dp.get_business_days(DAYS)
expirations    = dp.get_available_expirations(symbol)

for date_obj in business_dates:
    ds = date_obj.strftime("%Y-%m-%d")

    spot = dp.get_historical_spot_price(symbol, date_obj)
    if not spot:
        print(f"    {ds:<12} {'--':>9}  {'':>6}  {'':>6}  {'':>5}  {'':<8} DESCARTADA: sem spot (yfinance/Oplab)")
        continue

    odf = dp.get_oplab_historical_data(symbol, target_date=date_obj)
    if odf.empty:
        print(f"    {ds:<12} {spot:>9.2f}  {0:>6}  {'':>6}  {'':>5}  {'':<8} DESCARTADA: Oplab sem gregas nesta data")
        continue

    oi = dp.get_floqui_historical(symbol, VENC, date_obj)
    if not oi:
        print(f"    {ds:<12} {spot:>9.2f}  {len(odf):>6}  {0:>6}  {'':>5}  {'':<8} DESCARTADA: banco sem OI nesta data")
        continue

    # caminho de producao: casa por codigo da opcao, strike so como reserva
    oi_cod = dp.get_floqui_historical_by_code(symbol, VENC, date_obj)
    via    = "codigo" if not an._gex_por_codigo(odf, oi_cod, spot).empty else "strike"

    gex = an.calculate_gex(odf, oi, spot, oi_cod)
    if gex.empty:
        print(f"    {ds:<12} {spot:>9.2f}  {len(odf):>6}  {len(oi):>6}  {0:>5}  {'--':<8} DESCARTADA: nenhum contrato casou")
        continue

    print(f"    {ds:<12} {spot:>9.2f}  {len(odf):>6}  {len(oi):>6}  {len(gex):>5}  {via:<8} OK")

print("\nFim. A coluna RESULTADO mostra a causa exata de cada data faltante.")
