from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from premium.beta_regression_service import BetaRegressionService
import traceback
import pandas as pd
import numpy as np

def convert_to_serializable(obj):
    """Converte tipos numpy/pandas para tipos Python nativos serializáveis em JSON"""
    if isinstance(obj, (np.integer, pd.Int64Dtype)):
        return int(obj)
    elif isinstance(obj, (np.floating, pd.Float64Dtype)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    elif pd.isna(obj):
        return None
    else:
        return obj

# Criar blueprint
beta_regression_bp = Blueprint('beta_regression', __name__)

# Lista de ativos padrão (ações brasileiras mais negociadas)
DEFAULT_TICKERS = [
    "ABEV3", "ASAI3", "B3SA3", "BBDC4", "BBAS3", "BBSE3", "BPAC11", "MBRF",
    "BRKM5", "CMIG4", "CPLE6", "CRFB3", "CSAN3", "CSNA3", "CYRE3", "EGIE3",
    "EMBJ3", "ENGI11", "EQTL3", "GFSA3", "GGBR4", "GOAU4", "GUAR3", "HAPV3",
    "ITUB4", "JBSS3", "LREN3", "MGLU3", "MOVI3", "MRFG3", "MRVE3", "NTCO3",
    "PETR4", "PETZ3", "POMO4", "PRIO3", "RAIL3", "RDOR3", "RENT3", "RRRP3",
    "SANB11", "SBSP3", "SMTO3", "SUZB3", "TIMS3", "TOTS3", "UGPA3", "UNIP3",
    "USIM3", "USIM5", "VALE3", "VBBR3", "VIVA3", "VIVT3", "VULC3", "WEGE3",
    "WIZC3"
]

@beta_regression_bp.route('/')
def index():
    """Página principal do Beta Regressivo"""
    try:
        return render_template('beta_regression.html', 
                             default_tickers=DEFAULT_TICKERS,
                             page_title="Beta Regressivo - Geminii")
    except Exception as e:
        print(f"Erro na rota index: {e}")
        flash(f"Erro ao carregar página: {str(e)}", "error")
        return render_template('error.html', error="Erro interno do servidor")

@beta_regression_bp.route('/analyze', methods=['POST'])
def analyze():
    """Endpoint para análise individual de uma ação - COMPATÍVEL COM O HTML"""
    try:
        print("=== NOVA REQUISIÇÃO BETA REGRESSION ===")
        
        # Obter dados do JSON (como esperado pelo HTML)
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400

        symbol = data.get('symbol', '').strip().upper()
        anos = data.get('anos', 2)

        print(f"Parâmetros recebidos - Symbol: {symbol}, Anos: {anos}")

        # Validações
        if not symbol:
            return jsonify({
                'success': False,
                'error': 'Código da ação é obrigatório'
            }), 400

        try:
            anos = int(anos)
            if anos < 1 or anos > 10:
                return jsonify({
                    'success': False,
                    'error': 'Número de anos deve estar entre 1 e 10'
                }), 400
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Número de anos deve ser um valor numérico válido'
            }), 400

        print(f"=== INICIANDO ANÁLISE BETA REGRESSÃO ===")
        print(f"Símbolo: {symbol}, Anos: {anos}")
        
        # Executar análise - APENAS DIÁRIO (sem timeframe)
        service = BetaRegressionService()
        result = service.run_analysis(symbol, anos)
        
        if result['success']:
            print("Análise Beta Regression concluída com sucesso!")
            
            # Preparar dados para Chart.js - FORMATO CORRETO PARA O HTML
            df = result.get('dataframe')
            chart_data = None
            
            if df is not None:
                try:
                    # Preparar dados completos para os gráficos Chart.js
                    # IMPORTANTE: Converter todos os valores para tipos Python nativos
                    chart_data = {
                        # Labels formatados para display
                        'labels': df.index.strftime('%d/%m/%Y').tolist(),
                        
                        # Dados de preço e média móvel (convertidos para float)
                        'prices': [float(x) if pd.notna(x) else 0.0 for x in df['close'].round(2)],
                        'mm': [float(x) if pd.notna(x) else 0.0 for x in df['MM'].round(2)] if 'MM' in df.columns else [],
                        
                        # Beta0 normalizado (convertido para float)
                        'beta0_norm': [float(x) if pd.notna(x) else 0.0 for x in df['Beta0_Norm'].round(4)] if 'Beta0_Norm' in df.columns else [],
                        
                        # Sinais de trading (convertidos para int)
                        'trading_signals': [int(x) if pd.notna(x) else 0 for x in df['trading']] if 'trading' in df.columns else [],
                        
                        # Retornos acumulados (em porcentagem, convertidos para float)
                        'acc_returns': [float(x) if pd.notna(x) else 0.0 for x in (df['Acc_Returns'] * 100).round(2)] if 'Acc_Returns' in df.columns else [],
                        'acc_returns_after_fees': [float(x) if pd.notna(x) else 0.0 for x in (df['Acc_Returns_After_Fees'] * 100).round(2)] if 'Acc_Returns_After_Fees' in df.columns else [],
                        
                        # Retornos por operação (em porcentagem, convertidos para float)
                        'trading_after_fees': [float(x) if pd.notna(x) else 0.0 for x in (df['Trading_After_Fees'] * 100).round(2)] if 'Trading_After_Fees' in df.columns else []
                    }
                    print(f"Dados do gráfico Chart.js preparados: {len(chart_data['labels'])} pontos")
                except Exception as e:
                    print(f"Erro ao preparar dados do gráfico Chart.js: {e}")
                    import traceback
                    traceback.print_exc()
                    chart_data = None
            
            # Retornar resultado EXATAMENTE como esperado pelo HTML
            return jsonify({
                'success': True,
                'chart_html': result['chart_html'],        # Gráfico Plotly (backup)
                'chart_data': chart_data,                  # Dados para Chart.js (principal)
                'analysis_data': convert_to_serializable(result['analysis_data']),  # Dados da análise (convertidos)
                'trades_history': convert_to_serializable(result['trades_history']) # Histórico de trades (convertido)
            })
        else:
            print(f"Erro na análise: {result['error']}")
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
    except Exception as e:
        print(f"Erro na análise: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@beta_regression_bp.route('/bulk_analyze', methods=['POST'])
def bulk_analyze():
    """Endpoint para análise em lote de múltiplas ações"""
    try:
        # Obter dados do formulário
        data = request.get_json() if request.is_json else request.form
        
        symbols = data.get('symbols', [])
        anos = int(data.get('anos', 2))
        
        # Se symbols for string, converter para lista
        if isinstance(symbols, str):
            symbols = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        
        # Validações
        if not symbols:
            symbols = DEFAULT_TICKERS  # Usar lista padrão se não especificado
        
        if len(symbols) > 50:  # Limitar para evitar sobrecarga
            return jsonify({
                'success': False,
                'error': 'Máximo de 50 ações por análise'
            })
        
        print(f"=== ANÁLISE EM LOTE ===")
        print(f"Símbolos: {len(symbols)} ações, Anos: {anos}")
        
        # Executar análise para cada símbolo
        service = BetaRegressionService()
        results = []
        errors = []
        
        for i, symbol in enumerate(symbols):
            try:
                print(f"Analisando {symbol} ({i+1}/{len(symbols)})")
                result = service.run_analysis(symbol, anos)  # SEM timeframe
                
                if result['success']:
                    # Adicionar apenas dados resumidos para a tabela
                    analysis_data = result['analysis_data']
                    analysis_data['symbol'] = symbol  # Garantir que o símbolo está correto
                    results.append(analysis_data)
                else:
                    errors.append(f"{symbol}: {result['error']}")
                    
            except Exception as e:
                errors.append(f"{symbol}: {str(e)}")
                print(f"Erro ao analisar {symbol}: {e}")
        
        print(f"=== ANÁLISE EM LOTE CONCLUÍDA ===")
        print(f"Sucessos: {len(results)}, Erros: {len(errors)}")
        
        return jsonify({
            'success': True,
            'results': results,
            'errors': errors,
            'total_analyzed': len(results),
            'total_errors': len(errors)
        })
        
    except Exception as e:
        print(f"Erro na análise em lote: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        })

@beta_regression_bp.route('/get_analysis/<symbol>')
def get_analysis(symbol):
    """Endpoint para obter análise específica de uma ação (GET)"""
    try:
        anos = int(request.args.get('anos', 2))
        
        print(f"GET Analysis - Símbolo: {symbol}, Anos: {anos}")
        
        service = BetaRegressionService()
        result = service.run_analysis(symbol, anos)  # SEM timeframe
        
        if not result['success']:
            return jsonify(result)
        
        # Preparar dados para Chart.js
        df = result.get('dataframe')
        chart_data = None
        
        if df is not None:
            try:
                # Converter valores para tipos Python nativos (evitar int64/float64)
                chart_data = {
                    'labels': df.index.strftime('%d/%m/%Y').tolist(),
                    'prices': [float(x) if pd.notna(x) else 0.0 for x in df['close'].round(2)],
                    'beta0_norm': [float(x) if pd.notna(x) else 0.0 for x in df['Beta0_Norm'].round(4)],
                    'trading_signals': [int(x) if pd.notna(x) else 0 for x in df['trading']],
                    'acc_returns': [float(x) if pd.notna(x) else 0.0 for x in (df['Acc_Returns'] * 100).round(2)],
                    'acc_returns_after_fees': [float(x) if pd.notna(x) else 0.0 for x in (df['Acc_Returns_After_Fees'] * 100).round(2)],
                    'mm': [float(x) if pd.notna(x) else 0.0 for x in df['MM'].round(2)]
                }
            except Exception as e:
                print(f"Erro ao preparar dados Chart.js: {e}")
                chart_data = None
        
        return jsonify({
            'success': True,
            'chart_html': result['chart_html'],
            'chart_data': chart_data,
            'analysis_data': convert_to_serializable(result['analysis_data']),
            'trades_history': convert_to_serializable(result['trades_history'])
        })
        
    except Exception as e:
        print(f"Erro ao obter análise: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        })

@beta_regression_bp.route('/health')
def health():
    """Endpoint de verificação de saúde"""
    try:
        # Teste rápido com uma ação conhecida
        service = BetaRegressionService()
        test_result = service.get_yfinance_data('PETR4', 1)  # SEM timeframe
        
        if test_result is not None and len(test_result) > 0:
            status = "OK"
            message = f"Serviço funcionando. Teste com PETR4: {len(test_result)} registros"
        else:
            status = "WARNING"
            message = "Serviço funcionando mas com possíveis problemas de dados"
        
        return jsonify({
            'status': status,
            'message': message,
            'service': 'Beta Regression',
            'version': '1.0.0'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'ERROR',
            'message': f'Erro no serviço: {str(e)}',
            'service': 'Beta Regression',
            'version': '1.0.0'
        })

# Filtros customizados para templates
@beta_regression_bp.app_template_filter('format_percentage')
def format_percentage(value):
    """Formatar como porcentagem"""
    try:
        return f"{float(value):.2f}%"
    except:
        return "0.00%"

@beta_regression_bp.app_template_filter('format_currency')
def format_currency(value):
    """Formatar como moeda brasileira"""
    try:
        return f"R$ {float(value):.2f}"
    except:
        return "R$ 0.00"

@beta_regression_bp.app_template_filter('format_signal')
def format_signal(value):
    """Formatar sinal de trading"""
    signal_map = {
        'COMPRA': '🟢 COMPRA',
        'VENDA': ' VENDA', 
        'NEUTRO': '⚪ NEUTRO'
    }
    return signal_map.get(value, value)

@beta_regression_bp.app_template_filter('format_proximity_status')
def format_proximity_status(value):
    """Formatar status de proximidade"""
    status_map = {
        'NOVA COMPRA': ' NOVA COMPRA',
        'PREPARANDO COMPRA': '🟡 PREPARANDO COMPRA',
        'IMINENTE VENDA': ' IMINENTE VENDA',
        'PREPARANDO VENDA': '🟠 PREPARANDO VENDA',
        'NEUTRO': '⚪ NEUTRO'
    }
    return status_map.get(value, value)