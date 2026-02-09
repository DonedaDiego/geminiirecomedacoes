"""
screening_routes.py - Rotas para Screening de Gamma Flip
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import traceback

from .screening_service import ScreeningService

def get_screening_blueprint():
    """Factory function para criar o blueprint do Screening"""
    
    screening_bp = Blueprint('screening', __name__)
    logging.basicConfig(level=logging.INFO)
    service = ScreeningService()

    @screening_bp.route('/pro/screening/flip', methods=['POST'])
    def screen_gamma_flip():        
        try:
            data = request.get_json()
            
            tickers = data.get('tickers', [])
            if not tickers or not isinstance(tickers, list):
                return jsonify({
                    'error': 'Lista de tickers é obrigatória',
                    'example': {'tickers': ['PETR4', 'VALE3', 'BBAS3']}
                }), 400
            
            # Remove duplicatas e limpa tickers
            tickers = list(set([t.strip().upper() for t in tickers if t.strip()]))
            
            if not tickers:
                return jsonify({'error': 'Nenhum ticker válido fornecido'}), 400
            
            # Configuração opcional de workers
            max_workers = data.get('max_workers')
            if max_workers:
                service.max_workers = min(max_workers, 10)  # Máximo de 10
            
            logging.info(f"API Screening: {len(tickers)} tickers solicitados")
            logging.info(f"Tickers: {', '.join(tickers[:5])}{'...' if len(tickers) > 5 else ''}")
            
            # Executa screening
            result = service.screen_multiple_tickers(tickers)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'screening_type': 'GAMMA_FLIP_MULTI',
                **result
            }
            
            logging.info(f"API Screening concluído: {result.get('successful_analysis', 0)}/{len(tickers)}")
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro no screening: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @screening_bp.route('/pro/screening/flip/single', methods=['POST'])
    def screen_single_ticker():
        """
        Screening de um único ticker (versão simplificada)
        
        Body JSON:
        {
            "ticker": "PETR4"
        }
        """
        try:
            data = request.get_json()
            
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            logging.info(f"API Screening Single: {ticker}")
            
            result = service.analyze_single_ticker(ticker)
            
            if not result:
                return jsonify({'error': 'Falha na análise do ticker'}), 404
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'screening_type': 'GAMMA_FLIP_SINGLE',
                'result': result
            }
            
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro no screening single: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @screening_bp.route('/pro/screening/presets', methods=['GET'])
    def get_preset_lists():
        """Retorna listas pré-definidas de ativos para screening"""
        
        presets = {
            'Todos':["ABEV3","ALOS3","ASAI3","AURE3","AXIA3","AXIA6","AZZA3","B3SA3","BBAS3","BBDC4","BBSE3","BEEF3",
                     "BRAP4","BRAV3","BRKM5","CEAB3","CMIG4","CMIN3","COGN3","CPFE3","CPLE3","CSAN3","CSMG3","CSNA3","CURY3","CXSE3","CYRE3","CYRE4",
                     "DIRR3","EGIE3","EMBJ3","ENEV3","ENGI11","EQTL3","FLRY3","GGBR4","GOAU4","HAPV3","HYPE3","IGTI11","IRBR3","ISAE4","ITSA4","ITUB4","KLBN11","LREN3","MBRF3","MGLU3","MOTV3",
                     "MRVE3","MULT3","NATU3","PCAR3","PETR4","POMO4","PRIO3","PSSA3","RADL3","RAIL3","RAIZ4","RDOR3","RECV3","RENT3","SANB11","SBSP3","SLCE3",
                     "SMFT3","SUZB3","TAEE11","TIMS3","TOTS3","UGPA3","USIM5","VALE3","VAMO3","VBBR3","VIVA3","VIVT3","WEGE3","YDUQ3",
],        

            'ibovespa_liquidos': [
                'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'BBAS3', 'ABEV3',
                'B3SA3', 'WEGE3', 'RENT3', 'ITSA4', 'SUZB3', 'EMBJ3'
            ],
            'alta_liquidez': [
                'BOVA11', 'PETR4', 'VALE3', 'BBAS3', 'B3SA3', 
                'ITSA4', 'BBDC4', 'MGLU3'
            ],
            'media_liquidez': [
                'ITUB4', 'ABEV3', 'WEGE3', 'RENT3', 'AXIA3', 
                'PRIO3', 'SUZB3', 'EMBJ3', 'CIEL3', 'RADL3'
            ],
            'small_caps': [
                'VIVT3', 'CSAN3', 'GGBR4', 'USIM5', 'BRAV3', 'BPAC11'
            ],
            'commodities': [
                'PETR4', 'VALE3', 'SUZB3', 'GGBR4', 'USIM5'
            ],
            'financeiro': [
                'ITUB4', 'BBDC4', 'BBAS3', 'B3SA3', 'BPAC11', 'ITSA4'
            ]
        }
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'presets': presets,
            'total_presets': len(presets)
        })

    @screening_bp.route('/pro/screening/health', methods=['GET'])
    def screening_health_check():
        """Health check do sistema de Screening"""
        return jsonify({
            'service': 'Gamma Flip Screening',
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0',
            'features': [
                'Multi-ticker Screening',
                'Parallel Processing',
                'Flip Distance Calculation',
                'Regime Detection',
                'Liquidity Classification',
                'Statistical Summary'
            ],
            'max_workers': service.max_workers
        })

    @screening_bp.route('/pro/screening/export-ntsl-batch', methods=['POST'])
    def export_all_flips_ntsl():
        """Exporta TODOS os Gamma Flips do screening para formato NTSL"""
        try:
            data = request.get_json()
            
            results = data.get('results', [])
            if not results or not isinstance(results, list):
                return jsonify({'error': 'Resultados são obrigatórios'}), 400
            
            logging.info(f"API: Exportação NTSL em lote solicitada para {len(results)} ativos")
            
            # Gerar código NTSL com todos os flips
            ntsl_code = generate_batch_flip_ntsl(results)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'total_tickers': len(results),
                'ntsl_code': ntsl_code,
                'message': f'Código NTSL gerado com {len(results)} ativos'
            }
            
            logging.info(f"API: NTSL em lote gerado com sucesso")
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro na exportação NTSL em lote: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    def generate_batch_flip_ntsl(results):
        """Gera código NTSL com TODOS os Gamma Flips - Estilo Condicional"""
        
        # Cabeçalho
        ntsl_code = f"""// GAMMA FLIP SCREENING - GEMINII TECH
