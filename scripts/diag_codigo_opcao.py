"""
diag_codigo_opcao.py — verifica se da para cruzar Oplab x banco pelo CODIGO da
opcao (serie) em vez do strike.

Motivo: o strike muda em datas ex-proventos e as duas fontes aplicam o ajuste
em dias diferentes. O codigo da opcao NAO muda — se ele existir dos dois lados,
o casamento fica imune a proventos.

Uso:
    python scripts/diag_codigo_opcao.py BBDC4 20260821
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.INFO)

import pandas as pd
import requests
from sqlalchemy import text

from backend.pro.historical_service import HistoricalDataProvider

TICKER = (sys.argv[1] if len(sys.argv) > 1 else "BBDC4").upper()
VENC   = sys.argv[2] if len(sys.argv) > 2 else "20260821"
clean  = TICKER.replace(".SA", "")
exp_d  = datetime.strptime(VENC, "%Y%m%d").date()

dp = HistoricalDataProvider()

# ── A) Colunas que a Oplab devolve ─────────────────────────────────────────
to_date   = datetime.now().strftime("%Y-%m-%d")
from_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
url = f"{dp.oplab_url}/market/historical/options/{clean}/{from_date}/{to_date}"
r  = requests.get(url, headers=dp.headers, timeout=20)
df = pd.DataFrame(r.json())

print("=" * 78)
print("[A] COLUNAS devolvidas pela Oplab")
print("=" * 78)
print(f"  {list(df.columns)}")
print("\n  primeira linha:")
for k, v in df.iloc[0].items():
    print(f"    {k:<22} = {v!r}")

# ── B) Coluna serie no banco ───────────────────────────────────────────────
print("\n" + "=" * 78)
print("[B] Coluna 'serie' no banco")
print("=" * 78)
with dp.db_engine.connect() as conn:
    ultima = conn.execute(text("""
        SELECT MAX(data_referencia) FROM opcoes_b3 WHERE ticker = :t
    """), {"t": clean}).scalar()

    rows = conn.execute(text("""
        SELECT serie, tipo_opcao, preco_exercicio, qtd_total
        FROM opcoes_b3
        WHERE ticker = :t AND vencimento = :v AND data_referencia = :d
        ORDER BY preco_exercicio LIMIT 10
    """), {"t": clean, "v": exp_d, "d": ultima}).fetchall()

print(f"  data_referencia = {ultima}")
for s, tp, px, q in rows:
    print(f"    serie={s!r:<16} {tp:<5} strike={float(px):<8.2f} oi={q}")

# ── C) Teste do cruzamento por codigo ──────────────────────────────────────
print("\n" + "=" * 78)
print("[C] CRUZAMENTO por codigo — Oplab x banco")
print("=" * 78)

col_cod = next((c for c in ("symbol", "ticker", "code", "name", "option")
                if c in df.columns), None)
if not col_cod:
    print("  !! Oplab nao devolve coluna de codigo — cruzar por codigo nao da.")
    sys.exit(0)

print(f"  usando coluna Oplab: '{col_cod}'")
df["time"] = pd.to_datetime(df["time"])
sub = df[df["time"].dt.date == ultima]

cod_oplab = {str(x).strip().upper() for x in sub[col_cod]}
with dp.db_engine.connect() as conn:
    cod_banco = {str(x[0]).strip().upper() for x in conn.execute(text("""
        SELECT DISTINCT serie FROM opcoes_b3
        WHERE ticker = :t AND vencimento = :v AND data_referencia = :d
    """), {"t": clean, "v": exp_d, "d": ultima}).fetchall()}

inter = cod_oplab & cod_banco
print(f"  codigos Oplab (dia todo) : {len(cod_oplab)}")
print(f"  codigos banco (1 venc)   : {len(cod_banco)}")
print(f"  CASADOS                  : {len(inter)}")
print(f"  amostra Oplab : {sorted(cod_oplab)[:6]}")
print(f"  amostra banco : {sorted(cod_banco)[:6]}")
if inter:
    print(f"  amostra casada: {sorted(inter)[:6]}")
    print("\n  >> Cruzar por codigo FUNCIONA e e imune a proventos.")
else:
    print("\n  >> Codigos nao batem; manter cruzamento por strike com offset.")
