"""
bandas_pro_routes.py
Rotas da API para o sistema de Bandas PRO
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import traceback
import requests

# Import do serviço
from .bandas_pro_service import BandasProService

def get_bandas_pro_blueprint():
    """Factory function para criar o blueprint das bandas PRO"""
    
    bandas_pro_bp = Blueprint('bandas_pro', __name__)
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Instância do serviço
    service = BandasProService()

    @bandas_pro_bp.route('/pro/bandas/analyze', methods=['POST'])
    def analyze_complete():
        """Análise completa: Bandas + Flow"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            period = data.get('period', '6mo')
            flow_days = data.get('flow_days', 30)
            
            # Validações adicionais
            if flow_days < 7 or flow_days > 90:
                return jsonify({'error': 'flow_days deve estar entre 7 e 90'}), 400
            
            logging.info(f"API: Análise completa solicitada para {ticker}")
            
            # Executar análise
            
            result = service.analyze_complete(ticker, period, flow_days)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                **result
            }
            
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro na análise completa: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @bandas_pro_bp.route('/pro/bandas/analyze-bands', methods=['POST'])
    def analyze_bands_only():
        """Análise apenas das Bandas de Volatilidade"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            period = data.get('period', '6mo')
            logging.info(f"API: Análise de bandas solicitada para {ticker}")
            
            # Executar análise
            result = service.analyze_bands(ticker, period)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                **result
            }
            
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro na análise de bandas: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @bandas_pro_bp.route('/pro/bandas/analyze-flow', methods=['POST'])
    def analyze_flow_only():
        """Análise apenas do Flow de Opções"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            flow_days = data.get('flow_days', 30)
            
            # Validações adicionais
            if flow_days < 7 or flow_days > 90:
                return jsonify({'error': 'flow_days deve estar entre 7 e 90'}), 400
            
            logging.info(f"API: Análise de flow solicitada para {ticker}")
            
            # Executar análise
            result = service.analyze_flow(ticker, flow_days)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                **result
            }
            
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro na análise de flow: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @bandas_pro_bp.route('/pro/bandas/export-profit', methods=['POST'])
    def export_to_profit():
        """Exporta as bandas de volatilidade para formato NTSL (Profit)"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            bands_data = data.get('bands_data')
            
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            if not bands_data:
                return jsonify({'error': 'Dados das bandas são obrigatórios'}), 400
            
            logging.info(f"API: Exportação NTSL solicitada para {ticker}")
            
            # Extrair os últimos valores das bandas (mais recentes)
            try:
                # Função auxiliar para pegar último valor válido - CORREÇÃO AQUI
                def get_last_valid_value(data_input, default=0):
                    """
                    Extrai o último valor válido dos dados das bandas
                    Trata tanto listas quanto valores únicos
                    """
                    try:
                        # Se data_input é None ou vazio
                        if not data_input:
                            return default
                        
                        # Se é um número único (int, float)
                        if isinstance(data_input, (int, float)):
                            # Verificar se não é NaN
                            if data_input != data_input:  # NaN check
                                return default
                            return float(data_input)
                        
                        # Se é uma string (conversível para número)
                        if isinstance(data_input, str):
                            try:
                                value = float(data_input)
                                return value if value == value else default  # NaN check
                            except (ValueError, TypeError):
                                return default
                        
                        # Se é uma lista ou array
                        if hasattr(data_input, '__iter__') and not isinstance(data_input, str):
                            data_list = list(data_input)
                            if not data_list:
                                return default
                            
                            # Pegar o último valor válido (de trás para frente)
                            for i in range(len(data_list) - 1, -1, -1):
                                value = data_list[i]
                                if value is not None:
                                    try:
                                        float_value = float(value)
                                        # Verificar se não é NaN
                                        if float_value == float_value:
                                            return float_value
                                    except (ValueError, TypeError):
                                        continue
                            return default
                        
                        # Fallback: tentar conversão direta
                        try:
                            value = float(data_input)
                            return value if value == value else default
                        except (ValueError, TypeError):
                            return default
                            
                    except Exception as e:
                        logging.warning(f"Erro ao processar valor {data_input}: {e}")
                        return default
                
                # Extrair valores das bandas usando a função corrigida
                linha_central = get_last_valid_value(bands_data.get('linha_central'), 0)
                
                # Tentar diferentes variações das chaves para 2σ
                superior_2sigma = (
                    get_last_valid_value(bands_data.get('superior_2sigma'), 0) or
                    get_last_valid_value(bands_data.get('superior_2σ'), 0) or
                    get_last_valid_value(bands_data.get('banda_superior_2sigma'), 0)
                )
                
                inferior_2sigma = (
                    get_last_valid_value(bands_data.get('inferior_2sigma'), 0) or
                    get_last_valid_value(bands_data.get('inferior_2σ'), 0) or
                    get_last_valid_value(bands_data.get('banda_inferior_2sigma'), 0)
                )
                
                # Tentar diferentes variações das chaves para 4σ
                superior_4sigma = (
                    get_last_valid_value(bands_data.get('superior_4sigma'), 0) or
                    get_last_valid_value(bands_data.get('superior_4σ'), 0) or
                    get_last_valid_value(bands_data.get('banda_superior_4sigma'), 0)
                )
                
                inferior_4sigma = (
                    get_last_valid_value(bands_data.get('inferior_4sigma'), 0) or
                    get_last_valid_value(bands_data.get('inferior_4σ'), 0) or
                    get_last_valid_value(bands_data.get('banda_inferior_4sigma'), 0)
                )
                
                logging.info(f"Dados recebidos - Todas as chaves: {list(bands_data.keys())}")
                logging.info(f"Valores extraídos:")
                logging.info(f"  - LC: {linha_central}")
                logging.info(f"  - Superior 2σ: {superior_2sigma}")
                logging.info(f"  - Inferior 2σ: {inferior_2sigma}")
                logging.info(f"  - Superior 4σ: {superior_4sigma}")
                logging.info(f"  - Inferior 4σ: {inferior_4sigma}")
                
                # Validar se temos valores válidos - relaxar a validação para 4σ
                if all(v == 0 for v in [linha_central, superior_2sigma, inferior_2sigma]):
                    return jsonify({'error': 'Não foi possível extrair valores válidos das bandas principais'}), 400
                
                # Validação adicional de consistência
                if superior_2sigma <= inferior_2sigma:
                    logging.warning("Valores de bandas inconsistentes detectados")
                    # Tentar ajustar usando uma margem padrão
                    if linha_central > 0:
                        margin = linha_central * 0.05  # 5% de margem
                        if superior_2sigma == 0:
                            superior_2sigma = linha_central + margin
                        if inferior_2sigma == 0:
                            inferior_2sigma = linha_central - margin
                
            except Exception as e:
                logging.error(f"Erro ao extrair valores das bandas: {str(e)}")
                return jsonify({'error': f'Erro ao processar dados das bandas: {str(e)}'}), 400
            
            # Gerar código NTSL
            bands_values = {
                'linha_central': linha_central,
                'resistencia_2sigma': superior_2sigma,
                'suporte_2sigma': inferior_2sigma,
                'resistencia_4sigma': superior_4sigma,
                'suporte_4sigma': inferior_4sigma
            }
            
            ntsl_code = generate_ntsl_code(ticker, bands_values)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                'ntsl_code': ntsl_code,
                'bands_values': bands_values,
                'message': f'Código NTSL gerado com sucesso para {ticker}'
            }
            
            logging.info(f"API: NTSL gerado com sucesso para {ticker}")
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação na exportação: {str(e)}")
            return jsonify({'error': str(e)}), 400
            
        except Exception as e:
            logging.error(f"Erro na exportação NTSL: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    def generate_ntsl_code(ticker, bands):
        """Gera o código NTSL com as bandas de volatilidade"""
        
        # Limpar ticker para exibição
        display_ticker = ticker.replace('.SA', '')
        
        ntsl_template = f'''
        var
        // Bandas calculadas pelo modelo avançado
        linha_central : Float;
        resistencia_2sigma, suporte_2sigma : Float;
        resistencia_4sigma, suporte_4sigma : Float;

        begin
        // ===== VALORES CALCULADOS PELO MODELO =====
        linha_central := {bands['linha_central']:.2f};
        resistencia_2sigma := {bands['resistencia_2sigma']:.2f};
        suporte_2sigma := {bands['suporte_2sigma']:.2f};
        resistencia_4sigma := {bands['resistencia_4sigma']:.2f};
        suporte_4sigma := {bands['suporte_4sigma']:.2f};
        
        // ===== TRAÇANDO AS LINHAS NO GRÁFICO =====
        HorizontalLine(linha_central, RGB(255, 215, 0));           // Linha Central - Dourado
        HorizontalLine(resistencia_2sigma, RGB(255, 107, 107));    // R2σ - Vermelho claro
        HorizontalLine(suporte_2sigma, RGB(46, 213, 115));        // S2σ - Verde claro
        HorizontalLine(resistencia_4sigma, RGB(255, 71, 87));      // R4σ - Vermelho forte
        HorizontalLine(suporte_4sigma, RGB(0, 184, 148));         // S4σ - Verde forte
            
        end;

        {{
        ═══════════════════════════════════════════════════════════════
        COMO USAR NO PROFIT ULTRA:
        ═══════════════════════════════════════════════════════════════
        1. Copie todo este código
        2. Abra o Editor de Estratégias no Profit
        3. Cole o código e salve como "{display_ticker}_Bandas_Geminii"
        4. Execute no gráfico do {display_ticker}
        5. As linhas de suporte e resistência aparecerão automaticamente

        ═══════════════════════════════════════════════════════════════
        🎯 LEGENDA DAS BANDAS:
        ═══════════════════════════════════════════════════════════════
        🟡 LINHA CENTRAL ({bands['linha_central']:.2f})
        → Preço equilibrado calculado pelo modelo

        🔴 RESISTÊNCIAS:
        → R2σ: {bands['resistencia_2sigma']:.2f} (Resistência Primária)
        → R4σ: {bands['resistencia_4sigma']:.2f} (Resistência Extrema)

        🟢 SUPORTES:
        → S2σ: {bands['suporte_2sigma']:.2f} (Suporte Primário)  
        → S4σ: {bands['suporte_4sigma']:.2f} (Suporte Extremo)

        ═══════════════════════════════════════════════════════════════
        ⚡ INTERPRETAÇÃO:
        ═══════════════════════════════════════════════════════════════
        • COMPRA: Preço próximo ou abaixo dos suportes (S2σ/S4σ)
        • VENDA: Preço próximo ou acima das resistências (R2σ/R4σ)  
        • NEUTRO: Preço entre suporte S2σ e resistência R2σ
        • EXTREMO: Preço além das bandas 4σ (reversão provável)

        ═══════════════════════════════════════════════════════════════
        🤖 GERADO POR: Sistema Geminii Tech - Bandas Híbridas
        📈 TECNOLOGIA: GARCH + Machine Learning (XGBoost)
        🎲 VARIÁVEIS: 15+ indicadores técnicos e estatísticos
        ═══════════════════════════════════════════════════════════════
        }}'''

        return ntsl_template


    @bandas_pro_bp.route('/pro/bandas/ticker-details', methods=['POST'])
    def get_ticker_details():
        """Busca detalhes específicos do ticker (IV, volume, correlação, etc.)"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            logging.info(f"API: Detalhes do ticker solicitados para {ticker}")
            
            # Buscar detalhes do ticker
            result = service.get_ticker_details(ticker)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                **result
            }
            
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro ao buscar detalhes do ticker: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @bandas_pro_bp.route('/pro/bandas/ticker-search', methods=['GET'])
    def search_tickers():
        """Busca tickers disponíveis (lista simplificada para autocomplete)"""
        try:
            # Parâmetros de busca
            query = request.args.get('q', '').strip().upper()
            limit = min(int(request.args.get('limit', 20)), 100)
            
            logging.info(f"API: Busca de tickers com query '{query}'")
            
            # CORREÇÃO: Usar o serviço de ticker details ao invés de requisição direta
            ticker_service = service.ticker_details_service
            
            try:
                # Tentar buscar com parâmetros primeiro
                if query:
                    params = {
                        'symbol': query,
                        'limit': limit
                    }
                    response = requests.get(
                        ticker_service.base_url, 
                        headers=ticker_service.headers, 
                        params=params,
                        timeout=30
                    )
                else:
                    # Buscar lista geral
                    response = requests.get(
                        f"{ticker_service.base_url}/all", 
                        headers=ticker_service.headers, 
                        timeout=30
                    )
                
                if response.status_code != 200:
                    return jsonify({'error': 'Erro ao buscar tickers na API'}), 500
                
                all_stocks = response.json()
                
            except Exception as e:
                logging.error(f"Erro na API OpLab: {e}")
                return jsonify({'error': 'Erro de conexão com a API OpLab'}), 500
            
            # Filtrar e formatar para autocomplete
            filtered_tickers = []
            
            for stock in all_stocks:
                symbol = stock.get('symbol', '')
                name = stock.get('name', '')
                
                # Aplicar filtro se fornecido
                if query:
                    if not (query in symbol or query in name.upper()):
                        continue
                
                # Adicionar à lista
                filtered_tickers.append({
                    'symbol': symbol,
                    'name': name,
                    'type': stock.get('type'),
                    'has_options': stock.get('has_options', False),
                    'close': stock.get('close'),
                    'variation': stock.get('variation'),
                    'volume': stock.get('volume')
                })
                
                # Limitar resultados
                if len(filtered_tickers) >= limit:
                    break
            
            # Ordenar por símbolo
            filtered_tickers.sort(key=lambda x: x['symbol'])
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'query': query,
                'count': len(filtered_tickers),
                'tickers': filtered_tickers
            }
            
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro na busca de tickers: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @bandas_pro_bp.route('/pro/bandas/health', methods=['GET'])
    def health_check():
        """Health check da API"""
        return jsonify({
            'status': 'healthy',
            'service': 'Bandas PRO API',
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat(),
            'endpoints': [
                'POST /pro/bandas/analyze - Análise Completa',
                'POST /pro/bandas/analyze-bands - Apenas Bandas',
                'POST /pro/bandas/analyze-flow - Apenas Flow',
                'POST /pro/bandas/export-profit - Exportar para Profit',
                'POST /pro/bandas/ticker-details - Detalhes do Ticker',  # NOVO
                'GET /pro/bandas/ticker-search - Buscar Tickers',        # NOVO
                'POST /pro/bandas/tickers/validate - Validar Ticker',
                'GET /pro/bandas/status - Status do Serviço',
                'GET /pro/bandas/health - Health Check'
            ]
        })

    @bandas_pro_bp.route('/pro/bandas/tickers/validate', methods=['POST'])
    def validate_ticker():
        """Valida se um ticker está disponível"""
        try:
            data = request.get_json()
            ticker = data.get('ticker', '').strip().upper()
            
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            # Tentar carregar dados básicos para validar
            from .bandas_pro_service import HybridVolatilityBands
            import yfinance as yf
            
            # Normalizar ticker
            if len(ticker) <= 6 and not ticker.endswith('.SA') and '-' not in ticker:
                test_ticker = ticker + '.SA'
            else:
                test_ticker = ticker
            
            # Testar se ticker existe
            stock = yf.Ticker(test_ticker)
            info = stock.info
            
            # Verificar se tem dados básicos
            if not info or 'regularMarketPrice' not in info:
                return jsonify({
                    'valid': False,
                    'ticker': ticker,
                    'message': 'Ticker não encontrado ou sem dados'
                })
            
            return jsonify({
                'valid': True,
                'ticker': ticker,
                'normalized_ticker': test_ticker,
                'name': info.get('longName', ticker),
                'currency': info.get('currency', 'BRL'),
                'market': info.get('exchange', 'BVSP')
            })
            
        except Exception as e:
            return jsonify({
                'valid': False,
                'ticker': ticker if 'ticker' in locals() else '',
                'message': f'Erro na validação: {str(e)}'
            })

    @bandas_pro_bp.route('/pro/bandas/status', methods=['GET'])
    def service_status():
        """Status detalhado do serviço"""
        try:
            # Testar componentes principais
            from .bandas_pro_service import VolatilityValidator, GeminiiFlowTracker
            
            status = {
                'service': 'Bandas PRO',
                'timestamp': datetime.now().isoformat(),
                'status': 'operational',
                'components': {}
            }
            
            # Testar validador IV
            try:
                iv_validator = VolatilityValidator()
                status['components']['iv_validator'] = 'operational'
            except Exception as e:
                status['components']['iv_validator'] = f'error: {str(e)}'
            
            # Testar flow tracker
            try:
                flow_tracker = GeminiiFlowTracker()
                status['components']['flow_tracker'] = 'operational'
            except Exception as e:
                status['components']['flow_tracker'] = f'error: {str(e)}'
            
            # Testar yfinance
            try:
                import yfinance as yf
                status['components']['yfinance'] = 'operational'
            except Exception as e:
                status['components']['yfinance'] = f'error: {str(e)}'
            
            # Testar bibliotecas ML
            try:
                import xgboost as xgb
                from arch import arch_model
                status['components']['ml_libraries'] = 'operational'
            except Exception as e:
                status['components']['ml_libraries'] = f'error: {str(e)}'
            
            return jsonify(status)
            
        except Exception as e:
            return jsonify({
                'service': 'Bandas PRO',
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e)
            }), 500

    return bandas_pro_bp