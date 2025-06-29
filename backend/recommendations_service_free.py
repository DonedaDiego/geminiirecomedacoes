import yfinance as yf
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
from database import get_db_connection
import json
import random

class RecommendationsServiceFree:
    """Serviço para gerar e gerenciar recomendações mensais gratuitas"""
    
    # Lista de ações populares para análise
    STOCKS_POOL = [
        'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3', 'WEGE3', 'RENT3', 
        'MGLU3', 'B3SA3', 'LREN3', 'GGBR4', 'SUZB3', 'RAIL3', 'USIM5',
        'CSNA3', 'CSAN3', 'VIVT3', 'ELET3', 'CMIG4', 'BBAS3'
    ]
    
    @staticmethod
    def get_stock_data(ticker, period='3mo'):
        """Buscar dados históricos de uma ação"""
        try:
            symbol = ticker if ticker.endswith('.SA') else f"{ticker}.SA"
            stock = yf.Ticker(symbol)
            
            # Buscar dados históricos
            hist = stock.history(period=period)
            if hist.empty:
                return None
            
            # Buscar informações adicionais
            info = stock.info
            
            return {
                'ticker': ticker,
                'company_name': info.get('longName', ticker),
                'history': hist,
                'current_price': float(hist['Close'].iloc[-1]),
                'sector': info.get('sector', 'N/A'),
                'info': info
            }
        except Exception as e:
            print(f"Erro ao buscar dados de {ticker}: {e}")
            return None
    
    @staticmethod
    def calculate_technical_indicators(df):
        """Calcular indicadores técnicos"""
        # SMA
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        # EMA
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        
        # MACD
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['Signal']
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        
        # ATR para Stop Loss
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['ATR'] = true_range.rolling(window=14).mean()
        
        return df
    
    @staticmethod
    def generate_ml_signal(stock_data):
        """Gerar sinal usando lógica de ML simulada"""
        df = stock_data['history'].copy()
        df = RecommendationsServiceFree.calculate_technical_indicators(df)
        
        # Pegar últimos valores
        last_row = df.iloc[-1]
        current_price = float(last_row['Close'])
        
        # Pontuação baseada em múltiplos indicadores
        score = 0
        
        # Tendência de médias móveis
        if current_price > last_row['SMA_20']:
            score += 2
        if current_price > last_row['SMA_50']:
            score += 2
        if last_row['SMA_20'] > last_row['SMA_50']:
            score += 3
        
        # MACD
        if last_row['MACD'] > last_row['Signal']:
            score += 3
        if last_row['MACD_Histogram'] > 0:
            score += 2
        
        # RSI
        if 30 < last_row['RSI'] < 70:
            score += 2
        elif last_row['RSI'] < 30:
            score += 4  # Oversold
        elif last_row['RSI'] > 70:
            score -= 4  # Overbought
        
        # Bollinger Bands
        if current_price < last_row['BB_Lower']:
            score += 3  # Possível reversão
        elif current_price > last_row['BB_Upper']:
            score -= 3  # Possível correção
        
        # Volume
        avg_volume = df['Volume'].rolling(window=20).mean().iloc[-1]
        if last_row['Volume'] > avg_volume * 1.5:
            score += 2  # Alto volume
        
        # Momentum (últimos 5 dias)
        momentum = (current_price - df['Close'].iloc[-5]) / df['Close'].iloc[-5] * 100
        if momentum > 2:
            score += 2
        elif momentum < -2:
            score -= 2
        
        # Decisão final
        action = 'COMPRA' if score >= 8 else 'VENDA' if score <= -3 else None
        confidence = min(abs(score) / 15 * 100, 95)  # Confiança máxima de 95%
        
        # Calcular alvos e stops
        atr = last_row['ATR']
        
        if action == 'COMPRA':
            stop_loss = current_price - (atr * 2)
            target_price = current_price + (atr * 3.5)
        elif action == 'VENDA':
            stop_loss = current_price + (atr * 2)
            target_price = current_price - (atr * 3.5)
        else:
            return None
        
        return {
            'action': action,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'target_price': target_price,
            'confidence': confidence,
            'score': score,
            'risk_reward': 3.5 / 2,  # Sempre 1:1.75
            'technical_data': {
                'rsi': float(last_row['RSI']),
                'macd': float(last_row['MACD']),
                'sma20': float(last_row['SMA_20']),
                'sma50': float(last_row['SMA_50']),
                'volume_ratio': float(last_row['Volume'] / avg_volume)
            }
        }
    
    @staticmethod
    def generate_monthly_recommendations():
        """Gerar recomendações mensais automáticas"""
        recommendations = []
        analyzed_stocks = []
        
        # Embaralhar lista de ações para variedade
        stocks = RecommendationsServiceFree.STOCKS_POOL.copy()
        random.shuffle(stocks)
        
        # Analisar cada ação
        for ticker in stocks:
            stock_data = RecommendationsServiceFree.get_stock_data(ticker)
            if not stock_data:
                continue
            
            signal = RecommendationsServiceFree.generate_ml_signal(stock_data)
            if signal and signal['confidence'] >= 70:  # Apenas sinais com alta confiança
                recommendations.append({
                    'ticker': ticker,
                    'company_name': stock_data['company_name'],
                    'action': signal['action'],
                    'entry_price': signal['entry_price'],
                    'stop_loss': signal['stop_loss'],
                    'target_price': signal['target_price'],
                    'current_price': signal['entry_price'],
                    'confidence': signal['confidence'],
                    'risk_reward': signal['risk_reward'],
                    'technical_data': signal['technical_data']
                })
                
                # Limitar a 4-6 recomendações por mês
                if len(recommendations) >= 5:
                    break
        
        return recommendations
    
    @staticmethod
    def save_recommendations(recommendations):
        """Salvar recomendações no banco de dados"""
        try:
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'error': 'Erro de conexão'}
            
            cursor = conn.cursor()
            saved_count = 0
            
            for rec in recommendations:
                cursor.execute("""
                    INSERT INTO recommendations_free (
                        ticker, company_name, action, entry_price, stop_loss, 
                        target_price, current_price, confidence, risk_reward,
                        technical_data, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    rec['ticker'],
                    rec['company_name'],
                    rec['action'],
                    rec['entry_price'],
                    rec['stop_loss'],
                    rec['target_price'],
                    rec['current_price'],
                    rec['confidence'],
                    rec['risk_reward'],
                    json.dumps(rec['technical_data']),
                    'ATIVA',
                    datetime.now(timezone.utc)
                ))
                saved_count += 1
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return {'success': True, 'saved_count': saved_count}
            
        except Exception as e:
            print(f"Erro ao salvar recomendações: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_active_recommendations():
        """Buscar recomendações ativas"""
        try:
            conn = get_db_connection()
            if not conn:
                return []
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, ticker, company_name, action, entry_price, stop_loss,
                       target_price, current_price, confidence, risk_reward,
                       technical_data, status, created_at, performance
                FROM recommendations_free
                WHERE status = 'ATIVA'
                ORDER BY created_at DESC
            """)
            
            recommendations = []
            for row in cursor.fetchall():
                rec = {
                    'id': row[0],
                    'ticker': row[1],
                    'company_name': row[2],
                    'action': row[3],
                    'entry_price': float(row[4]),
                    'stop_loss': float(row[5]),
                    'target_price': float(row[6]),
                    'current_price': float(row[7]),
                    'confidence': float(row[8]),
                    'risk_reward': float(row[9]),
                    'technical_data': json.loads(row[10]) if row[10] else {},
                    'status': row[11],
                    'created_at': row[12].isoformat() if row[12] else None,
                    'performance': float(row[13]) if row[13] else 0
                }
                
                # Calcular performance atual
                rec['performance'] = ((rec['current_price'] - rec['entry_price']) / rec['entry_price'] * 100)
                if rec['action'] == 'VENDA':
                    rec['performance'] = -rec['performance']
                
                recommendations.append(rec)
            
            cursor.close()
            conn.close()
            
            return recommendations
            
        except Exception as e:
            print(f"Erro ao buscar recomendações: {e}")
            return []
    
    @staticmethod
    def update_current_prices():
        """Atualizar preços atuais das recomendações ativas"""
        try:
            recommendations = RecommendationsServiceFree.get_active_recommendations()
            
            conn = get_db_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            
            for rec in recommendations:
                # Buscar preço atual
                ticker = rec['ticker']
                symbol = ticker if ticker.endswith('.SA') else f"{ticker}.SA"
                
                try:
                    stock = yf.Ticker(symbol)
                    current_price = float(stock.history(period='1d')['Close'].iloc[-1])
                    
                    # Calcular performance
                    performance = ((current_price - rec['entry_price']) / rec['entry_price'] * 100)
                    if rec['action'] == 'VENDA':
                        performance = -performance
                    
                    # Verificar se atingiu alvo ou stop
                    status = rec['status']
                    if rec['action'] == 'COMPRA':
                        if current_price >= rec['target_price']:
                            status = 'FINALIZADA_GANHO'
                        elif current_price <= rec['stop_loss']:
                            status = 'FINALIZADA_PERDA'
                    else:  # VENDA
                        if current_price <= rec['target_price']:
                            status = 'FINALIZADA_GANHO'
                        elif current_price >= rec['stop_loss']:
                            status = 'FINALIZADA_PERDA'
                    
                    # Atualizar no banco
                    cursor.execute("""
                        UPDATE recommendations_free
                        SET current_price = %s, performance = %s, status = %s, updated_at = %s
                        WHERE id = %s
                    """, (current_price, performance, status, datetime.now(timezone.utc), rec['id']))
                    
                except Exception as e:
                    print(f"Erro ao atualizar {ticker}: {e}")
                    continue
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"Erro ao atualizar preços: {e}")
            return False
    
    @staticmethod
    def get_statistics():
        """Calcular estatísticas de performance"""
        try:
            conn = get_db_connection()
            if not conn:
                return None
            
            cursor = conn.cursor()
            
            # Estatísticas gerais
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status LIKE 'FINALIZADA%' THEN 1 END) as closed,
                    COUNT(CASE WHEN status = 'FINALIZADA_GANHO' THEN 1 END) as wins,
                    COUNT(CASE WHEN status = 'FINALIZADA_PERDA' THEN 1 END) as losses,
                    AVG(CASE WHEN status = 'FINALIZADA_GANHO' THEN performance END) as avg_gain,
                    AVG(CASE WHEN status = 'FINALIZADA_PERDA' THEN performance END) as avg_loss
                FROM recommendations_free
                WHERE created_at >= NOW() - INTERVAL '30 days'
            """)
            
            stats = cursor.fetchone()
            
            # Melhor performance
            cursor.execute("""
                SELECT ticker, performance, created_at
                FROM recommendations_free
                WHERE status = 'FINALIZADA_GANHO'
                ORDER BY performance DESC
                LIMIT 1
            """)
            
            best = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            total, closed, wins, losses, avg_gain, avg_loss = stats
            
            success_rate = (wins / closed * 100) if closed > 0 else 0
            profit_factor = (avg_gain / abs(avg_loss)) if avg_loss else 0
            
            return {
                'total_count': total or 0,
                'closed_count': closed or 0,
                'wins': wins or 0,
                'losses': losses or 0,
                'success_rate': success_rate,
                'avg_gain': avg_gain or 0,
                'avg_loss': avg_loss or 0,
                'profit_factor': profit_factor,
                'best_performance': {
                    'ticker': best[0],
                    'gain': float(best[1]),
                    'date': best[2].isoformat()
                } if best else None
            }
            
        except Exception as e:
            print(f"Erro ao calcular estatísticas: {e}")
            return None
    
    @staticmethod
    def get_chart_data(ticker, days=30):
        """Buscar dados para gráfico"""
        try:
            symbol = ticker if ticker.endswith('.SA') else f"{ticker}.SA"
            stock = yf.Ticker(symbol)
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                return None
            
            return {
                'dates': [d.strftime('%d/%m') for d in hist.index],
                'prices': hist['Close'].tolist(),
                'volumes': hist['Volume'].tolist()
            }
            
        except Exception as e:
            print(f"Erro ao buscar dados do gráfico: {e}")
            return None
    
    @staticmethod
    def get_performance_history():
        """Buscar histórico de performance para gráfico"""
        try:
            conn = get_db_connection()
            if not conn:
                return []
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ticker, performance, status, created_at
                FROM recommendations_free
                WHERE status LIKE 'FINALIZADA%'
                ORDER BY created_at DESC
                LIMIT 20
            """)
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'ticker': row[0],
                    'performance': float(row[1]),
                    'status': row[2],
                    'date': row[3].isoformat() if row[3] else None
                })
            
            cursor.close()
            conn.close()
            
            return history
            
        except Exception as e:
            print(f"Erro ao buscar histórico: {e}")
            return []

# Função para criar tabela no banco
def create_recommendations_table():
    """Criar tabela de recomendações free"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations_free (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                company_name VARCHAR(255),
                action VARCHAR(10) NOT NULL,
                entry_price DECIMAL(10,2) NOT NULL,
                stop_loss DECIMAL(10,2) NOT NULL,
                target_price DECIMAL(10,2) NOT NULL,
                current_price DECIMAL(10,2),
                confidence DECIMAL(5,2),
                risk_reward DECIMAL(5,2),
                technical_data JSONB,
                status VARCHAR(20) DEFAULT 'ATIVA',
                performance DECIMAL(10,2) DEFAULT 0,
                ml_analysis TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_rec_free_status ON recommendations_free(status);
            CREATE INDEX IF NOT EXISTS idx_rec_free_ticker ON recommendations_free(ticker);
            CREATE INDEX IF NOT EXISTS idx_rec_free_created ON recommendations_free(created_at);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela recommendations_free criada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela: {e}")
        return False