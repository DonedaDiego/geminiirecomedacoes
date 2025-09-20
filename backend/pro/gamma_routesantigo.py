"""
gamma_routes.py
Rotas da API para o sistema de Gamma Exposure Analysis
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import traceback

# Import do serviço
from .gamma_serviceantigo import GammaService

def get_gamma_blueprint():
    """Factory function para criar o blueprint do gamma"""
    
    gamma_bp = Blueprint('gamma', __name__)
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Instância do serviço
    service = GammaService()

    @gamma_bp.route('/pro/gamma/analyze', methods=['POST'])
    def analyze_gamma():
        """Análise completa de Gamma Exposure"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            days_back = data.get('days_back', 60)
            
            # Validações adicionais
            if days_back < 7 or days_back > 180:
                return jsonify({'error': 'days_back deve estar entre 7 e 180'}), 400
            
            logging.info(f"API: Análise de gamma solicitada para {ticker}")
            
            # Executar análise
            result = service.analyze_gamma_complete(ticker, days_back)
            
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
            logging.error(f"Erro na análise de gamma: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @gamma_bp.route('/pro/gamma/summary', methods=['POST'])
    def get_gamma_summary():
        """Resumo executivo da análise de gamma"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            days_back = data.get('days_back', 60)
            
            logging.info(f"API: Resumo de gamma solicitado para {ticker}")
            
            # Executar análise completa
            analysis_result = service.analyze_gamma_complete(ticker, days_back)
            
            # Gerar resumo
            summary = service.get_gamma_summary(analysis_result)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                'summary': summary,
                'full_analysis_available': True
            }
            
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro no resumo de gamma: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @gamma_bp.route('/pro/gamma/walls', methods=['POST'])
    def get_gamma_walls_only():
        """Busca apenas os gamma walls sem análise completa"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            days_back = data.get('days_back', 60)
            max_walls = data.get('max_walls', 6)
            
            # Validações
            if max_walls < 1 or max_walls > 20:
                return jsonify({'error': 'max_walls deve estar entre 1 e 20'}), 400
            
            logging.info(f"API: Gamma walls solicitados para {ticker}")
            
            # Executar análise
            result = service.analyze_gamma_complete(ticker, days_back)
            
            # Filtrar apenas os walls
            walls = result.get('walls', [])[:max_walls]
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                'spot_price': result.get('spot_price'),
                'walls': walls,
                'total_walls': len(walls)
            }
            
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro ao buscar gamma walls: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @gamma_bp.route('/pro/gamma/metrics', methods=['POST'])
    def get_gamma_metrics_only():
        """Busca apenas as métricas de gamma sem gráficos"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            days_back = data.get('days_back', 60)
            
            logging.info(f"API: Métricas de gamma solicitadas para {ticker}")
            
            # Executar análise
            result = service.analyze_gamma_complete(ticker, days_back)
            
            # Extrair apenas métricas
            metrics = result.get('metrics', {})
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                'spot_price': result.get('spot_price'),
                'options_count': result.get('options_count'),
                'metrics': metrics
            }
            
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro ao buscar métricas de gamma: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @gamma_bp.route('/pro/gamma/export-alerts', methods=['POST'])
    def export_gamma_alerts():
        """Exporta alertas de gamma para integração externa"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            alert_format = data.get('format', 'json')  # json, webhook, email
            threshold_intensity = data.get('threshold', 0.7)  # Só walls > 70% intensidade
            
            logging.info(f"API: Export de alertas solicitado para {ticker}")
            
            # Executar análise
            result = service.analyze_gamma_complete(ticker, days_back=60)
            
            # Filtrar walls por intensidade
            walls = result.get('walls', [])
            strong_walls = [w for w in walls if w.get('intensity', 0) >= threshold_intensity]
            
            # Gerar alertas
            alerts = []
            for wall in strong_walls:
                alert = {
                    'ticker': ticker.replace('.SA', ''),
                    'type': 'GAMMA_WALL',
                    'wall_type': wall['type'],
                    'strike': wall['strike'],
                    'intensity': wall['intensity'],
                    'distance_pct': wall['distance_pct'],
                    'timestamp': datetime.now().isoformat(),
                    'message': f"{wall['type']} wall at R$ {wall['strike']:.2f} - Intensity: {wall['intensity']:.1%}"
                }
                alerts.append(alert)
            
            # Adicionar alerta de regime
            metrics = result.get('metrics', {})
            regime_alert = {
                'ticker': ticker.replace('.SA', ''),
                'type': 'GAMMA_REGIME',
                'regime': metrics.get('gamma_regime'),
                'net_exposure': metrics.get('net_gamma_exposure'),
                'volatility_expectation': metrics.get('volatility_expectation'),
                'timestamp': datetime.now().isoformat(),
                'message': f"Gamma Regime: {metrics.get('gamma_regime')} - Expected Vol: {metrics.get('volatility_expectation')}"
            }
            alerts.append(regime_alert)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                'format': alert_format,
                'alerts_count': len(alerts),
                'alerts': alerts
            }
            
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro no export de alertas: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @gamma_bp.route('/pro/gamma/validate-ticker', methods=['POST'])
    def validate_ticker_gamma():
        """Valida se um ticker tem dados de opções suficientes para análise gamma"""
        try:
            data = request.get_json()
            ticker = data.get('ticker', '').strip().upper()
            
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            # Tentar obter preço e dados básicos
            analyzer = service.analyzer
            
            # Teste 1: Preço atual
            spot_price = analyzer.get_current_spot_price(ticker)
            if not spot_price:
                return jsonify({
                    'valid': False,
                    'ticker': ticker,
                    'reason': 'Ticker não encontrado ou sem dados de preço',
                    'has_options': False
                })
            
            # Teste 2: Dados de opções disponíveis
            options_data = analyzer.get_options_data(ticker, days_back=7)  # Teste rápido
            if not options_data:
                return jsonify({
                    'valid': False,
                    'ticker': ticker,
                    'reason': 'Sem dados de opções disponíveis',
                    'has_options': False,
                    'spot_price': spot_price
                })
            
            # Teste 3: Opções com gamma válido
            df = analyzer.process_options_data(options_data, spot_price)
            valid_options = len(df) if not df.empty else 0
            
            is_valid = valid_options >= 10  # Mínimo de 10 opções para análise confiável
            
            return jsonify({
                'valid': is_valid,
                'ticker': ticker.replace('.SA', ''),
                'spot_price': spot_price,
                'has_options': True,
                'valid_options_count': valid_options,
                'minimum_required': 10,
                'reason': 'Ticker válido para análise gamma' if is_valid else f'Poucas opções válidas ({valid_options}<10)'
            })
            
        except Exception as e:
            return jsonify({
                'valid': False,
                'ticker': ticker if 'ticker' in locals() else '',
                'reason': f'Erro na validação: {str(e)}',
                'has_options': False
            })

    @gamma_bp.route('/pro/gamma/status', methods=['GET'])
    def gamma_status():
        """Status detalhado do serviço de gamma"""
        try:
            # Testar componentes principais
            status = {
                'service': 'Gamma Exposure Analysis',
                'timestamp': datetime.now().isoformat(),
                'status': 'operational',
                'components': {}
            }
            
            # Testar analyzer
            try:
                analyzer = service.analyzer
                status['components']['gamma_analyzer'] = 'operational'
            except Exception as e:
                status['components']['gamma_analyzer'] = f'error: {str(e)}'
            
            # Testar API OpLab
            try:
                test_response = analyzer.get_options_data('PETR4', days_back=1)
                status['components']['oplab_api'] = 'operational' if test_response else 'limited'
            except Exception as e:
                status['components']['oplab_api'] = f'error: {str(e)}'
            
            # Testar yfinance
            try:
                import yfinance as yf
                status['components']['yfinance'] = 'operational'
            except Exception as e:
                status['components']['yfinance'] = f'error: {str(e)}'
            
            # Testar bibliotecas científicas
            try:
                import scipy
                import numpy as np
                import pandas as pd
                status['components']['scientific_libraries'] = 'operational'
            except Exception as e:
                status['components']['scientific_libraries'] = f'error: {str(e)}'
            
            return jsonify(status)
            
        except Exception as e:
            return jsonify({
                'service': 'Gamma Exposure Analysis',
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e)
            }), 500

    @gamma_bp.route('/pro/gamma/export-walls', methods=['POST'])
    def export_gamma_walls():
        """Exporta os gamma walls para formato NTSL (Profit)"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            walls_data = data.get('walls_data')
            spot_price = data.get('spot_price')
            
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            if not walls_data:
                return jsonify({'error': 'Dados dos walls são obrigatórios'}), 400
            
            logging.info(f"API: Exportação NTSL Gamma solicitada para {ticker}")
            
            # Gerar código NTSL para Gamma Walls
            ntsl_code = generate_gamma_walls_ntsl(ticker, walls_data, spot_price)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                'ntsl_code': ntsl_code,
                'walls_count': len(walls_data),
                'message': f'Código NTSL Gamma Walls gerado com sucesso para {ticker}'
            }
            
            logging.info(f"API: NTSL Gamma gerado com sucesso para {ticker}")
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação na exportação: {str(e)}")
            return jsonify({'error': str(e)}), 400
            
        except Exception as e:
            logging.error(f"Erro na exportação NTSL Gamma: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    def generate_gamma_walls_ntsl(ticker, walls, spot_price):
        """Gera o código NTSL com os gamma walls"""
        
        # Limpar ticker para exibição
        display_ticker = ticker.replace('.SA', '')
        
        # Separar walls por tipo
        support_walls = [w for w in walls if w['type'] == 'Support']
        resistance_walls = [w for w in walls if w['type'] == 'Resistance']
        
        # Criar variáveis para os strikes
        support_lines = []
        resistance_lines = []
        variables_declaration = []
        
        # Processar Support Walls
        for i, wall in enumerate(support_walls[:5]):  # Máximo 5 suportes
            var_name = f"suporte_gamma_{i+1}"
            variables_declaration.append(f"{var_name} : Float;")
            support_lines.append(f"{var_name} := {wall['strike']:.2f};")
            support_lines.append(f'HorizontalLineCustom({var_name}, RGB(173, 216, 230), 3, 2, "Support Gamma {i+1} - {wall["intensity"]:.1%}", 8, tpTopRight, 0, 0, 0, 0);')
        
        # Processar Resistance Walls
        for i, wall in enumerate(resistance_walls[:5]):  # Máximo 5 resistências
            var_name = f"resistencia_gamma_{i+1}"
            variables_declaration.append(f"{var_name} : Float;")
            resistance_lines.append(f"{var_name} := {wall['strike']:.2f};")
            resistance_lines.append(f'HorizontalLineCustom({var_name}, RGB(173, 216, 230), 3, 2, "Resistance Gamma {i+1} - {wall["intensity"]:.1%}", 8, tpTopRight, 0, 0, 0, 0);')
        
        ntsl_template = f'''
    var
    // Gamma Walls detectados pelo sistema avançado
    {chr(10).join(variables_declaration)}

    begin
    // ===== VALORES DOS GAMMA WALLS =====

    // --- SUPORTES GAMMA ---
    {chr(10).join(support_lines)}

    // --- RESISTÊNCIAS GAMMA ---
    {chr(10).join(resistance_lines)}

    end;

    {{
    ═══════════════════════════════════════════════════════════════
    COMO USAR NO PROFIT ULTRA:
    ═══════════════════════════════════════════════════════════════
    1. Copie todo este código
    2. Abra o Editor de Estratégias no Profit
    3. Cole o código e salve como "{display_ticker}_Gamma_Walls"
    4. Execute no gráfico do {display_ticker}
    5. Os walls de gamma aparecerão automaticamente

    ═══════════════════════════════════════════════════════════════
    LEGENDA DOS GAMMA WALLS:
    ═══════════════════════════════════════════════════════════════
    💎 WALLS GAMMA (Azul Claro Tracejado):

    🟢 SUPORTES GAMMA:
    {chr(10).join([f"→ S{i+1}: {w['strike']:.2f} (Intensidade: {w['intensity']:.1%})" for i, w in enumerate(support_walls[:5])])}

    🔴 RESISTÊNCIAS GAMMA:
    {chr(10).join([f"→ R{i+1}: {w['strike']:.2f} (Intensidade: {w['intensity']:.1%})" for i, w in enumerate(resistance_walls[:5])])}

    ═══════════════════════════════════════════════════════════════
    ⚡ INTERPRETAÇÃO DOS GAMMA WALLS:
    ═══════════════════════════════════════════════════════════════
    - SUPORTE: Market makers têm gamma positivo concentrado
    - RESISTÊNCIA: Market makers têm gamma negativo concentrado  
    - INTENSIDADE: Força do wall (maior = mais provável de segurar)
    - QUEBRA: Movimento forte quando wall é rompido com volume
    - COR: Azul claro tracejado (espessura 3) para fácil identificação

    ═══════════════════════════════════════════════════════════════
    🤖 GERADO POR: Sistema Geminii Tech - Gamma Levels
     TECNOLOGIA: Net Gamma Exposure + Peak Detection
     ALGORITMO: Detecção científica com suavização Gaussian
     PREÇO ATUAL: R$ {spot_price:.2f}
    ═══════════════════════════════════════════════════════════════
    }}'''

        return ntsl_template
    
    
    @gamma_bp.route('/pro/gamma/health', methods=['GET'])
    def health_check():
        """Health check da API de Gamma"""
        return jsonify({
            'status': 'healthy',
            'service': 'Gamma Exposure API',
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat(),
            'endpoints': [
                'POST /pro/gamma/analyze - Análise Completa de Gamma',
                'POST /pro/gamma/summary - Resumo Executivo',
                'POST /pro/gamma/walls - Apenas Gamma Walls',
                'POST /pro/gamma/metrics - Apenas Métricas',
                'POST /pro/gamma/export-alerts - Exportar Alertas',
                'POST /pro/gamma/validate-ticker - Validar Ticker',
                'GET /pro/gamma/status - Status do Serviço',
                'GET /pro/gamma/health - Health Check'
            ],
            'features': [
                'Net Gamma Exposure Calculation',
                'Gamma Walls Detection (Support/Resistance)',
                'Market Maker Position Analysis',
                'Volatility Regime Classification',
                'Real-time Options Data Integration',
                'Advanced Signal Processing'
            ]
        })

    return gamma_bp