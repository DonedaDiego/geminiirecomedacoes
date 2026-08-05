"""
strike_matching.py — traducao de strikes entre Oplab e banco B3.

PROBLEMA
--------
Em datas 'ex' (especie_papel vira EJ / EJS / ED / ES), a B3 ajusta TODOS os
strikes da serie no mesmo pregao. O banco entra ajustado no mesmo dia, mas a
Oplab aplica o ajuste com ~1 pregao de defasagem. Nesse intervalo as duas
grades ficam deslocadas em alguns centavos e qualquer cruzamento por
igualdade de strike (`f"{strike}_CALL"`) zera 100% dos casamentos — sem erro,
sem excecao, so numeros sumindo.

SOLUCAO
-------
O CODIGO da opcao nao muda em data ex. O banco guarda em `serie` e a Oplab
devolve em `symbol`. Cruzando por codigo, descobrimos a que strike do banco
cada strike da Oplab corresponde.

USO
---
    from .strike_matching import fetch_strike_translation

    strike_map = fetch_strike_translation(engine, symbol, exp_date, oplab_df)
    ...
    sk = strike_map.get(float(strike), float(strike))
    call_key = f"{sk}_CALL"
"""

import logging
from collections import defaultdict

from sqlalchemy import text


def fetch_strike_translation(db_engine, symbol, exp_date, oplab_df):
    """
    Monta {strike_oplab: strike_banco} para um ticker/vencimento.

    Em dia normal o mapa e a identidade (custo desprezivel). Em dia ex ele
    corrige a defasagem. Se algo faltar, retorna {} e o chamador segue com o
    comportamento antigo.
    """
    try:
        if oplab_df is None or oplab_df.empty or 'symbol' not in oplab_df.columns:
            return {}

        symbol_clean = str(symbol).replace('.SA', '').upper()

        rows = None
        with db_engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT serie, preco_exercicio
                FROM opcoes_b3
                WHERE ticker = :symbol
                  AND vencimento = :vencimento
                  AND serie IS NOT NULL
                  AND data_referencia = (
                      SELECT MAX(data_referencia) FROM opcoes_b3 WHERE ticker = :symbol
                  )
            """), {'symbol': symbol_clean, 'vencimento': exp_date}).fetchall()

        if not rows:
            return {}

        strike_por_codigo = {
            str(r[0]).strip().upper(): float(r[1])
            for r in rows if r[0] is not None and r[1] is not None
        }
        if not strike_por_codigo:
            return {}

        # agrupa: strike da Oplab -> strikes do banco vistos via codigo
        candidatos = defaultdict(set)
        for op_symbol, op_strike in zip(oplab_df['symbol'], oplab_df['strike']):
            alvo = strike_por_codigo.get(str(op_symbol).strip().upper())
            if alvo is None:
                continue
            try:
                candidatos[float(op_strike)].add(alvo)
            except (TypeError, ValueError):
                continue

        # so aceita traducao nao ambigua (1 strike da Oplab -> 1 strike do banco)
        mapa = {origem: next(iter(destinos))
                for origem, destinos in candidatos.items() if len(destinos) == 1}

        deslocados = sum(1 for o, d in mapa.items() if abs(o - d) > 1e-9)
        if deslocados:
            logging.warning(
                f"{symbol_clean}: grade de strikes deslocada (data ex-proventos) — "
                f"{deslocados} de {len(mapa)} strikes traduzidos pelo codigo da opcao"
            )
        return mapa

    except Exception as e:
        logging.error(f"Erro ao traduzir strikes de {symbol}: {e}")
        return {}
