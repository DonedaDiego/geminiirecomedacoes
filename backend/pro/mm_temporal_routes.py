"""
mm_temporal_routes.py - Rotas para análise temporal de Market Makers
"""

from flask import Blueprint, jsonify, request
from .mm_temporal_service import mm_temporal_service
from .gamma_service import GammaService
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Blueprint
mm_temporal_bp = Blueprint('mm_temporal', __name__)

# Instanciar serviços
gamma_service = GammaService()

@mm_temporal_bp.route('/api/mm-temporal/<ticker>', methods=['GET'])
def get_mm_temporal_analysis(ticker):
    """
    Análise temporal completa de Market Makers
    
    Query params:
    - days_back: número de dias para análise (default: 5)
    - expiration: código do vencimento (opcional)
    """
    try:
        # Parâmetros
        days_back = int(request.args.get('days_back', 5))
        expiration_code = request.args.get('expiration')
        
        # Validações
        if not ticker or len(ticker) < 3:
            return jsonify({
                'error': 'Ticker inválido',
                'success': False
            }), 400
        
        if days_back < 3 or days_back > 10:
            return jsonify({
                'error': 'days_back deve ser entre 3 e 10',
                'success': False
            }), 400
        
        logging.info(f"Iniciando análise temporal MM para {ticker} ({days_back} dias)")
        
        # 1. OBTER DADOS ATUAIS DO GEX (para ter current_oi_breakdown)
        try:
            gamma_result = gamma_service.analyze_gamma_complete(ticker, expiration_code)
            
            if not gamma_result.get('success'):
                return jsonify({
                    'error': 'Erro ao obter dados atuais de OI descoberto',
                    'success': False
                }), 500
            
            # Precisamos extrair o current_oi_breakdown do gamma service
            # Isso requer uma pequena modificação no gamma service ou usar os dados diretamente
            
        except Exception as e:
            logging.error(f"Erro ao buscar dados gamma para temporal: {e}")
            return jsonify({
                'error': 'Erro ao obter dados base para análise temporal',
                'success': False
            }), 500
        
        # 2. OBTER SPOT PRICE
        try:
            # Usar o mesmo data provider do gamma service
            spot_price = gamma_service.analyzer.data_provider.get_spot_price(ticker)
            if not spot_price:
                return jsonify({
                    'error': 'Não foi possível obter cotação atual',
                    'success': False
                }), 500
                
        except Exception as e:
            logging.error(f"Erro ao obter spot price: {e}")
            return jsonify({
                'error': 'Erro ao obter cotação',
                'success': False
            }), 500
        
        # 3. OBTER CURRENT_OI_BREAKDOWN
        try:
            # Buscar dados atuais de OI
            oi_breakdown, expiration_info = gamma_service.analyzer.data_provider.get_floqui_oi_breakdown(
                ticker, expiration_code
            )
            
            if not oi_breakdown:
                return jsonify({
                    'error': 'Não foi possível obter dados de Open Interest atual',
                    'success': False
                }), 500
                
        except Exception as e:
            logging.error(f"Erro ao obter OI breakdown: {e}")
            return jsonify({
                'error': 'Erro ao buscar dados de Open Interest',
                'success': False
            }), 500
        
        # 4. EXECUTAR ANÁLISE TEMPORAL
        try:
            temporal_result = mm_temporal_service.analyze_mm_temporal_complete(
                ticker=ticker,
                spot_price=spot_price,
                current_oi_breakdown=oi_breakdown,
                days_back=days_back
            )
            
            if not temporal_result.get('success'):
                return jsonify({
                    'error': temporal_result.get('error', 'Erro na análise temporal'),
                    'success': False
                }), 500
            
            # 5. ENRIQUECER COM DADOS ADICIONAIS
            enriched_result = {
                **temporal_result,
                'market_context': {
                    'spot_price': spot_price,
                    'expiration_used': expiration_info.get('desc') if expiration_info else None,
                    'total_oi_strikes': len(oi_breakdown)
                }
            }
            
            logging.info(f"Análise temporal MM concluída para {ticker}")
            return jsonify(enriched_result)
            
        except Exception as e:
            logging.error(f"Erro na análise temporal: {e}")
            return jsonify({
                'error': f'Erro na análise temporal: {str(e)}',
                'success': False
            }), 500
    
    except Exception as e:
        logging.error(f"Erro geral na rota temporal: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@mm_temporal_bp.route('/api/mm-temporal/<ticker>/summary', methods=['GET'])
def get_mm_temporal_summary(ticker):
    """
    Resumo executivo da análise temporal (resposta mais rápida)
    """
    try:
        # Usar apenas 3 dias para resposta mais rápida
        days_back = int(request.args.get('days_back', 3))
        expiration_code = request.args.get('expiration')
        
        logging.info(f"Buscando resumo temporal MM para {ticker}")
        
        # Obter dados necessários
        spot_price = gamma_service.analyzer.data_provider.get_spot_price(ticker)
        if not spot_price:
            return jsonify({'error': 'Erro ao obter cotação', 'success': False}), 500
        
        oi_breakdown, expiration_info = gamma_service.analyzer.data_provider.get_floqui_oi_breakdown(
            ticker, expiration_code
        )
        
        if not oi_breakdown:
            return jsonify({'error': 'Erro ao obter dados OI', 'success': False}), 500
        
        # Análise temporal
        temporal_result = mm_temporal_service.analyze_mm_temporal_complete(
            ticker=ticker,
            spot_price=spot_price,
            current_oi_breakdown=oi_breakdown,
            days_back=days_back
        )
        
        if not temporal_result.get('success'):
            return jsonify({'error': 'Erro na análise', 'success': False}), 500
        
        # Retornar apenas o essencial
        summary_result = {
            'ticker': temporal_result['ticker'],
            'success': True,
            'summary': temporal_result['summary'],
            'top_insights': temporal_result['insights'][:3],  # Apenas top 3 insights
            'analysis_date': temporal_result['analysis_metadata']['analysis_date']
        }
        
        return jsonify(summary_result)
        
    except Exception as e:
        logging.error(f"Erro no resumo temporal: {e}")
        return jsonify({
            'error': 'Erro ao gerar resumo',
            'success': False
        }), 500

@mm_temporal_bp.route('/api/mm-temporal/<ticker>/pressure-evolution', methods=['GET'])
def get_pressure_evolution(ticker):
    """
    Endpoint específico para evolução de pressão (para gráficos)
    """
    try:
        days_back = int(request.args.get('days_back', 5))
        expiration_code = request.args.get('expiration')
        
        # Buscar dados
        spot_price = gamma_service.analyzer.data_provider.get_spot_price(ticker)
        oi_breakdown, _ = gamma_service.analyzer.data_provider.get_floqui_oi_breakdown(ticker, expiration_code)
        
        if not spot_price or not oi_breakdown:
            return jsonify({'error': 'Dados insuficientes', 'success': False}), 500
        
        # Análise
        temporal_result = mm_temporal_service.analyze_mm_temporal_complete(
            ticker, spot_price, oi_breakdown, days_back
        )
        
        if not temporal_result.get('success'):
            return jsonify({'error': 'Erro na análise', 'success': False}), 500
        
        # Retornar apenas dados de evolução
        pressure_data = {
            'ticker': ticker,
            'pressure_evolution': temporal_result['temporal_metrics']['pressure_evolution'],
            'summary': {
                'trend_direction': temporal_result['summary']['trend_direction'],
                'trend_magnitude_pct': temporal_result['summary']['trend_magnitude_pct']
            },
            'success': True
        }
        
        return jsonify(pressure_data)
        
    except Exception as e:
        logging.error(f"Erro na evolução de pressão: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@mm_temporal_bp.route('/api/mm-temporal/<ticker>/liquidity-status', methods=['GET'])
def get_liquidity_status(ticker):
    """
    Status de liquidez ATM em tempo real
    """
    try:
        expiration_code = request.args.get('expiration')
        
        # Dados necessários
        spot_price = gamma_service.analyzer.data_provider.get_spot_price(ticker)
        oi_breakdown, expiration_info = gamma_service.analyzer.data_provider.get_floqui_oi_breakdown(ticker, expiration_code)
        
        if not spot_price or not oi_breakdown:
            return jsonify({'error': 'Dados insuficientes', 'success': False}), 500
        
        # Análise focada em liquidez
        temporal_result = mm_temporal_service.analyze_mm_temporal_complete(
            ticker, spot_price, oi_breakdown, days_back=3  # Apenas 3 dias para liquidez
        )
        
        if not temporal_result.get('success'):
            return jsonify({'error': 'Erro na análise', 'success': False}), 500
        
        # Extrair dados de liquidez
        liquidity_consumption = temporal_result['temporal_metrics']['liquidity_consumption']
        current_liquidity = liquidity_consumption[-1]
        
        liquidity_status = {
            'ticker': ticker,
            'atm_liquidity_current': current_liquidity['atm_liquidity'],
            'consumption_rate': current_liquidity['consumption_rate'],
            'liquidity_status': temporal_result['summary']['liquidity_status'],
            'spot_price': spot_price,
            'expiration': expiration_info.get('desc') if expiration_info else None,
            'analysis_time': temporal_result['analysis_metadata']['analysis_date'],
            'success': True
        }
        
        return jsonify(liquidity_status)
        
    except Exception as e:
        logging.error(f"Erro no status de liquidez: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@mm_temporal_bp.route('/api/mm-temporal/health', methods=['GET'])
def health_check():
    """Health check para o serviço temporal"""
    try:
        return jsonify({
            'service': 'mm_temporal',
            'status': 'healthy',
            'timestamp': logging.Formatter().formatTime(logging.LogRecord(
                name='', level=0, pathname='', lineno=0,
                msg='', args=(), exc_info=None
            )),
            'available_endpoints': [
                '/api/mm-temporal/<ticker>',
                '/api/mm-temporal/<ticker>/summary',
                '/api/mm-temporal/<ticker>/pressure-evolution',
                '/api/mm-temporal/<ticker>/liquidity-status'
            ]
        })
    except Exception as e:
        return jsonify({
            'service': 'mm_temporal',
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# Registro de erro handlers
@mm_temporal_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint não encontrado',
        'success': False,
        'available_endpoints': [
            '/api/mm-temporal/<ticker>',
            '/api/mm-temporal/<ticker>/summary', 
            '/api/mm-temporal/<ticker>/pressure-evolution',
            '/api/mm-temporal/<ticker>/liquidity-status'
        ]
    }), 404

@mm_temporal_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Erro interno do servidor',
        'success': False
    }), 500