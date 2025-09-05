import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
from database import get_db_connection

logger = logging.getLogger(__name__)

class ChartAtivosService:
    """Serviço para análise de carteiras com auto-atualização de preços"""
    
    def __init__(self):
        self.colors = {
            'primary': '#3B82F6',
            'success': '#10B981', 
            'danger': '#EF4444',
            'warning': '#F59E0B',
            'info': '#06B6D4'
        }

    def update_portfolio_prices(self, portfolio_name: str, force_update: bool = False) -> Dict:
        """
        Atualiza preços dos ativos da carteira no banco de dados
        """
        try:
            logger.info(f"💰 Atualizando preços da carteira: {portfolio_name}")
            
            conn = get_db_connection()
            if not conn:
                raise Exception("Erro de conexão com banco")
                
            cursor = conn.cursor()
            
            # Buscar ativos da carteira
            cursor.execute("""
                SELECT ticker, current_price, updated_at
                FROM portfolio_assets 
                WHERE portfolio_name = %s AND is_active = true
            """, (portfolio_name,))
            
            assets = cursor.fetchall()
            if not assets:
                cursor.close()
                conn.close()
                return {'success': False, 'error': 'Carteira sem ativos'}
            
            # Verificar se precisa atualizar (última atualização > 5 minutos)
            needs_update = force_update
            if not force_update:
                for asset in assets:
                    if asset[2]:  # updated_at
                        time_diff = datetime.now() - asset[2]
                        if time_diff.total_seconds() > 300:  # 5 minutos
                            needs_update = True
                            break
                    else:
                        needs_update = True
                        break
            
            if not needs_update:
                logger.info("⏰ Preços ainda atuais (< 5 min)")
                cursor.close()
                conn.close()
                return {'success': True, 'message': 'Preços atuais', 'updated': False}
            
            # Buscar novos preços
            tickers = [asset[0] for asset in assets]
            logger.info(f"🔄 Buscando preços atualizados para: {tickers}")
            
            new_prices = self.fetch_current_prices(tickers)
            
            if not new_prices:
                logger.warning("⚠️ Nenhum preço obtido da API")
                cursor.close()
                conn.close()
                return {'success': False, 'error': 'Falha ao obter preços'}
            
            # Atualizar preços no banco
            updated_count = 0
            for ticker, new_price in new_prices.items():
                cursor.execute("""
                    UPDATE portfolio_assets 
                    SET current_price = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE portfolio_name = %s AND ticker = %s
                """, (new_price, portfolio_name, ticker))
                
                if cursor.rowcount > 0:
                    updated_count += 1
                    logger.info(f"✅ {ticker}: R$ {new_price}")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"💾 {updated_count} preços atualizados no banco")
            
            return {
                'success': True,
                'message': f'{updated_count} preços atualizados',
                'updated': True,
                'updated_count': updated_count,
                'prices': new_prices
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar preços: {str(e)}")
            return {'success': False, 'error': str(e)}

    def fetch_current_prices(self, tickers: List[str]) -> Dict[str, float]:
        """Busca preços atuais do Yahoo Finance"""
        try:
            logger.info(f"📡 Buscando preços via API para {len(tickers)} ativos")
            
            prices = {}
            
            # Normalizar tickers
            normalized_tickers = []
            for ticker in tickers:
                if not ticker.endswith('.SA'):
                    normalized_tickers.append(ticker + '.SA')
                else:
                    normalized_tickers.append(ticker)
            
            # Buscar em lote primeiro
            try:
                data = yf.download(
                    tickers=normalized_tickers,
                    period='1d',
                    progress=False,
                    group_by='ticker',
                    auto_adjust=True,
                    threads=True
                )
                
                if not data.empty:
                    # Se múltiplos tickers
                    if len(normalized_tickers) > 1 and isinstance(data.columns, pd.MultiIndex):
                        for i, ticker in enumerate(tickers):
                            norm_ticker = normalized_tickers[i]
                            try:
                                if norm_ticker in data.columns.get_level_values(0):
                                    close_data = data[norm_ticker]['Close']
                                    if not close_data.empty and not pd.isna(close_data.iloc[-1]):
                                        prices[ticker] = round(float(close_data.iloc[-1]), 2)
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao processar {ticker}: {e}")
                    else:
                        # Apenas um ticker
                        if 'Close' in data.columns and not data['Close'].empty:
                            ticker_clean = tickers[0]
                            prices[ticker_clean] = round(float(data['Close'].iloc[-1]), 2)
                
                # Busca individual para tickers que falharam
                missing_tickers = [t for t in tickers if t not in prices]
                if missing_tickers:
                    logger.info(f"🔄 Busca individual para {len(missing_tickers)} ativos")
                    for ticker in missing_tickers:
                        try:
                            individual_price = self.fetch_single_price(ticker)
                            if individual_price:
                                prices[ticker] = individual_price
                        except:
                            continue
                            
            except Exception as e:
                logger.error(f"❌ Erro na busca em lote: {e}")
                
                # Fallback total para busca individual
                for ticker in tickers:
                    try:
                        price = self.fetch_single_price(ticker)
                        if price:
                            prices[ticker] = price
                    except:
                        continue
            
            logger.info(f"✅ {len(prices)}/{len(tickers)} preços obtidos")
            return prices
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar preços: {str(e)}")
            return {}

    def fetch_single_price(self, ticker: str) -> Optional[float]:
        """Busca preço individual"""
        try:
            norm_ticker = ticker if ticker.endswith('.SA') else ticker + '.SA'
            
            stock = yf.Ticker(norm_ticker)
            hist = stock.history(period='1d')
            
            if not hist.empty and 'Close' in hist.columns:
                return round(float(hist['Close'].iloc[-1]), 2)
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Erro individual {ticker}: {e}")
            return None

    def get_portfolio_data_from_db(self, portfolio_name: str) -> Dict:
        """Busca dados atualizados da carteira do banco"""
        try:
            conn = get_db_connection()
            if not conn:
                return None
                
            cursor = conn.cursor()
            
            # Buscar dados da carteira
            cursor.execute("""
                SELECT p.display_name
                FROM portfolios p
                WHERE p.name = %s AND p.is_active = true
            """, (portfolio_name,))
            
            portfolio_info = cursor.fetchone()
            if not portfolio_info:
                cursor.close()
                conn.close()
                return None

            # Buscar ativos
            cursor.execute("""
                SELECT 
                    ticker,
                    weight,
                    sector,
                    entry_price,
                    current_price,
                    target_price,
                    entry_date,
                    updated_at
                FROM portfolio_assets
                WHERE portfolio_name = %s AND is_active = true
                ORDER BY weight DESC
            """, (portfolio_name,))
            
            assets_data = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if not assets_data:
                return None

            # Organizar dados
            assets = []
            for row in assets_data:
                asset = {
                    'ticker': row[0],
                    'weight': float(row[1]) if row[1] else 0.0,
                    'sector': row[2] or 'N/A',
                    'entry_price': float(row[3]) if row[3] else 0.0,
                    'current_price': float(row[4]) if row[4] else 0.0,
                    'target_price': float(row[5]) if row[5] else 0.0,
                    'entry_date': row[6],
                    'updated_at': row[7],
                    'company_name': ''
                }
                assets.append(asset)
            
            return {
                'name': portfolio_info[0],
                'assets': assets
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar dados: {str(e)}")
            return None

    def calculate_portfolio_metrics(self, assets: List[Dict]) -> Dict:
        """Calcula métricas da carteira"""
        try:
            logger.info(" Calculando métricas da carteira")
            
            if not assets:
                return {'error': 'Portfolio sem ativos', 'total_return': 0.0}
            
            total_return = 0.0
            assets_performance = {}
            last_update = None
            
            for asset in assets:
                ticker = asset['ticker']
                weight = asset['weight'] / 100.0
                entry_price = asset['entry_price']
                current_price = asset['current_price']
                updated_at = asset.get('updated_at')
                
                if updated_at and (not last_update or updated_at > last_update):
                    last_update = updated_at
                
                if current_price and entry_price and entry_price > 0:
                    asset_return = ((current_price - entry_price) / entry_price) * 100
                    weighted_return = asset_return * weight
                    
                    assets_performance[ticker] = {
                        'return': round(asset_return, 2),
                        'weighted_return': round(weighted_return, 2),
                        'weight': round(weight * 100, 1),
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'profit_loss': round(current_price - entry_price, 2),
                        'sector': asset.get('sector', 'N/A'),
                        'updated_at': updated_at.isoformat() if updated_at else None
                    }
                    
                    total_return += weighted_return
            
            result = {
                'total_return': round(total_return, 2),
                'assets_performance': assets_performance,
                'number_of_assets': len(assets_performance),
                'calculation_date': datetime.now().isoformat(),
                'last_price_update': last_update.isoformat() if last_update else None,
                'needs_refresh': self.check_needs_refresh(last_update)
            }
            
            logger.info(f"✅ Métricas calculadas - Retorno: {total_return:.2f}%")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro no cálculo: {str(e)}")
            return {'error': str(e), 'total_return': 0.0}

    def check_needs_refresh(self, last_update: datetime) -> bool:
        """Verifica se precisa atualizar preços"""
        if not last_update:
            return True
        
        time_diff = datetime.now() - last_update
        return time_diff.total_seconds() > 300  # 5 minutos

    def analyze_portfolio(self, portfolio_name: str, force_refresh: bool = False) -> Dict:
        """
        Análise completa da carteira com auto-atualização
        """
        try:
            logger.info(f"🚀 Iniciando análise da carteira: {portfolio_name}")
            
            # ETAPA 1: Atualizar preços automaticamente
            update_result = self.update_portfolio_prices(portfolio_name, force_refresh)
            
            if not update_result['success'] and 'sem ativos' in update_result.get('error', '').lower():
                return {
                    'success': False,
                    'error': 'Carteira não encontrada ou sem ativos',
                    'portfolio_name': portfolio_name
                }
            
            # ETAPA 2: Buscar dados atualizados do banco
            portfolio_data = self.get_portfolio_data_from_db(portfolio_name)
            
            if not portfolio_data:
                return {
                    'success': False,
                    'error': 'Erro ao carregar dados da carteira',
                    'portfolio_name': portfolio_name
                }

            assets = portfolio_data['assets']
            portfolio_display_name = portfolio_data['name']
            
            logger.info(f"✅ Carteira carregada: {portfolio_display_name}")
            logger.info(f" {len(assets)} ativos encontrados")
            
            # ETAPA 3: Calcular métricas
            metrics = self.calculate_portfolio_metrics(assets)
            
            # ETAPA 4: Preparar resultado
            result = {
                'success': True,
                'portfolio_name': portfolio_display_name,
                'portfolio_id': portfolio_name,
                'analysis_date': datetime.now().isoformat(),
                'metrics': metrics,
                'assets_count': len(assets),
                'update_info': {
                    'prices_updated': update_result.get('updated', False),
                    'update_message': update_result.get('message', ''),
                    'needs_refresh': metrics.get('needs_refresh', False),
                    'last_update': metrics.get('last_price_update')
                }
            }
            
            logger.info(f"✅ Análise concluída para {portfolio_display_name}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro na análise: {str(e)}")
            
            return {
                'success': False,
                'error': str(e),
                'portfolio_name': portfolio_name,
                'analysis_date': datetime.now().isoformat()
            }