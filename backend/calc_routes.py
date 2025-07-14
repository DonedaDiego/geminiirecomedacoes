# calc_routes.py - Blueprint para rotas de cálculo de opções

from flask import Blueprint, request, jsonify
from calc_service import OptionsCalculatorService
import os
import numpy as np

calc_bp = Blueprint('calc', __name__, url_prefix='/calc')

# Inicializar serviço com token da API
API_TOKEN = os.getenv('OPLAB_TOKEN')
calc_service = OptionsCalculatorService(API_TOKEN)

@calc_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "service": "options_calculator"})

@calc_bp.route('/analyze', methods=['POST'])
def analyze_option():
    try:
        data = request.get_json()
        
        # Validar dados obrigatórios
        required_fields = ['ticker', 'option_code', 'operation', 'option_type']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "error": f"Campo obrigatório '{field}' não encontrado",
                    "success": False
                }), 400
        
        ticker = data['ticker'].upper()
        option_code = data['option_code'].upper()
        operation = data['operation'].upper()
        option_type = data['option_type'].upper()
        
        # Validar valores
        if operation not in ['COMPRA', 'VENDA']:
            return jsonify({
                "error": "Operação deve ser 'COMPRA' ou 'VENDA'",
                "success": False
            }), 400
        
        if option_type not in ['CALL', 'PUT']:
            return jsonify({
                "error": "Tipo de opção deve ser 'CALL' ou 'PUT'",
                "success": False
            }), 400
        
        # Processar análise
        result = calc_service.analyze_option_trade(
            ticker=ticker,
            option_code=option_code,
            operation=operation,
            option_type=option_type
        )
        
        if not result.get('success', False):
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "success": False
        }), 500

@calc_bp.route('/stock-bands/<ticker>', methods=['GET'])
def get_stock_bands(ticker):
    try:
        # Buscar dados da ação
        stock_data = calc_service.get_stock_data(ticker)
        if stock_data is None:
            return jsonify({
                "error": "Erro ao buscar dados da ação",
                "success": False
            }), 400
        
        # Processar modelo
        stock_data = calc_service.calculate_base_volatility(stock_data)
        stock_data = calc_service.engineer_features(stock_data)
        stock_data = calc_service.train_xgboost(stock_data)
        stock_data = calc_service.create_hybrid_model(stock_data)
        stock_data = calc_service.create_bands(stock_data)
        
        # Dados atuais
        current_stock = calc_service.get_current_stock_info(ticker)
        if not current_stock:
            return jsonify({
                "error": "Erro ao buscar dados atuais",
                "success": False
            }), 400
        
        latest = stock_data.iloc[-1]
        
        return jsonify({
            "ticker": ticker.upper(),
            "current_price": current_stock['close'],
            "volatility": {
                "garch": float(latest['garch_vol']),
                "xgb": float(latest['xgb_vol']),
                "hybrid": float(latest['hybrid_vol'])
            },
            "bands": {
                "superior_2sigma": float(latest['banda_superior_2sigma']),
                "inferior_2sigma": float(latest['banda_inferior_2sigma']),
                "superior_4sigma": float(latest['banda_superior_4sigma']),
                "inferior_4sigma": float(latest['banda_inferior_4sigma']),
                "linha_central": float(latest['linha_central'])
            },
            "regime": {
                "volatility": "High" if latest['vol_regime'] == 1 else "Low",
                "trend": "Bull" if latest['trend_regime'] == 1 else "Bear"
            },
            "success": True
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "success": False
        }), 500

@calc_bp.route('/option-info/<ticker>/<option_code>', methods=['GET'])
def get_option_info(ticker, option_code):
    try:
        # Dados atuais da opção
        current_option = calc_service.get_current_option_info(ticker, option_code)
        if not current_option:
            return jsonify({
                "error": "Opção não encontrada",
                "success": False
            }), 404
        
        # Histórico da opção
        option_history = calc_service.get_option_history(ticker, option_code)
        
        return jsonify({
            "ticker": ticker.upper(),
            "option_code": option_code.upper(),
            "current_data": {
                "strike": float(current_option['strike']),
                "premium": float(current_option['premium']),
                "type": current_option['type'],
                "due_date": current_option['due_date'],
                "days_to_maturity": int(current_option['days_to_maturity']),
                "moneyness": current_option['moneyness'],
                "iv": float(current_option['volatility'])
            },
            "greeks": {
                "delta": float(current_option['delta']),
                "gamma": float(current_option['gamma']),
                "theta": float(current_option['theta']),
                "vega": float(current_option['vega']),
                "rho": float(current_option['rho'])
            },
            "probability": {
                "poe": float(current_option['poe']),
                "bs_theoretical": float(current_option['bs'])
            },
            "history_summary": {
                "points": len(option_history),
                "avg_premium": float(np.mean([h['premium'] for h in option_history])) if option_history else 0.0,
                "avg_iv": float(np.mean([h['volatility'] for h in option_history])) if option_history else 0.0
            },
            "success": True
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "success": False
        }), 500

