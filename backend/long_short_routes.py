from flask import Blueprint, jsonify, request

from long_short_service import LongShortService
import pandas as pd
import json
import numpy as np
from datetime import datetime, timedelta

# Criar Blueprint
long_short_bp = Blueprint('long_short', __name__)

# Instância do serviço
service = LongShortService()

@long_short_bp.route('/api/long-short/analyze', methods=['POST'])
def analisar_long_short():
    """Executar análise completa de Long & Short"""
    try:
        data = request.get_json() or {}
        
        # Parâmetros da análise
        dias = data.get('dias', 240)
        zscore_minimo = data.get('zscore_minimo', 2.0)
        investimento = data.get('investimento', 10000)
        
        # Validações
        if not isinstance(dias, int) or dias < 60 or dias > 500:
            return jsonify({
                'success': False,
                'error': 'Dias deve ser um número entre 60 e 500'
            }), 400
        
        if not isinstance(zscore_minimo, (int, float)) or zscore_minimo < 1.0 or zscore_minimo > 4.0:
            return jsonify({
                'success': False,
                'error': 'Z-Score mínimo deve ser um número entre 1.0 e 4.0'
            }), 400
        
        if not isinstance(investimento, (int, float)) or investimento < 1000:
            return jsonify({
                'success': False,
                'error': 'Investimento deve ser maior que R$ 1.000'
            }), 400
        
        # Executar análise
        resultado = service.executar_analise_completa(
            dias=dias,
            zscore_minimo=zscore_minimo,
            investimento=investimento
        )
        
        # ✅ CORRIGIR SERIALIZAÇÃO DO CACHE
        if resultado['success'] and 'dados_cache' in resultado['data']:
            try:
                # Remover dados_cache da resposta principal para evitar problemas
                dados_para_cache = resultado['data'].pop('dados_cache', None)
                
                # Criar um cache simplificado e mais robusto
                if dados_para_cache:
                    dados_df = pd.read_json(dados_para_cache, orient='split')
                    
                    # Serializar de forma mais robusta
                    cache_otimizado = {
                        'index': dados_df.index.strftime('%Y-%m-%d').tolist(),
                        'columns': dados_df.columns.tolist(),
                        'data': dados_df.values.tolist()
                    }
                    
                    resultado['data']['dados_cache'] = json.dumps(cache_otimizado)
                    
            except Exception as cache_error:
                print(f"⚠️ Erro no cache: {cache_error}")
                # Continuar sem cache se houver erro
                resultado['data']['dados_cache'] = None
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ Erro na análise: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@long_short_bp.route('/api/long-short/pair-detail', methods=['POST'])
def analisar_par_detalhado():
    """Análise detalhada de um par específico"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        acao1 = data.get('acao1', '').upper()
        acao2 = data.get('acao2', '').upper()
        dados_cache = data.get('dados_cache')
        investimento = data.get('investimento', 10000)
        
        print(f"🔍 Analisando par: {acao1} x {acao2}")
        print(f"💰 Investimento: R$ {investimento}")
        print(f"📦 Cache recebido: {'Sim' if dados_cache else 'Não'}")
        
        if not acao1 or not acao2:
            return jsonify({
                'success': False,
                'error': 'Ação1 e Ação2 são obrigatórios'
            }), 400
        
        # ✅ MELHORAR TRATAMENTO DO CACHE
        dados = None
        
        if dados_cache:
            try:
                print("🔄 Tentando reconstruir dados do cache...")
                
                # Tentar deserializar o cache otimizado
                if isinstance(dados_cache, str):
                    cache_data = json.loads(dados_cache)
                else:
                    cache_data = dados_cache
                
                # Verificar se é o formato otimizado
                if isinstance(cache_data, dict) and 'index' in cache_data:
                    # Formato otimizado
                    dados = pd.DataFrame(
                        data=cache_data['data'],
                        index=pd.to_datetime(cache_data['index']),
                        columns=cache_data['columns']
                    )
                    print("✅ Cache otimizado reconstituído com sucesso")
                    
                else:
                    # Formato original (fallback)
                    dados = pd.read_json(cache_data, orient='split')
                    print("✅ Cache original reconstituído com sucesso")
                
                # ✅ RECONSTRUIR MULTIINDEX CORRETAMENTE
                if dados is not None and len(dados.columns) > 0:
                    # Verificar se precisa reconstruir MultiIndex
                    if not isinstance(dados.columns, pd.MultiIndex):
                        print("🔧 Reconstruindo MultiIndex...")
                        
                        # Criar tuplas para MultiIndex
                        tuples = []
                        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                            for ticker in service.top_50_acoes:
                                col_name = f"('{col}', '{ticker}')"
                                if col_name in dados.columns or f"{col}_{ticker}" in dados.columns:
                                    tuples.append((col, ticker))
                        
                        if tuples:
                            try:
                                columns = pd.MultiIndex.from_tuples(tuples)
                                
                                # Reordenar colunas para corresponder ao MultiIndex
                                dados_reordenados = pd.DataFrame(index=dados.index)
                                
                                for col, ticker in tuples:
                                    col_variations = [
                                        f"('{col}', '{ticker}')",
                                        f"{col}_{ticker}",
                                        f"('{col}', '{ticker}.SA')",
                                        ticker if col == 'Close' else None
                                    ]
                                    
                                    for variation in col_variations:
                                        if variation and variation in dados.columns:
                                            dados_reordenados[(col, ticker)] = dados[variation]
                                            break
                                
                                dados_reordenados.columns = pd.MultiIndex.from_tuples(
                                    [(col, ticker) for col, ticker in tuples if (col, ticker) in dados_reordenados.columns]
                                )
                                dados = dados_reordenados
                                print("✅ MultiIndex reconstruído com sucesso")
                                
                            except Exception as multi_error:
                                print(f"⚠️ Erro ao reconstruir MultiIndex: {multi_error}")
                
            except Exception as cache_error:
                print(f"❌ Erro ao processar cache: {cache_error}")
                dados = None
        
        # ✅ FALLBACK: OBTER DADOS NOVAMENTE SE CACHE FALHAR
        if dados is None:
            print("🔄 Cache inválido, obtendo dados novamente...")
            try:
                data_fim = datetime.now()
                data_inicio = data_fim - timedelta(days=240)
                dados = service.obter_dados([acao1, acao2], data_inicio, data_fim)
                print("✅ Dados obtidos diretamente")
            except Exception as fetch_error:
                print(f"❌ Erro ao obter dados: {fetch_error}")
                return jsonify({
                    'success': False,
                    'error': f'Erro ao obter dados das ações: {str(fetch_error)}'
                }), 500
        
        # Verificar se as ações existem nos dados
        if dados is None or dados.empty:
            return jsonify({
                'success': False,
                'error': 'Não foi possível obter dados das ações'
            }), 500
        
        # Verificar colunas disponíveis
        print(f"📊 Colunas disponíveis: {dados.columns.tolist()[:10]}...")
        
        # Verificar se as ações estão nos dados
        acoes_disponiveis = []
        if isinstance(dados.columns, pd.MultiIndex):
            acoes_disponiveis = dados['Close'].columns.tolist() if 'Close' in dados.columns.levels[0] else []
        else:
            acoes_disponiveis = [col for col in dados.columns if any(ticker in col for ticker in [acao1, acao2])]
        
        print(f"📈 Ações disponíveis: {acoes_disponiveis}")
        
        if isinstance(dados.columns, pd.MultiIndex):
            if 'Close' not in dados.columns.levels[0]:
                return jsonify({
                    'success': False,
                    'error': 'Dados de preços de fechamento não encontrados'
                }), 400
                
            if acao1 not in dados['Close'].columns or acao2 not in dados['Close'].columns:
                return jsonify({
                    'success': False,
                    'error': f'Ações {acao1} ou {acao2} não encontradas nos dados disponíveis: {dados["Close"].columns.tolist()}'
                }), 400
        else:
            # Tentar encontrar as colunas das ações
            acao1_found = any(acao1 in str(col) for col in dados.columns)
            acao2_found = any(acao2 in str(col) for col in dados.columns)
            
            if not acao1_found or not acao2_found:
                return jsonify({
                    'success': False,
                    'error': f'Ações {acao1} ou {acao2} não encontradas nos dados'
                }), 400
        
        # Executar análise detalhada
        print("🎯 Executando análise detalhada...")
        resultado = service.analisar_par_detalhado(dados, acao1, acao2, investimento)
        
        if resultado['success']:
            print("✅ Análise detalhada concluída com sucesso")
        else:
            print(f"❌ Erro na análise detalhada: {resultado.get('error')}")
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ Erro crítico na análise detalhada: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@long_short_bp.route('/api/long-short/margin-costs', methods=['POST'])
def calcular_margem_custos():
    """Calcular margem e custos operacionais"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        # Parâmetros obrigatórios
        valor_vendido = data.get('valor_vendido', 0)
        valor_comprado = data.get('valor_comprado', 0)
        
        # Parâmetros opcionais
        percentual_garantia = data.get('percentual_garantia', 25.0)
        taxa_btc_anual = data.get('taxa_btc_anual', 2.0)
        dias_operacao = data.get('dias_operacao', 10)
        taxa_corretora_btc = data.get('taxa_corretora_btc', 35.0)
        
        if valor_vendido <= 0 or valor_comprado <= 0:
            return jsonify({
                'success': False,
                'error': 'Valores vendido e comprado devem ser maiores que zero'
            }), 400
        
        # Cálculos
        garantia_venda = valor_vendido * (1 + percentual_garantia / 100)
        garantia_compra = valor_comprado * (1 + percentual_garantia / 100)
        margem_necessaria = abs(garantia_venda - garantia_compra)
        
        volume_total = valor_vendido + valor_comprado
        emolumentos = (volume_total / 10000) * 3.25
        
        taxa_btc_diaria = (taxa_btc_anual / 100) / 252
        custo_btc_periodo = valor_vendido * taxa_btc_diaria * dias_operacao
        taxa_corretora = custo_btc_periodo * (taxa_corretora_btc / 100)
        
        custo_total = margem_necessaria + emolumentos + custo_btc_periodo + taxa_corretora
        
        return jsonify({
            'success': True,
            'data': {
                'garantia_venda': garantia_venda,
                'garantia_compra': garantia_compra,
                'margem_necessaria': margem_necessaria,
                'emolumentos': emolumentos,
                'custo_btc_periodo': custo_btc_periodo,
                'taxa_corretora': taxa_corretora,
                'custo_total': custo_total,
                'parametros': {
                    'percentual_garantia': percentual_garantia,
                    'taxa_btc_anual': taxa_btc_anual,
                    'dias_operacao': dias_operacao,
                    'taxa_corretora_btc': taxa_corretora_btc
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro no cálculo de margem: {str(e)}'
        }), 500

@long_short_bp.route('/api/long-short/stability-analysis', methods=['POST'])
def analisar_estabilidade():
    """Análise de estabilidade de cointegração por períodos"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        acao1 = data.get('acao1', '').upper()
        acao2 = data.get('acao2', '').upper()
        dados_cache = data.get('dados_cache')
        
        print(f"🔍 Análise de estabilidade: {acao1} x {acao2}")
        print(f"📦 Cache recebido: {'Sim' if dados_cache else 'Não'}")
        
        if not acao1 or not acao2:
            return jsonify({
                'success': False,
                'error': 'Ação1 e Ação2 são obrigatórios'
            }), 400
        
        # ✅ USAR A MESMA LÓGICA DE RECONSTRUÇÃO DO CACHE DA FUNÇÃO ANTERIOR
        dados = None
        
        if dados_cache:
            try:
                print("🔄 Reconstruindo dados do cache para análise de estabilidade...")
                
                # Tentar deserializar o cache otimizado
                if isinstance(dados_cache, str):
                    cache_data = json.loads(dados_cache)
                else:
                    cache_data = dados_cache
                
                # Verificar se é o formato otimizado
                if isinstance(cache_data, dict) and 'index' in cache_data:
                    # Formato otimizado
                    dados = pd.DataFrame(
                        data=cache_data['data'],
                        index=pd.to_datetime(cache_data['index']),
                        columns=cache_data['columns']
                    )
                    print("✅ Cache otimizado reconstituído")
                    
                else:
                    # Formato original (fallback)
                    dados = pd.read_json(cache_data, orient='split')
                    print("✅ Cache original reconstituído")
                
                # ✅ RECONSTRUIR MULTIINDEX CORRETAMENTE (MESMA LÓGICA)
                if dados is not None and len(dados.columns) > 0:
                    # Verificar se precisa reconstruir MultiIndex
                    if not isinstance(dados.columns, pd.MultiIndex):
                        print("🔧 Reconstruindo MultiIndex para estabilidade...")
                        
                        # Criar tuplas para MultiIndex
                        tuples = []
                        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                            for ticker in service.top_50_acoes:
                                col_name = f"('{col}', '{ticker}')"
                                if col_name in dados.columns or f"{col}_{ticker}" in dados.columns:
                                    tuples.append((col, ticker))
                        
                        if tuples:
                            try:
                                columns = pd.MultiIndex.from_tuples(tuples)
                                
                                # Reordenar colunas para corresponder ao MultiIndex
                                dados_reordenados = pd.DataFrame(index=dados.index)
                                
                                for col, ticker in tuples:
                                    col_variations = [
                                        f"('{col}', '{ticker}')",
                                        f"{col}_{ticker}",
                                        f"('{col}', '{ticker}.SA')",
                                        ticker if col == 'Close' else None
                                    ]
                                    
                                    for variation in col_variations:
                                        if variation and variation in dados.columns:
                                            dados_reordenados[(col, ticker)] = dados[variation]
                                            break
                                
                                dados_reordenados.columns = pd.MultiIndex.from_tuples(
                                    [(col, ticker) for col, ticker in tuples if (col, ticker) in dados_reordenados.columns]
                                )
                                dados = dados_reordenados
                                print("✅ MultiIndex reconstruído para estabilidade")
                                
                            except Exception as multi_error:
                                print(f"⚠️ Erro ao reconstruir MultiIndex: {multi_error}")
                
            except Exception as cache_error:
                print(f"❌ Erro ao processar cache: {cache_error}")
                dados = None
        
        # ✅ FALLBACK: OBTER DADOS NOVAMENTE SE CACHE FALHAR
        if dados is None:
            print("🔄 Cache inválido, obtendo dados novamente para estabilidade...")
            try:
                data_fim = datetime.now()
                data_inicio = data_fim - timedelta(days=240)
                dados = service.obter_dados([acao1, acao2], data_inicio, data_fim)
                print("✅ Dados obtidos diretamente para estabilidade")
            except Exception as fetch_error:
                print(f"❌ Erro ao obter dados: {fetch_error}")
                return jsonify({
                    'success': False,
                    'error': f'Erro ao obter dados das ações: {str(fetch_error)}'
                }), 500
        
        # Verificar se as ações existem nos dados
        if dados is None or dados.empty:
            return jsonify({
                'success': False,
                'error': 'Não foi possível obter dados das ações'
            }), 500
        
        # ✅ VERIFICAR ESTRUTURA DOS DADOS
        print(f"📊 Estrutura dos dados: {type(dados.columns)}")
        print(f"📈 Shape dos dados: {dados.shape}")
        
        # Verificar se as ações estão disponíveis
        if isinstance(dados.columns, pd.MultiIndex):
            if 'Close' not in dados.columns.levels[0]:
                return jsonify({
                    'success': False,
                    'error': 'Dados de preços de fechamento não encontrados'
                }), 400
                
            acoes_disponiveis = dados['Close'].columns.tolist()
            if acao1 not in acoes_disponiveis or acao2 not in acoes_disponiveis:
                return jsonify({
                    'success': False,
                    'error': f'Ações {acao1} ou {acao2} não encontradas. Disponíveis: {acoes_disponiveis}'
                }), 400
        else:
            return jsonify({
                'success': False,
                'error': f'Estrutura de dados inválida. Esperado MultiIndex, recebido: {type(dados.columns)}'
            }), 400
        
        # ✅ ANÁLISE DE ESTABILIDADE POR PERÍODOS COM MELHOR TRATAMENTO DE ERROS
        periodos = [60, 90, 120, 140, 180, 200, 240]
        resultados = []
        
        print("📊 Iniciando análise de estabilidade por períodos...")
        
        for periodo in periodos:
            try:
                print(f"🔍 Analisando período de {periodo} dias...")
                
                # Verificar se temos dados suficientes
                if len(dados) < periodo:
                    print(f"⚠️ Dados insuficientes para período de {periodo} dias")
                    resultados.append({
                        'periodo': periodo,
                        'pvalor_cointegração': None,
                        'meia_vida': None,
                        'r_squared': None,
                        'status': 'Dados Insuficientes'
                    })
                    continue
                
                dados_recentes = dados.tail(periodo)
                
                # Verificar se as ações têm dados válidos no período
                serie1 = dados_recentes['Close'][acao1].dropna()
                serie2 = dados_recentes['Close'][acao2].dropna()
                
                if len(serie1) < 30 or len(serie2) < 30:
                    print(f"⚠️ Dados insuficientes para {acao1} ou {acao2} no período de {periodo} dias")
                    resultados.append({
                        'periodo': periodo,
                        'pvalor_cointegração': None,
                        'meia_vida': None,
                        'r_squared': None,
                        'status': 'Dados Insuficientes'
                    })
                    continue
                
                # Teste de cointegração
                from statsmodels.tsa.stattools import coint
                from statsmodels.regression.linear_model import OLS
                
                try:
                    _, pvalor, _ = coint(serie1, serie2)
                    print(f"✅ Cointegração calculada para {periodo} dias: p-valor = {pvalor:.4f}")
                except Exception as coint_error:
                    print(f"❌ Erro no teste de cointegração para {periodo} dias: {coint_error}")
                    resultados.append({
                        'periodo': periodo,
                        'pvalor_cointegração': None,
                        'meia_vida': None,
                        'r_squared': None,
                        'status': 'Erro Cointegração'
                    })
                    continue
                
                # Calcular spread e meia-vida
                try:
                    modelo = OLS(serie1, serie2).fit()
                    spread = serie1 - modelo.params[0] * serie2
                    meia_vida = service.calcular_meia_vida(spread) if len(spread.dropna()) > 1 else None
                    print(f"✅ Meia-vida calculada para {periodo} dias: {meia_vida}")
                except Exception as spread_error:
                    print(f"❌ Erro no cálculo do spread para {periodo} dias: {spread_error}")
                    meia_vida = None
                    modelo = None
                
                # Preparar resultado
                status = 'Cointegrado' if pvalor < 0.05 else 'Não Cointegrado'
                
                resultado_periodo = {
                    'periodo': periodo,
                    'pvalor_cointegração': round(pvalor, 4) if pvalor is not None else None,
                    'meia_vida': round(meia_vida, 2) if meia_vida is not None else None,
                    'r_squared': round(modelo.rsquared, 4) if modelo is not None else None,
                    'status': status
                }
                
                resultados.append(resultado_periodo)
                print(f"✅ Período {periodo} concluído: {status}")
                
            except Exception as e:
                print(f"❌ Erro geral no período {periodo}: {str(e)}")
                resultados.append({
                    'periodo': periodo,
                    'pvalor_cointegração': None,
                    'meia_vida': None,
                    'r_squared': None,
                    'status': 'Erro'
                })
        
        # ✅ DIAGNÓSTICO GERAL MELHORADO
        periodos_validos = [r for r in resultados if r['status'] not in ['Erro', 'Dados Insuficientes', 'Erro Cointegração']]
        periodos_cointegrados = sum(1 for r in periodos_validos if r['status'] == 'Cointegrado')
        total_periodos = len(periodos_validos)
        
        if total_periodos == 0:
            diagnostico = "Não foi possível analisar nenhum período"
            status_icon = "❌"
            r2_medio = 0
        else:
            r2_values = [r['r_squared'] for r in resultados if r['r_squared'] is not None]
            r2_medio = sum(r2_values) / len(r2_values) if r2_values else 0
            
            if periodos_cointegrados == total_periodos:
                diagnostico = "Cointegração estável em todos os períodos"
                status_icon = "✅"
            elif periodos_cointegrados >= total_periodos * 0.7:
                diagnostico = "Cointegração presente na maioria dos períodos"
                status_icon = "⚠️"
            else:
                diagnostico = "Cointegração instável ou ausente"
                status_icon = "❌"
        
        print(f"🎯 Diagnóstico final: {diagnostico}")
        print(f"📊 Períodos cointegrados: {periodos_cointegrados}/{total_periodos}")
        
        return jsonify({
            'success': True,
            'data': {
                'analise_periodos': resultados,
                'diagnostico': {
                    'status_icon': status_icon,
                    'texto': diagnostico,
                    'periodos_cointegrados': periodos_cointegrados,
                    'total_periodos': total_periodos,
                    'r2_medio': round(r2_medio, 4)
                }
            }
        })
        
    except Exception as e:
        print(f"❌ Erro crítico na análise de estabilidade: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': f'Erro na análise de estabilidade: {str(e)}'
        }), 500

@long_short_bp.route('/api/long-short/setores', methods=['GET'])
def obter_setores():
    """Obter mapeamento de setores das ações"""
    try:
        return jsonify({
            'success': True,
            'data': {
                'setores': service.setores,
                'acoes_disponiveis': service.top_50_acoes
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao obter setores: {str(e)}'
        }), 500

@long_short_bp.route('/api/long-short/status', methods=['GET'])
def status_servico():
    """Status do serviço Long & Short"""
    return jsonify({
        'success': True,
        'data': {
            'status': 'online',
            'total_acoes': len(service.top_50_acoes),
            'setores_unicos': len(set(service.setores.values())),
            'version': '1.0.0'
        }
    })