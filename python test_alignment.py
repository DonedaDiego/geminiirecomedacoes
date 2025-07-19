#!/usr/bin/env python3
"""
test_alignment.py - Testador para comparar vol_regimes vs bandas_pro
Vamos direto ao ponto! 🎯
"""

import pandas as pd
import yfinance as yf
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_vol_regimes_logic(ticker="PETR4"):
    """Testar a lógica do vol_regimes_service.py"""
    logger.info("=== TESTANDO VOL_REGIMES_SERVICE.PY ===")
    
    # LÓGICA EXATA DO VOL_REGIMES
    original_ticker = ticker
    if not ticker.endswith('.SA') and not ticker.startswith('^'):
        ticker = ticker + '.SA'
    
    logger.info(f"🔍 TICKER ORIGINAL: {original_ticker}")
    logger.info(f"🔍 TICKER PROCESSADO: {ticker}")
    logger.info(f"🔍 PERIOD: 6mo")
    
    # Download dados
    data = yf.download(ticker, start=None, end=None, period='6mo', interval='1d')
    
    # Tratamento de colunas multinível
    if hasattr(data.columns, 'get_level_values') and ticker in data.columns.get_level_values(1):
        data = data.xs(ticker, axis=1, level=1)
        logger.info("✅ Extraído dados de coluna multinível")
    
    if data.empty:
        logger.error(f"❌ Nenhum dado encontrado para {ticker}")
        return None
    
    # Reset index e calcular retornos
    data.reset_index(inplace=True)
    data['Returns'] = data['Close'].pct_change()
    data['Log_Returns'] = pd.Series([0.0] * len(data))  # Placeholder
    data.dropna(inplace=True)
    
    logger.info(f"✅ VOL_REGIMES - Dados carregados: {len(data)} registros")
    logger.info(f"✅ VOL_REGIMES - Período: {data['Date'].iloc[0]} até {data['Date'].iloc[-1]}")
    logger.info(f"✅ VOL_REGIMES - Último preço: R$ {data['Close'].iloc[-1]:.2f}")
    
    return {
        'ticker_processado': ticker,
        'data': data,
        'ultimo_preco': data['Close'].iloc[-1],
        'total_registros': len(data),
        'data_inicial': data['Date'].iloc[0],
        'data_final': data['Date'].iloc[-1]
    }

def test_bandas_pro_logic(ticker="PETR4"):
    """Testar a lógica do bandas_pro_service.py ATUAL"""
    logger.info("=== TESTANDO BANDAS_PRO_SERVICE.PY (ATUAL) ===")
    
    # LÓGICA ATUAL DO BANDAS_PRO (ANTES DA CORREÇÃO)
    original_ticker = ticker
    if not ticker.endswith('.SA') and not ticker.startswith('^'):
        ticker = ticker + '.SA'
    
    logger.info(f"🔍 TICKER ORIGINAL: {original_ticker}")
    logger.info(f"🔍 TICKER PROCESSADO: {ticker}")
    logger.info(f"🔍 PERIOD: 6mo")
    
    # Download dados
    data = yf.download(ticker, start=None, end=None, period='6mo', interval='1d')
    
    # Tratamento de colunas multinível (IGUAL ao vol_regimes agora)
    if hasattr(data.columns, 'get_level_values') and ticker in data.columns.get_level_values(1):
        data = data.xs(ticker, axis=1, level=1)
        logger.info("✅ Extraído dados de coluna multinível")
    
    if data.empty:
        logger.error(f"❌ Nenhum dado encontrado para {ticker}")
        return None
    
    # Reset index e calcular retornos
    data.reset_index(inplace=True)
    data['Returns'] = data['Close'].pct_change()
    data['Log_Returns'] = pd.Series([0.0] * len(data))  # Placeholder
    data.dropna(inplace=True)
    
    logger.info(f"✅ BANDAS_PRO - Dados carregados: {len(data)} registros")
    logger.info(f"✅ BANDAS_PRO - Período: {data['Date'].iloc[0]} até {data['Date'].iloc[-1]}")
    logger.info(f"✅ BANDAS_PRO - Último preço: R$ {data['Close'].iloc[-1]:.2f}")
    
    return {
        'ticker_processado': ticker,
        'data': data,
        'ultimo_preco': data['Close'].iloc[-1],
        'total_registros': len(data),
        'data_inicial': data['Date'].iloc[0],
        'data_final': data['Date'].iloc[-1]
    }

