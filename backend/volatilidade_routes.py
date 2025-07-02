from flask import Blueprint, request, jsonify
from volatilidade_service import VolatilidadeService
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar blueprint
volatilidade_bp = Blueprint('volatilidade', __name__)

@volatilidade_bp.route('/api/volatilidade/analise', methods=['POST'])
def analise_volatilidade():
    """
    Endpoint para análise completa de volatilidade de ações
    
    Parâmetros esperados no JSON:
    - ticker: código da ação (ex: 'PETR4')
    - year: ano para análise (ex: '2024')
    - inicio: data de início (opcional, padrão: '2020-01-01')
    - fim: data de fim (opcional, padrão: '2025-12-31')
    """
    try:
        # Obter dados do request
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400
        
        ticker = data.get('ticker', '').strip().upper()
        year = data.get('year', '2024')
        inicio = data.get('inicio', '2020-01-01')
        fim = data.get('fim', '2025-12-31')
        
        # Validações básicas
        if not ticker:
            return jsonify({'success': False, 'error': 'Ticker é obrigatório'}), 400
        
        if not year:
            return jsonify({'success': False, 'error': 'Ano é obrigatório'}), 400
        
        # Instanciar serviço
        volatilidade_service = VolatilidadeService()
        
        # Executar análise
        resultado = volatilidade_service.analyze_volatility(
            ticker=ticker,
            year=year,
            inicio=inicio,
            fim=fim
        )
        
        if not resultado.get('success'):
            return jsonify(resultado), 400
        
        logger.info(f"Análise de volatilidade realizada com sucesso para {ticker}")
        return jsonify(resultado), 200
        
    except Exception as e:
        logger.error(f"Erro na análise de volatilidade: {str(e)}")
        return jsonify({'success': False, 'error': f'Erro interno do servidor: {str(e)}'}), 500

@volatilidade_bp.route('/api/volatilidade/graficos', methods=['POST'])
def gerar_graficos_volatilidade():
    """
    Endpoint para gerar apenas os gráficos de volatilidade
    
    Parâmetros esperados no JSON:
    - ticker: código da ação (ex: 'PETR4')
    - year: ano para análise (ex: '2024')
    - inicio: data de início (opcional, padrão: '2020-01-01')
    - fim: data de fim (opcional, padrão: '2025-12-31')
    """
    try:
        # Obter dados do request
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400
        
        ticker = data.get('ticker', '').strip().upper()
        year = data.get('year', '2024')
        inicio = data.get('inicio', '2020-01-01')
        fim = data.get('fim', '2025-12-31')
        
        # Validações básicas
        if not ticker or not year:
            return jsonify({'success': False, 'error': 'Ticker e ano são obrigatórios'}), 400
        
        # Instanciar serviço
        volatilidade_service = VolatilidadeService()
        
        # Executar análise completa (necessária para gerar gráficos)
        resultado = volatilidade_service.analyze_volatility(
            ticker=ticker,
            year=year,
            inicio=inicio,
            fim=fim
        )
        
        if not resultado.get('success'):
            return jsonify(resultado), 400
        
        # Retornar apenas os gráficos
        response = {
            'success': True,
            'ticker': ticker,
            'year': year,
            'chart_annual': resultado.get('chart_annual'),
            'chart_weekly': resultado.get('chart_weekly')
        }
        
        logger.info(f"Gráficos de volatilidade gerados com sucesso para {ticker}")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Erro na geração de gráficos: {str(e)}")
        return jsonify({'success': False, 'error': f'Erro interno do servidor: {str(e)}'}), 500

@volatilidade_bp.route('/api/volatilidade/niveis', methods=['POST'])
def calcular_niveis_volatilidade():
    """
    Endpoint para calcular apenas os níveis de suporte e resistência
    
    Parâmetros esperados no JSON:
    - ticker: código da ação (ex: 'PETR4')
    - year: ano para análise (ex: '2024')
    - inicio: data de início (opcional, padrão: '2020-01-01')
    - fim: data de fim (opcional, padrão: '2025-12-31')
    """
    try:
        # Obter dados do request
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400
        
        ticker = data.get('ticker', '').strip().upper()
        year = data.get('year', '2024')
        inicio = data.get('inicio', '2020-01-01')
        fim = data.get('fim', '2025-12-31')
        
        # Validações básicas
        if not ticker or not year:
            return jsonify({'success': False, 'error': 'Ticker e ano são obrigatórios'}), 400
        
        # Instanciar serviço
        volatilidade_service = VolatilidadeService()
        
        # Obter dados
        asset_data = volatilidade_service.get_data(ticker, start=inicio, end=fim)
        
        if asset_data is None:
            return jsonify({'success': False, 'error': f'Não foi possível obter dados para {ticker}'}), 400
        
        # Processar dados
        processed_data = volatilidade_service.processar_dados(asset_data)
        
        if processed_data is None:
            return jsonify({'success': False, 'error': 'Erro ao processar dados'}), 400
        
        # Calcular níveis
        niveis, error_msg = volatilidade_service.calcular_niveis_anuais(processed_data, year)
        
        if niveis is None:
            return jsonify({'success': False, 'error': error_msg}), 400
        
        # Análise da posição atual
        current_price = float(processed_data['close'].iloc[-1])
        price_position = volatilidade_service._analyze_price_position(current_price, niveis)
        
        response = {
            'success': True,
            'ticker': ticker,
            'year': year,
            'current_price': round(current_price, 2),
            'price_position': price_position,
            'niveis': niveis,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        logger.info(f"Níveis de volatilidade calculados com sucesso para {ticker}")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Erro no cálculo de níveis: {str(e)}")
        return jsonify({'success': False, 'error': f'Erro interno do servidor: {str(e)}'}), 500

@volatilidade_bp.route('/api/volatilidade/symbols', methods=['GET'])
def get_available_symbols():
    """
    Endpoint para obter lista de símbolos disponíveis
    """
    try:
        volatilidade_service = VolatilidadeService()
        symbols = volatilidade_service.get_available_symbols()
        
        return jsonify({
            'success': True,
            'symbols': symbols,
            'count': len(symbols)
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter símbolos: {str(e)}")
        return jsonify({'success': False, 'error': f'Erro interno do servidor: {str(e)}'}), 500

@volatilidade_bp.route('/api/volatilidade/status', methods=['GET'])
def get_status():
    """
    Endpoint para verificar o status do serviço
    """
    try:
        return jsonify({
            'success': True,
            'service': 'Análise de Volatilidade',
            'version': '1.0.0',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'endpoints': [
                '/api/volatilidade/analise',
                '/api/volatilidade/graficos', 
                '/api/volatilidade/niveis',
                '/api/volatilidade/symbols',
                '/api/volatilidade/status'
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter status: {str(e)}")
        return jsonify({'success': False, 'error': f'Erro interno do servidor: {str(e)}'}), 500