// TOTAL DE ATIVOS: {len(results)}
// GERADO EM: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

const
"""
        
        # Lista de futuros BMF (se precisar)
        futuros_bmf = ['WIN', 'WDO', 'GLD', 'CCM', 'ICF', 'BGI', 'DI1', 'ETR', 'SOL', 'BIT', 'IND', 'DOL']
        
        # Declarar constantes dos ativos
        for result in results:
            ticker = result.get('ticker', '').replace('.SA', '')
            
            if ticker in futuros_bmf:
                ntsl_code += f"  {ticker} = Asset(\"{ticker}FUT\", feedBMF);\n"
            else:
                ntsl_code += f"  {ticker} = Asset(\"{ticker}\", feedBovespa);\n"
        
        # Variáveis
        ntsl_code += """
var
  gamma_flip : Float;
  ativo_atual : String;
  
begin
  ativo_atual := GetAsset;
  
"""
        
        # Gerar blocos condicionais para cada ticker
        for result in results:
            ticker = result.get('ticker', '').replace('.SA', '')
            flip_strike = result.get('flip_strike', 0)
            spot_price = result.get('spot_price', 0)
            regime = result.get('regime', 'Neutral')
            distance_pct = result.get('distance_pct', 0)
            
            # Emoji para comentário
            if regime == 'Long Gamma':
                emoji = '🟢'
            elif regime == 'Short Gamma':
                emoji = '🔴'
            else:
                emoji = '⚪'
            
            # Determinar comparação (futuro ou ação)
            if ticker in futuros_bmf:
                comparison = f'(ativo_atual = "{ticker}FUT")'
            else:
                comparison = f'(ativo_atual = "{ticker}")'
            
            # Bloco condicional para cada ticker
            ntsl_code += f"""  // {emoji} {ticker} - {regime} | Flip: R$ {flip_strike:.2f} | Spot: R$ {spot_price:.2f} | Dist: {distance_pct:+.2f}%
  if {comparison} then
  begin
    gamma_flip := {flip_strike:.2f};
    HorizontalLineCustom(gamma_flip, clWhite, 3, 2, "Flip {ticker}", 10, tpTopRight);
  end;
  
