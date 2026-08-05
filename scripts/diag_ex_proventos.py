"""
diag_ex_proventos.py — lista quais tickers ficaram 'ex' recentemente e quais
tiveram a grade de strikes deslocada pela B3.

E o deslocamento da grade que quebra o casamento por igualdade exata em
gamma/delta/theta/vega/historical. Hoje e o BBDC4; no mes que vem sera outro.

Uso:
    python scripts/diag_ex_proventos.py [n_datas]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.INFO)

from sqlalchemy import text
from backend.pro.historical_service import HistoricalDataProvider

N = int(sys.argv[1] if len(sys.argv) > 1 else 4)
dp = HistoricalDataProvider()

with dp.db_engine.connect() as conn:
    datas = sorted(r[0] for r in conn.execute(text("""
        SELECT DISTINCT data_referencia FROM opcoes_b3
        ORDER BY data_referencia DESC LIMIT :n
    """), {"n": N}).fetchall())

    print("=" * 78)
    print(f"[A] especie_papel com marcacao 'ex' — datas {datas[0]} .. {datas[-1]}")
    print("=" * 78)
    rows = conn.execute(text("""
        SELECT data_referencia, ticker, especie_papel, COUNT(*) AS n
        FROM opcoes_b3
        WHERE data_referencia = ANY(:ds)
          AND (especie_papel LIKE '%%EJ%%' OR especie_papel LIKE '%%ED%%'
               OR especie_papel LIKE '%%EB%%' OR especie_papel LIKE '%%EX%%'
               OR especie_papel LIKE '%%ES%%')
        GROUP BY data_referencia, ticker, especie_papel
        ORDER BY data_referencia, ticker
    """), {"ds": datas}).fetchall()

    if rows:
        for d, t, esp, n in rows:
            print(f"  {d}  {t:<8} {esp:<14} {n:>6} linhas")
    else:
        print("  nenhum ticker marcado como ex nessas datas")

    # ── B) grade de strikes deslocada entre datas consecutivas ──────────────
    print("\n" + "=" * 78)
    print("[B] Tickers com a GRADE DE STRIKES deslocada (comparando dia a dia)")
    print("=" * 78)

    tickers = [r[0] for r in conn.execute(text("""
        SELECT DISTINCT ticker FROM opcoes_b3 WHERE data_referencia = :d
    """), {"d": datas[-1]}).fetchall()]

    achou = False
    for t in sorted(tickers):
        grades = {}
        for d in datas:
            s = conn.execute(text("""
                SELECT DISTINCT preco_exercicio FROM opcoes_b3
                WHERE ticker = :t AND data_referencia = :d
                ORDER BY preco_exercicio LIMIT 12
            """), {"t": t, "d": d}).fetchall()
            if s:
                grades[d] = [float(x[0]) for x in s]

        ds = sorted(grades)
        for a, b in zip(ds, ds[1:]):
            ga, gb = grades[a], grades[b]
            comum = min(len(ga), len(gb))
            if comum < 3:
                continue
            difs = [round(gb[i] - ga[i], 2) for i in range(comum)]
            off  = max(set(difs), key=difs.count)
            if off != 0 and difs.count(off) >= comum * 0.6:
                achou = True
                print(f"  {t:<8} {a} -> {b}   offset {off:+.2f}   "
                      f"ex.: {ga[0]:.2f} -> {gb[0]:.2f}")

    if not achou:
        print("  nenhuma grade deslocada nesse intervalo")

print("\nQuem aparece em [B] e exatamente quem quebra o casamento por strike.")
