"""
diag_strikes.py — compara as CHAVES de casamento (strike + tipo_opcao) entre
o banco e a Oplab, dia a dia. O GEX zerou em 03/08 e 04/08 mesmo com 133 linhas
no banco, logo a chave `f"{strike}_{tipo}"` deixou de bater.

Uso:
    python scripts/diag_strikes.py BBDC4 20260821
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

# ── A) Banco: valores brutos por data ───────────────────────────────────────
print("=" * 80)
print(f"[A] BANCO — {clean} / venc {VENC}: tipo_opcao e preco_exercicio por data")
print("=" * 80)
with dp.db_engine.connect() as conn:
    datas = [r[0] for r in conn.execute(text("""
        SELECT DISTINCT data_referencia FROM opcoes_b3
        WHERE ticker = :t AND vencimento = :v
        ORDER BY data_referencia DESC LIMIT 6
    """), {"t": clean, "v": exp_d}).fetchall()]

    for d in sorted(datas):
        rows = conn.execute(text("""
            SELECT preco_exercicio, tipo_opcao, qtd_total, serie, especie_papel
            FROM opcoes_b3
            WHERE ticker = :t AND vencimento = :v AND data_referencia = :d
            ORDER BY preco_exercicio
        """), {"t": clean, "v": exp_d, "d": d}).fetchall()

        strikes = sorted({float(r[0]) for r in rows})
        tipos   = sorted({str(r[1]) for r in rows})
        especie = sorted({str(r[4]) for r in rows})
        print(f"\n  {d}   linhas={len(rows)}")
        print(f"    tipo_opcao distintos : {tipos}")
        print(f"    especie_papel        : {especie}")
        print(f"    strike min/max       : {min(strikes):.4f} .. {max(strikes):.4f}")
        print(f"    primeiros strikes    : {[round(s, 4) for s in strikes[:8]]}")
        print(f"    chaves de exemplo    : {[f'{s}_{rows[0][1]}' for s in strikes[:3]]}")

# ── B) Oplab: strikes por data ──────────────────────────────────────────────
print("\n" + "=" * 80)
print(f"[B] OPLAB — strikes devolvidos por data (venc {exp_d})")
print("=" * 80)
to_date   = datetime.now().strftime("%Y-%m-%d")
from_date = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
url = f"{dp.oplab_url}/market/historical/options/{clean}/{from_date}/{to_date}"
r = requests.get(url, headers=dp.headers, timeout=20)
df = pd.DataFrame(r.json())
df["time"] = pd.to_datetime(df["time"])

for d in sorted(datas):
    sub = df[df["time"].dt.date == d]
    if sub.empty:
        print(f"\n  {d}   -- Oplab sem dados")
        continue
    strikes = sorted({float(x) for x in sub["strike"]})
    tipos   = sorted({str(x) for x in sub["type"]})
    print(f"\n  {d}   linhas={len(sub)}")
    print(f"    type distintos    : {tipos}")
    print(f"    strike min/max    : {min(strikes):.4f} .. {max(strikes):.4f}")
    print(f"    primeiros strikes : {[round(s, 4) for s in strikes[:8]]}")

# ── C) Interseccao real das chaves ──────────────────────────────────────────
print("\n" + "=" * 80)
print("[C] INTERSECCAO das chaves banco x Oplab (o que calculate_gex procura)")
print("=" * 80)
for d in sorted(datas):
    dt = datetime.combine(d, datetime.min.time())
    oi = dp.get_floqui_historical(f"{clean}.SA", VENC, dt)
    sub = df[df["time"].dt.date == d]
    if not oi or sub.empty:
        print(f"  {d}   banco={len(oi)}  oplab={len(sub)}  -> sem como cruzar")
        continue
    chaves_oplab = {f"{float(s)}_{str(t).upper()}" for s, t in zip(sub["strike"], sub["type"])}
    inter = chaves_oplab & set(oi.keys())
    print(f"  {d}   chaves banco={len(oi)}  chaves oplab={len(chaves_oplab)}  CASADAS={len(inter)}")
    if not inter:
        print(f"       exemplo banco : {sorted(oi.keys())[:4]}")
        print(f"       exemplo oplab : {sorted(chaves_oplab)[:4]}")