"""
        
        ntsl_code += "end;\n\n"
        
        # Documentação
        ntsl_code += "{\n"
        ntsl_code += "═══════════════════════════════════════════════════════════════\n"
        ntsl_code += " GAMMA FLIP SCREENING - GEMINII TECH\n"
        ntsl_code += "═══════════════════════════════════════════════════════════════\n"
        ntsl_code += f" TOTAL DE ATIVOS: {len(results)}\n"
        ntsl_code += f" DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        ntsl_code += "═══════════════════════════════════════════════════════════════\n\n"
        
        ntsl_code += " NÍVEIS IDENTIFICADOS:\n"
        ntsl_code += "───────────────────────────────────────────────────────────────\n"
        
        # Listar todos os ativos
        for result in results:
            ticker = result.get('ticker', '').replace('.SA', '')
            flip_strike = result.get('flip_strike', 0)
            spot_price = result.get('spot_price', 0)
            regime = result.get('regime', 'Neutral')
            distance_pct = result.get('distance_pct', 0)
            
            if regime == 'Long Gamma':
                emoji = '🟢'
            elif regime == 'Short Gamma':
                emoji = '🔴'
            else:
                emoji = '⚪'
            
            ntsl_code += f"{emoji} {ticker:8s} | Flip: R$ {flip_strike:7.2f} | Spot: R$ {spot_price:7.2f} | Dist: {distance_pct:+6.2f}% | {regime}\n"
        
        ntsl_code += " LEGENDA DOS REGIMES:\n"
        ntsl_code += "───────────────────────────────────────────────────────────────\n"
        ntsl_code += " 🟢 LONG GAMMA  (Preço acima do flip - mercado contido)\n"
        ntsl_code += "    → Market makers vendem volatilidade\n"
        ntsl_code += "    → Movimentos tendem a ser limitados\n"
        ntsl_code += "    → Bom para venda de opções\n\n"
        ntsl_code += " 🔴 SHORT GAMMA (Preço abaixo do flip - mercado explosivo)\n"
        ntsl_code += "    → Market makers compram volatilidade\n"
        ntsl_code += "    → Movimentos podem ser amplificados\n"
        ntsl_code += "    → Bom para compra direcional\n\n"
        ntsl_code += " ⚪ NEUTRAL     (Próximo ao flip - zona de transição)\n"
        ntsl_code += "    → Alta probabilidade de mudança de regime\n"
        ntsl_code += "    → Aguardar confirmação\n"
        ntsl_code += "\n═══════════════════════════════════════════════════════════════\n"
        ntsl_code += " 🚀 COMO USAR NO PROFIT\n"
        ntsl_code += "───────────────────────────────────────────────────────────────\n"
        ntsl_code += " 1. Copie TODO este código (já está copiado!)\n"
        ntsl_code += " 2. Abra o Editor de Estratégias no Profit\n"
        ntsl_code += " 3. Cole e salve como 'GammaFlip_Screening_Geminii'\n"
        ntsl_code += " 4. Execute no gráfico de QUALQUER ativo da lista\n"
        ntsl_code += " 5. A linha do flip aparecerá AUTOMATICAMENTE\n"
        ntsl_code += "\n DICA: Basta ABRIR o ativo no gráfico que a linha aparece!\n"
        ntsl_code += " Não precisa configurar nada, o código detecta sozinho.\n"        
        ntsl_code += "}\n"
        
        return ntsl_code

    return screening_bp