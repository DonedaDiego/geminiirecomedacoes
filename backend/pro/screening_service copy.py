"""
screening_service.py - Screening de Gamma Flip para múltiplos ativos
"""

import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from .gamma_service import GammaService, convert_to_json_serializable

logging.basicConfig(level=logging.INFO)


class ScreeningService:
    def __init__(self):
        self.gamma_service = GammaService()
        self.max_workers = 5  # Limite de threads paralelas
    
    def analyze_single_ticker(self, ticker):
        """Analisa um único ticker e retorna dados resumidos"""
        try:
            logging.info(f"Screening: Analisando {ticker}")
            
            # Executa análise completa do GEX
            result = self.gamma_service.analyze_gamma_complete(ticker)
            
            if not result.get('success'):
                return None
            
            spot_price = result['spot_price']
            flip_strike = result.get('flip_strike')
            
            # Calcula distância do flip
            if flip_strike and flip_strike != spot_price:
                distance_pct = ((flip_strike - spot_price) / spot_price) * 100
                distance_abs = flip_strike - spot_price
            else:
                distance_pct = 0.0
                distance_abs = 0.0
            
            # Determina regime
            regime = result.get('regime', 'Neutral')
            
            # Extrai dados de qualidade
            data_quality = result.get('data_quality', {})
            
            screening_data = {
                'ticker': ticker.replace('.SA', ''),
                'spot_price': spot_price,
                'flip_strike': flip_strike,
                'distance_abs': distance_abs,
                'distance_pct': distance_pct,
                'regime': regime,
                'net_gex': result.get('gex_levels', {}).get('total_gex', 0),
                'net_gex_descoberto': result.get('gex_levels', {}).get('total_gex_descoberto', 0),
                'market_bias': result.get('gex_levels', {}).get('market_bias', 'NEUTRAL'),
                'expiration': data_quality.get('expiration'),
                'liquidity_category': data_quality.get('liquidity_category'),
                'atm_range_pct': data_quality.get('atm_range_pct'),
                'real_data_count': data_quality.get('real_data_count', 0),
                'options_count': result.get('options_count', 0),
                'timestamp': datetime.now().isoformat(),
                'success': True
            }
            
            logging.info(f"{ticker}: Flip R$ {flip_strike:.2f} ({distance_pct:+.2f}%) - {regime}")
            return screening_data
            
        except Exception as e:
            logging.error(f"Erro ao analisar {ticker}: {e}")
            return {
                'ticker': ticker.replace('.SA', ''),
                'error': str(e),
                'success': False,
                'timestamp': datetime.now().isoformat()
            }
    
    def screen_multiple_tickers(self, tickers_list):
        """Executa screening em paralelo para múltiplos tickers"""
        try:
            logging.info(f"Iniciando screening de {len(tickers_list)} ativos")
            
            results = []
            errors = []
            
            # Execução paralela com ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_ticker = {
                    executor.submit(self.analyze_single_ticker, ticker): ticker 
                    for ticker in tickers_list
                }
                
                for future in as_completed(future_to_ticker):
                    ticker = future_to_ticker[future]
                    try:
                        data = future.result()
                        if data:
                            if data.get('success'):
                                results.append(data)
                            else:
                                errors.append(data)
                    except Exception as e:
                        logging.error(f"Erro no future de {ticker}: {e}")
                        errors.append({
                            'ticker': ticker.replace('.SA', ''),
                            'error': str(e),
                            'success': False
                        })
            
            # Ordena resultados por distância absoluta do flip (mais próximos primeiro)
            results.sort(key=lambda x: abs(x.get('distance_pct', 999)))
            
            # Cria DataFrame para análise
            df_results = pd.DataFrame(results) if results else pd.DataFrame()
            
            # Estatísticas do screening
            summary = self._generate_summary(results)
            
            logging.info(f"Screening concluído: {len(results)} sucessos, {len(errors)} erros")
            
            return {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'total_tickers': len(tickers_list),
                'successful_analysis': len(results),
                'failed_analysis': len(errors),
                'results': results,
                'errors': errors,
                'summary': summary,
                'dataframe': df_results.to_dict('records') if not df_results.empty else []
            }
            
        except Exception as e:
            logging.error(f"Erro no screening múltiplo: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _generate_summary(self, results):
        """Gera estatísticas resumidas do screening"""
        if not results:
            return {}
        
        df = pd.DataFrame(results)
        
        # Contagens por regime
        regime_counts = df['regime'].value_counts().to_dict() if 'regime' in df.columns else {}
        
        # Contagens por bias de mercado
        bias_counts = df['market_bias'].value_counts().to_dict() if 'market_bias' in df.columns else {}
        
        # Contagens por liquidez
        liquidity_counts = df['liquidity_category'].value_counts().to_dict() if 'liquidity_category' in df.columns else {}
        
        # Estatísticas de distância do flip
        distance_stats = {}
        if 'distance_pct' in df.columns:
            distance_stats = {
                'mean': float(df['distance_pct'].mean()),
                'median': float(df['distance_pct'].median()),
                'min': float(df['distance_pct'].min()),
                'max': float(df['distance_pct'].max()),
                'std': float(df['distance_pct'].std())
            }
        
        # Top 5 mais próximos do flip
        top_closest = []
        if 'distance_pct' in df.columns:
            df_sorted = df.copy()
            df_sorted['abs_distance'] = df_sorted['distance_pct'].abs()
            top_closest = df_sorted.nsmallest(5, 'abs_distance')[
                ['ticker', 'spot_price', 'flip_strike', 'distance_pct', 'regime']
            ].to_dict('records')
        
        summary = {
            'regime_distribution': regime_counts,
            'market_bias_distribution': bias_counts,
            'liquidity_distribution': liquidity_counts,
            'distance_statistics': distance_stats,
            'top_5_closest_to_flip': top_closest,
            'total_analyzed': len(results)
        }
        
        return convert_to_json_serializable(summary)