@calc_bp.route('/quick-calc', methods=['POST'])
def quick_calculation():
    try:
        data = request.get_json()
        
        required_fields = ['current_price', 'strike', 'premium', 'operation', 'option_type']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "error": f"Campo '{field}' obrigatório",
                    "success": False
                }), 400
        
        # Usar bandas padrão se não fornecidas
        current_price = float(data['current_price'])
        vol_estimate = float(data.get('volatility', 0.25))  # 25% se não fornecido
        
        banda_sup_2sigma = current_price * (1 + 2 * vol_estimate)
        banda_inf_2sigma = current_price * (1 - 2 * vol_estimate)
        banda_sup_4sigma = current_price * (1 + 4 * vol_estimate)
        banda_inf_4sigma = current_price * (1 - 4 * vol_estimate)
        
        targets = calc_service.calculate_option_targets(
            current_price=current_price,
            strike=float(data['strike']),
            banda_sup_2sigma=banda_sup_2sigma,
            banda_inf_2sigma=banda_inf_2sigma,
            banda_sup_4sigma=banda_sup_4sigma,
            banda_inf_4sigma=banda_inf_4sigma,
            operation=data['operation'].upper(),
            option_type=data['option_type'].upper(),
            premium=float(data['premium'])
        )
        
        return jsonify({
            "inputs": {
                "current_price": current_price,
                "strike": float(data['strike']),
                "premium": float(data['premium']),
                "operation": data['operation'].upper(),
                "option_type": data['option_type'].upper()
            },
            "estimated_bands": {
                "superior_2sigma": banda_sup_2sigma,
                "inferior_2sigma": banda_inf_2sigma,
                "superior_4sigma": banda_sup_4sigma,
                "inferior_4sigma": banda_inf_4sigma
            },
            "targets_and_stops": targets,
            "success": True
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "success": False
        }), 500

@calc_bp.route('/list-options/<ticker>', methods=['GET'])
def list_options(ticker):
    try:
        # Buscar todas as opções de um ticker
        url = f"{calc_service.base_url}/options/{ticker.upper()}"
        params = {"limit": 100}
        
        import requests
        response = requests.get(url, headers=calc_service.headers, params=params)
        response.raise_for_status()
        
        options_data = response.json()
        
        # Filtrar e organizar dados
        options_summary = []
        for option in options_data:
            options_summary.append({
                "symbol": option['symbol'],
                "type": option['type'],
                "strike": float(option['strike']),
                "premium": float(option['premium']),
                "days_to_maturity": int(option['days_to_maturity']),
                "moneyness": option['moneyness'],
                "iv": float(option['volatility']),
                "delta": float(option['delta']),
                "theta": float(option['theta']),
                "poe": float(option['poe'])
            })
        
        return jsonify({
            "ticker": ticker.upper(),
            "total_options": len(options_summary),
            "options": options_summary,
            "success": True
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "success": False
        }), 500

@calc_bp.route('/batch-analyze', methods=['POST'])
def batch_analyze():
    try:
        data = request.get_json()
        
        if 'options' not in data:
            return jsonify({
                "error": "Campo 'options' obrigatório",
                "success": False
            }), 400
        
        results = []
        errors = []
        
        for option_data in data['options']:
            try:
                result = calc_service.analyze_option_trade(
                    ticker=option_data['ticker'].upper(),
                    option_code=option_data['option_code'].upper(),
                    operation=option_data['operation'].upper(),
                    option_type=option_data['option_type'].upper()
                )
                
                if result.get('success', False):
                    results.append(result)
                else:
                    errors.append({
                        "option": option_data,
                        "error": result.get('error', 'Erro desconhecido')
                    })
                    
            except Exception as e:
                errors.append({
                    "option": option_data,
                    "error": str(e)
                })
        
        return jsonify({
            "total_requested": len(data['options']),
            "successful_analyses": len(results),
            "failed_analyses": len(errors),
            "results": results,
            "errors": errors,
            "success": True
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "success": False
        }), 500

@calc_bp.route('/market-overview', methods=['GET'])
def market_overview():
    try:
        # Buscar algumas ações principais
        tickers = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
        overview = []
        
        for ticker in tickers:
            try:
                current_stock = calc_service.get_current_stock_info(ticker)
                if current_stock:
                    overview.append({
                        "ticker": ticker,
                        "price": float(current_stock['close']),
                        "variation": float(current_stock.get('variation', 0)),
                        "volume": int(current_stock.get('volume', 0)),
                        "has_options": bool(current_stock.get('has_options', False))
                    })
            except:
                continue
        
        return jsonify({
            "market_time": "Current",
            "stocks_overview": overview,
            "total_stocks": len(overview),
            "success": True
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "success": False
        }), 500