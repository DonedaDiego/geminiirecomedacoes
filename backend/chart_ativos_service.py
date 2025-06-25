# chart_ativos_service.py
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChartAtivosService:
    """
    Serviço para análise de performance de carteiras usando dados do Yahoo Finance
    """
    
    def __init__(self):
        self.benchmark_ticker = '^BVSP'  # IBOVESPA
        self.trading_days_year = 252
        
    def _convert_ticker_to_yahoo(self, ticker: str) -> str:
        """
        Converte ticker brasileiro para formato Yahoo Finance
        """
        if not ticker.endswith('.SA'):
            return f"{ticker}.SA"
        return ticker
    
    def _prepare_portfolio_data(self, assets: List) -> Tuple[List[str], np.ndarray, datetime]:
        """
        Prepara dados da carteira para análise
        
        Args:
            assets: Lista de ativos da carteira com ticker, weight, created_at
            
        Returns:
            tickers: Lista de tickers no formato Yahoo
            weights: Array normalizado de pesos
            creation_date: Data de criação da carteira
        """
        tickers = []
        weights = []
        creation_date = None
        
        for asset in assets:
            # Converter ticker para formato Yahoo Finance
            yahoo_ticker = self._convert_ticker_to_yahoo(asset.ticker)
            tickers.append(yahoo_ticker)
            weights.append(asset.weight / 100.0)  # Converter % para decimal
            
            # Data de criação (menor created_at)
            if creation_date is None or asset.created_at < creation_date:
                creation_date = asset.created_at
        
        # Normalizar pesos para garantir que somem 1
        weights = np.array(weights)
        weights = weights / np.sum(weights)
        
        logger.info(f"📊 Carteira preparada: {len(tickers)} ativos")
        logger.info(f"📅 Data de criação: {creation_date}")
        logger.info(f"📈 Tickers: {tickers}")
        
        return tickers, weights, creation_date
    
    def _fetch_historical_data(self, tickers: List[str], start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Busca dados históricos do Yahoo Finance
        
        Args:
            tickers: Lista de tickers para buscar
            start_date: Data inicial
            end_date: Data final
            
        Returns:
            DataFrame com preços ajustados
        """
        try:
            logger.info(f"🔍 Buscando dados de {start_date.date()} até {end_date.date()}")
            logger.info(f"📊 Tickers: {tickers}")
            
            # Buscar dados
            data = yf.download(
                tickers, 
                start=start_date, 
                end=end_date, 
                progress=False,
                threads=True
            )
            
            if data.empty:
                raise ValueError("Nenhum dado encontrado para o período especificado")
            
            # Usar preços de fechamento ajustados se disponível
            if 'Adj Close' in data.columns:
                prices_df = data['Adj Close']
            else:
                prices_df = data['Close']
            
            # Se só temos um ticker, o pandas retorna Series, converter para DataFrame
            if isinstance(prices_df, pd.Series):
                prices_df = prices_df.to_frame(name=tickers[0])
            
            # Remover linhas com NaN
            prices_df = prices_df.dropna()
            
            logger.info(f"✅ Dados coletados: {len(prices_df)} dias, {len(prices_df.columns)} ativos")
            
            return prices_df
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar dados: {e}")
            raise
    
    def _calculate_portfolio_performance(self, prices_df: pd.DataFrame, portfolio_tickers: List[str], 
                                       weights: np.ndarray) -> Tuple[pd.Series, List[str], np.ndarray]:
        """
        Calcula performance da carteira ponderada
        
        Args:
            prices_df: DataFrame com preços históricos
            portfolio_tickers: Lista de tickers da carteira
            weights: Array de pesos
            
        Returns:
            portfolio_normalized: Série com performance normalizada da carteira
            available_tickers: Lista de tickers com dados disponíveis
            adjusted_weights: Pesos ajustados para tickers disponíveis
        """
        # Filtrar tickers que realmente temos dados
        available_tickers = [t for t in portfolio_tickers if t in prices_df.columns]
        
        if not available_tickers:
            raise ValueError("Nenhum ativo da carteira tem dados disponíveis")
        
        # Ajustar pesos para ativos disponíveis
        available_indices = [i for i, t in enumerate(portfolio_tickers) if t in available_tickers]
        adjusted_weights = weights[available_indices]
        adjusted_weights = adjusted_weights / np.sum(adjusted_weights)  # Renormalizar
        
        # Normalizar preços (base = primeiro dia)
        normalized_prices = prices_df / prices_df.iloc[0]
        
        # Calcular performance da carteira ponderada
        portfolio_normalized = (normalized_prices[available_tickers] * adjusted_weights).sum(axis=1)
        
        logger.info(f"📊 Carteira calculada: {len(available_tickers)}/{len(portfolio_tickers)} ativos")
        logger.info(f"⚖️ Pesos ajustados: {adjusted_weights}")
        
        return portfolio_normalized, available_tickers, adjusted_weights
    
    def _calculate_metrics(self, portfolio_returns: pd.Series, benchmark_returns: pd.Series = None) -> Dict:
        """
        Calcula métricas de performance
        
        Args:
            portfolio_returns: Retornos diários da carteira
            benchmark_returns: Retornos diários do benchmark (opcional)
            
        Returns:
            Dicionário com métricas calculadas
        """
        metrics = {}
        
        # Métricas da carteira
        total_return = (portfolio_returns.iloc[-1] - 1) * 100  # Já normalizado
        volatility = portfolio_returns.pct_change().dropna().std() * np.sqrt(self.trading_days_year) * 100
        
        # Sharpe Ratio (assumindo rf = 0)
        daily_returns = portfolio_returns.pct_change().dropna()
        sharpe = (daily_returns.mean() * self.trading_days_year) / (daily_returns.std() * np.sqrt(self.trading_days_year))
        
        # Drawdown
        cumulative = portfolio_returns
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak * 100
        max_drawdown = drawdown.min()
        
        metrics.update({
            'total_return_portfolio': round(total_return, 2),
            'volatility_portfolio': round(volatility, 2),
            'sharpe_portfolio': round(sharpe, 2),
            'max_drawdown_portfolio': round(max_drawdown, 2)
        })
        
        # Métricas do benchmark (se disponível)
        if benchmark_returns is not None and len(benchmark_returns) > 1:
            benchmark_total_return = (benchmark_returns.iloc[-1] - 1) * 100
            benchmark_volatility = benchmark_returns.pct_change().dropna().std() * np.sqrt(self.trading_days_year) * 100
            
            benchmark_daily_returns = benchmark_returns.pct_change().dropna()
            benchmark_sharpe = (benchmark_daily_returns.mean() * self.trading_days_year) / (benchmark_daily_returns.std() * np.sqrt(self.trading_days_year))
            
            benchmark_cumulative = benchmark_returns
            benchmark_peak = benchmark_cumulative.cummax()
            benchmark_drawdown = (benchmark_cumulative - benchmark_peak) / benchmark_peak * 100
            benchmark_max_drawdown = benchmark_drawdown.min()
            
            # Beta
            if len(daily_returns) == len(benchmark_daily_returns):
                covariance = np.cov(daily_returns, benchmark_daily_returns)[0][1]
                benchmark_variance = np.var(benchmark_daily_returns)
                beta = covariance / benchmark_variance if benchmark_variance != 0 else 0
            else:
                beta = 0
            
            metrics.update({
                'total_return_benchmark': round(benchmark_total_return, 2),
                'volatility_benchmark': round(benchmark_volatility, 2),
                'sharpe_benchmark': round(benchmark_sharpe, 2),
                'max_drawdown_benchmark': round(benchmark_max_drawdown, 2),
                'beta_portfolio': round(beta, 2)
            })
        else:
            # Valores padrão se não temos benchmark
            metrics.update({
                'total_return_benchmark': 0,
                'volatility_benchmark': 0,
                'sharpe_benchmark': 0,
                'max_drawdown_benchmark': 0,
                'beta_portfolio': 0
            })
        
        return metrics
    
    def analyze_portfolio(self, assets: List, portfolio_name: str) -> Dict:
        """
        Função principal para análise de carteira
        
        Args:
            assets: Lista de ativos da carteira
            portfolio_name: Nome da carteira
            
        Returns:
            Dicionário com análise completa
        """
        try:
            logger.info(f"🚀 Iniciando análise da carteira: {portfolio_name}")
            
            # 1. Preparar dados da carteira
            portfolio_tickers, weights, creation_date = self._prepare_portfolio_data(assets)
            
            # 2. Definir período de análise
            end_date = datetime.now()
            start_date = creation_date or (end_date - timedelta(days=365))
            
            # Garantir que temos pelo menos 30 dias de dados
            if (end_date - start_date).days < 30:
                start_date = end_date - timedelta(days=90)
            
            # 3. Buscar dados históricos (carteira + benchmark)
            all_tickers = portfolio_tickers + [self.benchmark_ticker]
            prices_df = self._fetch_historical_data(all_tickers, start_date, end_date)
            
            # 4. Calcular performance da carteira
            portfolio_normalized, available_tickers, adjusted_weights = self._calculate_portfolio_performance(
                prices_df, portfolio_tickers, weights
            )
            
            # 5. Performance do benchmark
            benchmark_normalized = None
            if self.benchmark_ticker in prices_df.columns:
                benchmark_normalized = prices_df[self.benchmark_ticker] / prices_df[self.benchmark_ticker].iloc[0]
            
            # 6. Calcular métricas
            metrics = self._calculate_metrics(portfolio_normalized, benchmark_normalized)
            
            # 7. Preparar dados para gráficos (últimos 30 pontos)
            chart_length = min(30, len(portfolio_normalized))
            recent_portfolio = portfolio_normalized.tail(chart_length)
            recent_benchmark = benchmark_normalized.tail(chart_length) if benchmark_normalized is not None else []
            
            # 8. Calcular drawdown para gráfico
            portfolio_cumulative = portfolio_normalized
            portfolio_peak = portfolio_cumulative.cummax()
            portfolio_drawdown = (portfolio_cumulative - portfolio_peak) / portfolio_peak * 100
            
            benchmark_drawdown = []
            if benchmark_normalized is not None:
                benchmark_cumulative = benchmark_normalized
                benchmark_peak = benchmark_cumulative.cummax()
                benchmark_drawdown = (benchmark_cumulative - benchmark_peak) / benchmark_peak * 100
            
            # 9. Montar resposta
            result = {
                'portfolio_name': portfolio_name,
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': (end_date - start_date).days
                },
                'assets_analyzed': {
                    'total_assets': len(assets),
                    'assets_with_data': len(available_tickers),
                    'tickers': available_tickers,
                    'weights': adjusted_weights.tolist()
                },
                'performance_metrics': metrics,
                'chart_data': {
                    'dates': recent_portfolio.index.strftime('%Y-%m-%d').tolist(),
                    'portfolio_normalized': recent_portfolio.tolist(),
                    'benchmark_normalized': recent_benchmark.tolist(),
                    'portfolio_drawdown': portfolio_drawdown.tail(chart_length).tolist(),
                    'benchmark_drawdown': benchmark_drawdown.tail(chart_length).tolist() if len(benchmark_drawdown) > 0 else []
                }
            }
            
            logger.info(f"✅ Análise concluída para {portfolio_name}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro na análise da carteira {portfolio_name}: {e}")
            raise
    
    def get_current_prices(self, tickers: List[str]) -> Dict[str, float]:
        """
        Busca preços atuais para uma lista de tickers
        
        Args:
            tickers: Lista de tickers
            
        Returns:
            Dicionário com ticker: preço_atual
        """
        try:
            yahoo_tickers = [self._convert_ticker_to_yahoo(ticker) for ticker in tickers]
            
            # Buscar dados do último dia
            data = yf.download(yahoo_tickers, period="1d", progress=False)
            
            if data.empty:
                return {}
            
            # Extrair preços de fechamento
            if 'Close' in data.columns:
                if len(yahoo_tickers) == 1:
                    return {tickers[0]: float(data['Close'].iloc[-1])}
                else:
                    prices = {}
                    for i, ticker in enumerate(tickers):
                        yahoo_ticker = yahoo_tickers[i]
                        if yahoo_ticker in data['Close'].columns:
                            prices[ticker] = float(data['Close'][yahoo_ticker].iloc[-1])
                    return prices
            
            return {}
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar preços atuais: {e}")
            return {}