def compare_results(vol_regimes_result, bandas_pro_result):
    """Comparar os resultados dos dois sistemas"""
    logger.info("=== COMPARAÇÃO DOS RESULTADOS ===")
    
    if not vol_regimes_result or not bandas_pro_result:
        logger.error("❌ Um dos sistemas falhou!")
        return False
    
    # Comparar tickers processados
    ticker_match = vol_regimes_result['ticker_processado'] == bandas_pro_result['ticker_processado']
    logger.info(f"🔍 TICKER PROCESSADO - VOL: {vol_regimes_result['ticker_processado']}")
    logger.info(f"🔍 TICKER PROCESSADO - PRO: {bandas_pro_result['ticker_processado']}")
    logger.info(f"✅ TICKERS IGUAIS: {ticker_match}")
    
    # Comparar número de registros
    records_match = vol_regimes_result['total_registros'] == bandas_pro_result['total_registros']
    logger.info(f"🔍 REGISTROS - VOL: {vol_regimes_result['total_registros']}")
    logger.info(f"🔍 REGISTROS - PRO: {bandas_pro_result['total_registros']}")
    logger.info(f"✅ REGISTROS IGUAIS: {records_match}")
    
    # Comparar datas
    data_inicial_match = vol_regimes_result['data_inicial'] == bandas_pro_result['data_inicial']
    data_final_match = vol_regimes_result['data_final'] == bandas_pro_result['data_final']
    logger.info(f"🔍 DATA INICIAL - VOL: {vol_regimes_result['data_inicial']}")
    logger.info(f"🔍 DATA INICIAL - PRO: {bandas_pro_result['data_inicial']}")
    logger.info(f"✅ DATA INICIAL IGUAL: {data_inicial_match}")
    logger.info(f"🔍 DATA FINAL - VOL: {vol_regimes_result['data_final']}")
    logger.info(f"🔍 DATA FINAL - PRO: {bandas_pro_result['data_final']}")
    logger.info(f"✅ DATA FINAL IGUAL: {data_final_match}")
    
    # Comparar preços (MAIS IMPORTANTE)
    price_diff = abs(vol_regimes_result['ultimo_preco'] - bandas_pro_result['ultimo_preco'])
    price_match = price_diff < 0.01  # Diferença menor que 1 centavo
    
    logger.info(f"🔍 ÚLTIMO PREÇO - VOL: R$ {vol_regimes_result['ultimo_preco']:.4f}")
    logger.info(f"🔍 ÚLTIMO PREÇO - PRO: R$ {bandas_pro_result['ultimo_preco']:.4f}")
    logger.info(f"🔍 DIFERENÇA: R$ {price_diff:.4f}")
    logger.info(f"✅ PREÇOS IGUAIS: {price_match}")
    
    # Resultado final
    all_match = ticker_match and records_match and data_inicial_match and data_final_match and price_match
    
    logger.info("=== RESULTADO FINAL ===")
    if all_match:
        logger.info("🎯 SUCESSO! Os dois sistemas estão perfeitamente alinhados!")
    else:
        logger.warning("⚠️ PROBLEMA! Há diferenças entre os sistemas:")
        if not ticker_match:
            logger.warning("   - Tickers processados diferentes")
        if not records_match:
            logger.warning("   - Número de registros diferentes")
        if not data_inicial_match or not data_final_match:
            logger.warning("   - Períodos de dados diferentes")
        if not price_match:
            logger.warning(f"   - Preços diferentes (diferença: R$ {price_diff:.4f})")
    
    return all_match

