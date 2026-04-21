#!/usr/bin/env python3
# vencimentos_opcoes_b3.py

import psycopg2

conn = psycopg2.connect(
    host="ballast.proxy.rlwy.net",
    port=33654,
    dbname="railway",
    user="postgres",
    password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
)
cur = conn.cursor()

cur.execute("""
    SELECT
        vencimento,
        tipo_opcao,
        COUNT(*)          AS total_series,
        COUNT(DISTINCT ticker) AS tickers,
        MIN(data_referencia)  AS data_min,
        MAX(data_referencia)  AS data_max
    FROM opcoes_b3
    GROUP BY vencimento, tipo_opcao
    ORDER BY vencimento, tipo_opcao
""")

rows = cur.fetchall()

print(f"{'VENCIMENTO':<14} {'TIPO':<6} {'SERIES':>10} {'TICKERS':>10} {'DATA_MIN':<12} {'DATA_MAX':<12}")
print("-" * 70)

for vencimento, tipo, total, tickers, data_min, data_max in rows:
    print(f"{str(vencimento):<14} {tipo:<6} {total:>10,} {tickers:>10,} {str(data_min):<12} {str(data_max):<12}")

cur.close()
conn.close()