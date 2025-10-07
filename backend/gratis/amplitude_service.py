import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from database import get_db_connection

class AmplitudeService:
    """Serviço para analisar amplitude de variação de ativos"""
    
    @staticmethod
    def get_stock_amplitude_data(ticker, period='1y'):
        """Buscar dados históricos para análise de amplitude"""
        try:
            symbol = ticker if ticker.endswith('.SA') else f"{ticker}.SA"
            stock = yf.Ticker(symbol)
            
            # Buscar dados históricos de 1 ano
            hist = stock.history(period=period)
            if hist.empty:
                return None
            
            # Buscar informações da empresa
            info = stock.info
            
            return {
                'ticker': ticker,
                'company_name': info.get('longName', ticker),
                'sector': info.get('sector', 'N/A'),
                'history': hist,
                'current_price': float(hist['Close'].iloc[-1]),
                'info': info
            }
        except Exception as e:
            print(f"Erro ao buscar dados de {ticker}: {e}")
            return None
    
    @staticmethod
    def calculate_daily_amplitude(df):
        """Calcular amplitude diária (máxima - mínima) / abertura"""
        df['Daily_Amplitude'] = ((df['High'] - df['Low']) / df['Open'] * 100)
        df['Daily_Variation'] = ((df['Close'] - df['Open']) / df['Open'] * 100)
        return df
    
    @staticmethod
    def analyze_amplitude_patterns(ticker):
        """Análise completa de amplitude para um ativo"""
        
        # Buscar dados
        stock_data = AmplitudeService.get_stock_amplitude_data(ticker)
        if not stock_data:
            return None
        
        df = stock_data['history'].copy()
        df = AmplitudeService.calculate_daily_amplitude(df)
        
        # ===== ANÁLISE DIÁRIA (últimos 252 dias úteis = 1 ano) =====
        daily_analysis = AmplitudeService._analyze_daily_patterns(df)
        
        # ===== ANÁLISE POR PERÍODOS (2, 3, 4, 5, 12, 30 pregões) =====
        periods_analysis = {}
        for period in [2, 3, 4, 5, 12, 30]:
            periods_analysis[f'{period}_days'] = AmplitudeService._analyze_period_patterns(df, period)
        
        return {
            'ticker': ticker,
            'company_name': stock_data['company_name'],
            'sector': stock_data['sector'],
            'current_price': stock_data['current_price'],
            'analysis_date': datetime.now().strftime('%d/%m/%Y'),
            'daily_analysis': daily_analysis,
            'periods_analysis': periods_analysis,
            'summary': AmplitudeService._create_summary(daily_analysis, periods_analysis)
        }
    
    @staticmethod
    def _analyze_daily_patterns(df):
        """Analisar padrões de amplitude diária"""
        
        # Pegar apenas últimos 252 dias úteis (1 ano)
        df_analysis = df.tail(252).copy()
        
        # Definir faixas de amplitude
        amplitude_ranges = {
            'menos_1': {'min': 0, 'max': 1, 'label': 'Menos de 1%'},
            'entre_1_2': {'min': 1, 'max': 2, 'label': 'Entre 1% e 2%'},
            'entre_2_4': {'min': 2, 'max': 4, 'label': 'Entre 2% e 4%'},
            'entre_4_6': {'min': 4, 'max': 6, 'label': 'Entre 4% e 6%'},
            'entre_6_10': {'min': 6, 'max': 10, 'label': 'Entre 6% e 10%'},
            'mais_10': {'min': 10, 'max': 100, 'label': 'Mais de 10%'}
        }
        
        # Definir faixas de variação (fechamento vs abertura)
        variation_ranges = {
            'muito_negativo': {'min': -100, 'max': -4, 'label': 'Muito Negativo (< -4%)'},
            'negativo': {'min': -4, 'max': -2, 'label': 'Negativo (-4% a -2%)'},
            'pouco_negativo': {'min': -2, 'max': -1, 'label': 'Pouco Negativo (-2% a -1%)'},
            'neutro': {'min': -1, 'max': 1, 'label': 'Neutro (-1% a +1%)'},
            'pouco_positivo': {'min': 1, 'max': 2, 'label': 'Pouco Positivo (+1% a +2%)'},
            'positivo': {'min': 2, 'max': 4, 'label': 'Positivo (+2% a +4%)'},
            'muito_positivo': {'min': 4, 'max': 100, 'label': 'Muito Positivo (> +4%)'}
        }
        
        total_days = len(df_analysis)
        
        # Calcular distribuição de amplitude
        amplitude_distribution = {}
        for key, range_data in amplitude_ranges.items():
            count = len(df_analysis[
                (df_analysis['Daily_Amplitude'] >= range_data['min']) & 
                (df_analysis['Daily_Amplitude'] < range_data['max'])
            ])
            amplitude_distribution[key] = {
                'label': range_data['label'],
                'count': count,
                'percentage': round(count / total_days * 100, 1)
            }
        
        # Calcular distribuição de variação
        variation_distribution = {}
        for key, range_data in variation_ranges.items():
            count = len(df_analysis[
                (df_analysis['Daily_Variation'] >= range_data['min']) & 
                (df_analysis['Daily_Variation'] < range_data['max'])
            ])
            variation_distribution[key] = {
                'label': range_data['label'],
                'count': count,
                'percentage': round(count / total_days * 100, 1)
            }
        
        # Estatísticas gerais
        stats = {
            'avg_amplitude': round(df_analysis['Daily_Amplitude'].mean(), 2),
            'max_amplitude': round(df_analysis['Daily_Amplitude'].max(), 2),
            'min_amplitude': round(df_analysis['Daily_Amplitude'].min(), 2),
            'avg_variation': round(df_analysis['Daily_Variation'].mean(), 2),
            'volatility': round(df_analysis['Daily_Variation'].std(), 2),
            'total_days_analyzed': total_days
        }
        
        return {
            'amplitude_distribution': amplitude_distribution,
            'variation_distribution': variation_distribution,
            'statistics': stats
        }
    
    @staticmethod
    def _analyze_period_patterns(df, period_days):
        """Analisar padrões para períodos específicos (2, 3, 4, 5, 12, 30 dias)"""
        
        # Calcular variação acumulada para o período
        df_periods = df.copy()
        df_periods[f'Period_{period_days}_Variation'] = (
            (df_periods['Close'] - df_periods['Close'].shift(period_days)) / 
            df_periods['Close'].shift(period_days) * 100
        ).dropna()
        
        # Pegar apenas últimos 252 dias para ter base consistente
        df_analysis = df_periods.tail(252).dropna()
        
        if len(df_analysis) == 0:
            return None
        
        period_variations = df_analysis[f'Period_{period_days}_Variation'].dropna()
        
        if len(period_variations) == 0:
            return None
        
        # Definir faixas para períodos
        variation_ranges = {
            'muito_negativo': {'min': -100, 'max': -10, 'label': 'Muito Negativo (< -10%)'},
            'negativo': {'min': -10, 'max': -5, 'label': 'Negativo (-10% a -5%)'},
            'pouco_negativo': {'min': -5, 'max': -2, 'label': 'Pouco Negativo (-5% a -2%)'},
            'neutro': {'min': -2, 'max': 2, 'label': 'Neutro (-2% a +2%)'},
            'pouco_positivo': {'min': 2, 'max': 5, 'label': 'Pouco Positivo (+2% a +5%)'},
            'positivo': {'min': 5, 'max': 10, 'label': 'Positivo (+5% a +10%)'},
            'muito_positivo': {'min': 10, 'max': 100, 'label': 'Muito Positivo (> +10%)'}
        }
        
        total_periods = len(period_variations)
        
        # Calcular distribuição
        distribution = {}
        for key, range_data in variation_ranges.items():
            count = len(period_variations[
                (period_variations >= range_data['min']) & 
                (period_variations < range_data['max'])
            ])
            distribution[key] = {
                'label': range_data['label'],
                'count': count,
                'percentage': round(count / total_periods * 100, 1) if total_periods > 0 else 0
            }
        
        # Estatísticas
        stats = {
            'avg_variation': round(period_variations.mean(), 2),
            'max_variation': round(period_variations.max(), 2),
            'min_variation': round(period_variations.min(), 2),
            'volatility': round(period_variations.std(), 2),
            'total_periods_analyzed': total_periods,
            'positive_periods': len(period_variations[period_variations > 0]),
            'negative_periods': len(period_variations[period_variations < 0]),
            'success_rate': round(len(period_variations[period_variations > 0]) / total_periods * 100, 1) if total_periods > 0 else 0
        }
        
        return {
            'period_days': period_days,
            'distribution': distribution,
            'statistics': stats
        }
    
    @staticmethod
    def _create_summary(daily_analysis, periods_analysis):
        """Criar resumo executivo da análise"""
        
        # Classificar volatilidade baseada na amplitude média diária
        avg_amplitude = daily_analysis['statistics']['avg_amplitude']
        
        if avg_amplitude < 2:
            volatility_level = 'BAIXA'
            volatility_desc = 'Ativo de baixa volatilidade, oscila pouco no dia'
        elif avg_amplitude < 4:
            volatility_level = 'MÉDIA'
            volatility_desc = 'Ativo de volatilidade moderada'
        elif avg_amplitude < 6:
            volatility_level = 'ALTA'
            volatility_desc = 'Ativo de alta volatilidade, oscila bastante'
        else:
            volatility_level = 'MUITO ALTA'
            volatility_desc = 'Ativo de volatilidade extrema, risco elevado'
        
        # Tendência geral
        avg_variation = daily_analysis['statistics']['avg_variation']
        if avg_variation > 0.1:
            trend = 'ALTA'
        elif avg_variation < -0.1:
            trend = 'BAIXA'
        else:
            trend = 'LATERAL'
        
        # Melhor período
        best_period = None
        best_success_rate = 0
        
        for period_key, period_data in periods_analysis.items():
            if period_data and period_data['statistics']['success_rate'] > best_success_rate:
                best_success_rate = period_data['statistics']['success_rate']
                best_period = period_data['period_days']
        
        return {
            'volatility_level': volatility_level,
            'volatility_description': volatility_desc,
            'trend': trend,
            'avg_daily_amplitude': avg_amplitude,
            'avg_daily_variation': avg_variation,
            'best_period_days': best_period,
            'best_period_success_rate': best_success_rate,
            'recommendation': AmplitudeService._generate_recommendation(volatility_level, trend, best_period)
        }
    
    @staticmethod
    def _generate_recommendation(volatility_level, trend, best_period):
        """Gerar recomendação baseada na análise"""
        
        recommendations = []
        
        # Recomendação por volatilidade
        if volatility_level == 'BAIXA':
            recommendations.append("Ativo adequado para investidores conservadores")
        elif volatility_level == 'MÉDIA':
            recommendations.append("Ativo equilibrado para perfil moderado")
        elif volatility_level == 'ALTA':
            recommendations.append("Ativo para investidores que toleram risco")
        else:
            recommendations.append("Ativo de alto risco, apenas para experientes")
        
        # Recomendação por tendência
        if trend == 'ALTA':
            recommendations.append("Tendência de alta no período analisado")
        elif trend == 'BAIXA':
            recommendations.append("Tendência de baixa no período analisado")
        else:
            recommendations.append("Movimento lateral, sem tendência definida")
        
        # Recomendação por melhor período
        if best_period:
            recommendations.append(f"Melhor janela de operação: {best_period} dias")
        
        return recommendations
    
    @staticmethod
    def get_multiple_stocks_analysis(tickers_list):
        """Analisar múltiplos ativos para comparação"""
        
        results = []
        
        for ticker in tickers_list:
            try:
                print(f"🔄 Analisando {ticker}...")  # Debug
                analysis = AmplitudeService.analyze_amplitude_patterns(ticker)
                if analysis:
                    results.append({
                        'ticker': ticker,
                        'company_name': analysis['company_name'],
                        'avg_amplitude': analysis['daily_analysis']['statistics']['avg_amplitude'],
                        'volatility_level': analysis['summary']['volatility_level'],
                        'trend': analysis['summary']['trend'],
                        'success_rate_best_period': analysis['summary']['best_period_success_rate'],
                        'analysis_date': analysis['analysis_date']  #  ADICIONAR ESTE CAMPO
                    })
                    print(f" {ticker} analisado com sucesso")  # Debug
                else:
                    print(f" Falha ao analisar {ticker}")  # Debug
            except Exception as e:
                print(f" Erro ao analisar {ticker}: {e}")  # Debug mais detalhado
                continue
        
        # Ordenar por volatilidade (amplitude média)
        results.sort(key=lambda x: x['avg_amplitude'])
        
        print(f" Total de ativos analisados: {len(results)}")  # Debug final
        
        return results
    
    @staticmethod
    def save_analysis_cache(ticker, analysis_data):
        """Salvar análise em cache para não recalcular sempre"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            
            # Verificar se já existe
            cursor.execute("""
                SELECT id FROM amplitude_cache 
                WHERE ticker = %s AND DATE(created_at) = CURRENT_DATE
            """, (ticker,))
            
            if cursor.fetchone():
                # Atualizar
                cursor.execute("""
                    UPDATE amplitude_cache 
                    SET analysis_data = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE ticker = %s AND DATE(created_at) = CURRENT_DATE
                """, (str(analysis_data), ticker))
            else:
                # Inserir novo
                cursor.execute("""
                    INSERT INTO amplitude_cache (ticker, analysis_data, created_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                """, (ticker, str(analysis_data)))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Erro ao salvar cache: {e}")
            return False

# Função para criar tabela de cache
def create_amplitude_cache_table():
    """Criar tabela para cache de análises"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS amplitude_cache (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                analysis_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_amplitude_ticker_date 
            ON amplitude_cache(ticker, created_at);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(" Tabela amplitude_cache criada com sucesso!")
        return True
        
    except Exception as e:
        print(f" Erro ao criar tabela: {e}")
        return False