def test_cache_differences():
    """Testar se há diferenças por cache do yfinance"""
    logger.info("=== TESTANDO DIFERENÇAS DE CACHE ===")
    
    ticker = "PETR4.SA"
    
    # Primeira chamada
    logger.info("📥 PRIMEIRA CHAMADA...")
    data1 = yf.download(ticker, start=None, end=None, period='6mo', interval='1d')
    if hasattr(data1.columns, 'get_level_values') and ticker in data1.columns.get_level_values(1):
        data1 = data1.xs(ticker, axis=1, level=1)
    data1.reset_index(inplace=True)
    
    # Segunda chamada (imediata)
    logger.info("📥 SEGUNDA CHAMADA (IMEDIATA)...")
    data2 = yf.download(ticker, start=None, end=None, period='6mo', interval='1d')
    if hasattr(data2.columns, 'get_level_values') and ticker in data2.columns.get_level_values(1):
        data2 = data2.xs(ticker, axis=1, level=1)
    data2.reset_index(inplace=True)
    
    # Comparar
    if len(data1) == len(data2):
        price_diff = abs(data1['Close'].iloc[-1] - data2['Close'].iloc[-1])
        logger.info(f"✅ CACHE TEST - Mesmo tamanho: {len(data1)} registros")
        logger.info(f"✅ CACHE TEST - Preço 1: R$ {data1['Close'].iloc[-1]:.4f}")
        logger.info(f"✅ CACHE TEST - Preço 2: R$ {data2['Close'].iloc[-1]:.4f}")
        logger.info(f"✅ CACHE TEST - Diferença: R$ {price_diff:.4f}")
        
        if price_diff < 0.01:
            logger.info("🎯 CACHE OK - Não há problema de cache")
        else:
            logger.warning("⚠️ CACHE PROBLEM - yfinance retornando dados diferentes!")
    else:
        logger.warning(f"⚠️ CACHE PROBLEM - Tamanhos diferentes: {len(data1)} vs {len(data2)}")

def run_full_test():
    """Executar teste completo"""
    logger.info("🚀 INICIANDO TESTE COMPLETO DE ALINHAMENTO")
    logger.info("=" * 60)
    
    # Teste individual dos sistemas
    vol_result = test_vol_regimes_logic("PETR4")
    bandas_result = test_bandas_pro_logic("PETR4")
    
    # Comparação
    if vol_result and bandas_result:
        success = compare_results(vol_result, bandas_result)
    else:
        success = False
    
    # Teste de cache
    test_cache_differences()
    
    logger.info("=" * 60)
    logger.info(f"🏁 TESTE CONCLUÍDO - SUCESSO: {success}")
    
    return success

def test_with_debug_info():
    """Teste com informações de debug detalhadas"""
    logger.info("🔬 TESTE DETALHADO COM DEBUG")
    
    ticker = "PETR4"
    
    # Processar ticker igual aos dois sistemas
    if not ticker.endswith('.SA') and not ticker.startswith('^'):
        ticker = ticker + '.SA'
    
    logger.info(f"🎯 TICKER FINAL: {ticker}")
    
    # Download com debug
    logger.info("📡 Fazendo download do yfinance...")
    data = yf.download(ticker, start=None, end=None, period='6mo', interval='1d', progress=False)
    
    logger.info(f"📊 COLUNAS RETORNADAS: {list(data.columns)}")
    logger.info(f"📊 TIPO DAS COLUNAS: {type(data.columns)}")
    
    if hasattr(data.columns, 'get_level_values'):
        logger.info(f"📊 LEVELS DISPONÍVEIS: {data.columns.get_level_values(1).tolist()}")
        
        if ticker in data.columns.get_level_values(1):
            logger.info(f"✅ TICKER {ticker} ENCONTRADO NAS COLUNAS")
            data = data.xs(ticker, axis=1, level=1)
            logger.info(f"✅ DADOS EXTRAÍDOS: {list(data.columns)}")
        else:
            logger.warning(f"⚠️ TICKER {ticker} NÃO ENCONTRADO NAS COLUNAS")
    else:
        logger.info("📊 COLUNAS SIMPLES (não multinível)")
    
    logger.info(f"📊 SHAPE FINAL: {data.shape}")
    logger.info(f"📊 PRIMEIRAS 3 LINHAS:")
    print(data.head(3))
    
    if not data.empty:
        data.reset_index(inplace=True)
        logger.info(f"🎯 ÚLTIMO PREÇO: R$ {data['Close'].iloc[-1]:.4f}")
        logger.info(f"🎯 DATA INICIAL: {data['Date'].iloc[0]}")
        logger.info(f"🎯 DATA FINAL: {data['Date'].iloc[-1]}")

if __name__ == "__main__":
    print("🧪 TESTADOR DE ALINHAMENTO - VOL_REGIMES vs BANDAS_PRO")
    print("=" * 60)
    
    # Escolher tipo de teste
    print("Escolha o tipo de teste:")
    print("1. Teste completo de alinhamento")
    print("2. Teste com debug detalhado")
    print("3. Apenas teste de cache")
    
    choice = input("Digite sua escolha (1-3): ").strip()
    
    if choice == "1":
        run_full_test()
    elif choice == "2":
        test_with_debug_info()
    elif choice == "3":
        test_cache_differences()
    else:
        print("❌ Opção inválida. Executando teste completo...")
        run_full_test()