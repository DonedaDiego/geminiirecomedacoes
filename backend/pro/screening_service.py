"""
screening_service.py - Screening de Gamma Flip COM CACHE
"""

import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from .gamma_service import GammaService, convert_to_json_serializable
from database import get_screening_cache, save_screening_cache, get_cache_status

logging.basicConfig(level=logging.INFO)

# Lista oficial de tickers com opções
OFFICIAL_TICKERS = [
    'PETR4', 'VALE3', 'ITUB4', 'BBAS3', 'PRIO3', 'ABEV3', 'BBDC4', 'B3SA3',
    'AXIA3', 'PETR3', 'ITSA4', 'SBSP3', 'SUZB3', 'WEGE3', 'EMBJ3',
    'GGBR4', 'ENEV3', 'EQTL3', 'RENT3', 'VBBR3', 'RADL3', 'CSMG3',
    'RDOR3', 'BBSE3', 'CPLE3', 'LREN3', 'VIVT3', 'MGLU3', 'RAIL3',
    'CYRE3', 'TIMS3', 'COGN3', 'CPFE3', 'MBRF3', 'CSAN3', 'UGPA3',
    'CURY3', 'CMIG4', 'CEAB3', 'MOTV3', 'VIVA3', 'ALOS3', 'BRAV3', 
    'SMFT3', 'TOTS3', 'HAPV3', 'BBDC3', 'CSNA3', 'ASAI3', 'MULT3', 'USIM5',
    'POMO4', 'AURE3', 'CXSE3', 'GOAU4', 'AXIA6', 'BEEF3', 'PSSA3',
    'IRBR3', 'MRVE3', 'VAMO3', 'AZZA3', 'DIRR3', 'EGIE3', 'NATU3', 'ISAE4',
    'BRAP4', 'YDUQ3', 'PCAR3', 'BRKM5', 'HYPE3', 'RECV3', 'CMIN3',
    'FLRY3', 'SLCE3', 'RAIZ4', 'CYRE4'
]


class ScreeningService:
    def __init__(self):
        self.gamma_service = GammaService()
        self.max_workers = 5
        self.cache_max_age_hours = 24
    
    def analyze_single_ticker(self, ticker, use_cache=True):
        """Analisa um único ticker com suporte a cache"""
        try:
            # Tentar buscar do cache primeiro
            if use_cache:
                cached_data = get_screening_cache(ticker, self.cache_max_age_hours)
                if cached_data:
                    # ✅ NOVO: Se tem erro no cache E não passou 7 dias, pula
                    if not cached_data.get('success'):
                        logging.info(f"{ticker}: Pulando (erro em cache)")
                        return cached_data  # Retorna o erro do cache
                    
                    logging.info(f"{ticker}: Usando dados do cache")
                    return cached_data
            
            logging.info(f"Screening: Analisando {ticker} (nova consulta)")
            
            # Executa análise completa do GEX
            result = self.gamma_service.analyze_gamma_complete(ticker)
            
            if not result.get('success'):
                # ✅ CORREÇÃO: Salvar erro no cache com TTL mais longo
                error_data = {
                    'ticker': ticker.replace('.SA', ''),
                    'error': result.get('error', 'Sem dados disponíveis'),
                    'success': False,
                    'timestamp': datetime.now().isoformat()
                }
                save_screening_cache(ticker, error_data)
                logging.warning(f"{ticker}: Erro salvo no cache - {error_data['error']}")
                return error_data
            
            # ... resto do código continua igual ...
            
        except Exception as e:
            logging.error(f"Erro ao analisar {ticker}: {e}")
            
            error_data = {
                'ticker': ticker.replace('.SA', ''),
                'error': str(e),
                'success': False,
                'timestamp': datetime.now().isoformat()
            }
            
            # ✅ SALVAR ERRO NO CACHE
            save_screening_cache(ticker, error_data)
            
            return error_data
    
    def screen_multiple_tickers(self, tickers_list=None, use_cache=True, force_refresh=False):
        """
        Executa screening INTELIGENTE ticker por ticker
        """
        try:
            # ✅ CORREÇÃO: Se não forneceu lista, USA OFFICIAL_TICKERS
            if tickers_list is None or len(tickers_list) == 0:
                tickers_list = OFFICIAL_TICKERS
                logging.info(f"Usando lista oficial com {len(tickers_list)} tickers")
            
            # Se force_refresh, ignora cache
            if force_refresh:
                use_cache = False
                logging.info("Force refresh ativado - ignorando cache")
            
            results = []
            errors = []
            tickers_to_analyze = []
            
            # FASE 1: VERIFICAR CACHE TICKER POR TICKER
            if use_cache and not force_refresh:
                logging.info("Verificando cache para cada ticker...")
                
                for ticker in tickers_list:
                    cached_data = get_screening_cache(ticker, self.cache_max_age_hours)
                    
                    if cached_data:
                        logging.info(f"{ticker}: Usando cache")
                        results.append(cached_data)
                    else:
                        logging.info(f"{ticker}: Precisa analisar")
                        tickers_to_analyze.append(ticker)
                
                logging.info(f"Cache: {len(results)} hits, {len(tickers_to_analyze)} misses")
            else:
                tickers_to_analyze = tickers_list
            
            # FASE 2: ANALISAR APENAS OS QUE FALTAM
            if tickers_to_analyze:
                logging.info(f"Iniciando análise de {len(tickers_to_analyze)} ativos")
                
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_ticker = {
                        executor.submit(self.analyze_single_ticker, ticker, False): ticker 
                        for ticker in tickers_to_analyze
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
            
            # Ordena resultados por distância absoluta do flip
            results.sort(key=lambda x: abs(x.get('distance_pct') or 999))
            
            # Estatísticas do screening
            summary = self._generate_summary(results)
            
            from_cache = len(tickers_to_analyze) == 0
            
            logging.info(f"✓ Screening concluído: {len(results)} sucessos, {len(errors)} erros")
            
            return {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'total_tickers': len(tickers_list),
                'successful_analysis': len(results),
                'failed_analysis': len(errors),
                'results': results,
                'errors': errors,
                'summary': summary,
                'dataframe': results,
                'from_cache': from_cache,
                'cache_hits': len(results) - len(tickers_to_analyze),
                'new_analysis': len(tickers_to_analyze),
                'cache_status': get_cache_status()
            }
            
        except Exception as e:
            logging.error(f"Erro no screening múltiplo: {e}")
            import traceback
            traceback.print_exc()
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