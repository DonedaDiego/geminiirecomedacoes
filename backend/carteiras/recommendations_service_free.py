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
        """Calcular indicadores técnicos com foco em cruzamento"""
        
        # ✅ MÉDIAS MAIS RÁPIDAS PARA SINAIS PRECISOS
        df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()   # Média rápida
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean() # Média lenta
        
        # Detectar cruzamentos
        df['Signal_Cross'] = 0
        
        # Cruzamento para CIMA (Golden Cross) = COMPRA
        df.loc[(df['EMA_9'] > df['EMA_21']) & 
            (df['EMA_9'].shift(1) <= df['EMA_21'].shift(1)), 'Signal_Cross'] = 1
        
        # Cruzamento para BAIXO (Death Cross) = VENDA  
        df.loc[(df['EMA_9'] < df['EMA_21']) & 
            (df['EMA_9'].shift(1) >= df['EMA_21'].shift(1)), 'Signal_Cross'] = -1
        
        # Força do cruzamento (% de distância entre médias)
        df['Cross_Strength'] = abs((df['EMA_9'] - df['EMA_21']) / df['EMA_21'] * 100)
        
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
        """Gerar sinal com foco em cruzamento de médias"""
        df = stock_data['history'].copy()
        df = RecommendationsServiceFree.calculate_technical_indicators(df)
        
        last_row = df.iloc[-1]
        current_price = float(last_row['Close'])
        
        score = 0
        
        # 🚀 CRUZAMENTO DE MÉDIAS (15 pontos - PESO MAIOR!)
        if last_row['Signal_Cross'] == 1:  # Golden Cross
            score += 10  # Sinal forte de compra
            
            # Bônus pela força do cruzamento
            if last_row['Cross_Strength'] > 2:  # >2% de distância
                score += 5
            elif last_row['Cross_Strength'] > 1:  # >1% de distância  
                score += 3
                
        elif last_row['Signal_Cross'] == -1:  # Death Cross
            score -= 10  # Sinal forte de venda
            
            if last_row['Cross_Strength'] > 2:
                score -= 5
            elif last_row['Cross_Strength'] > 1:
                score -= 3
        
        # Confirmar tendência (EMA 9 acima/abaixo EMA 21)
        if last_row['EMA_9'] > last_row['EMA_21']:
            score += 3  # Tendência de alta confirmada
        else:
            score -= 3  # Tendência de baixa confirmada
        
        # 📊 RSI para confirmar (5 pontos)
        if 40 < last_row['RSI'] < 60:  # Zona neutra
            score += 2
        elif last_row['RSI'] < 35:  # Oversold + cruzamento = forte compra
            score += 3
        elif last_row['RSI'] > 65:  # Overbought + cruzamento = forte venda
            score -= 3
        
        # 📈 Volume confirmação (3 pontos)
        avg_volume = df['Volume'].rolling(window=20).mean().iloc[-1]
        if last_row['Volume'] > avg_volume * 1.5:
            score += 3  # Volume confirma o movimento
        
        # 🎯 DECISÃO MAIS SELETIVA
        if score >= 12:  # Precisa de score maior para COMPRA
            action = 'COMPRA'
            confidence = min(score / 18 * 100, 95)
        elif score <= -8:  # Score menor para VENDA
            action = 'VENDA'  
            confidence = min(abs(score) / 18 * 100, 95)
        else:
            return None  # Não gera recomendação
        
        # Calcular stops/alvos baseados no cruzamento
        atr = last_row['ATR']
        ema_distance = abs(last_row['EMA_9'] - last_row['EMA_21'])
        
        if action == 'COMPRA':
            # Stop abaixo da EMA 21 ou 1.5x ATR
            stop_loss = min(last_row['EMA_21'] * 0.98, current_price - (atr * 1.5))
            target_price = current_price + (atr * 3)
        else:  # VENDA
            # Stop acima da EMA 21 ou 1.5x ATR  
            stop_loss = max(last_row['EMA_21'] * 1.02, current_price + (atr * 1.5))
            target_price = current_price - (atr * 3)
        
        return {
            'action': action,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'target_price': target_price,
            'confidence': confidence,
            'score': score,
            'crossover_signal': last_row['Signal_Cross'],
            'cross_strength': last_row['Cross_Strength'],
            'ema_9': last_row['EMA_9'],
            'ema_21': last_row['EMA_21'],
            'technical_data': {
                'ema_9': float(last_row['EMA_9']),
                'ema_21': float(last_row['EMA_21']),
                'crossover': int(last_row['Signal_Cross']),
                'cross_strength': float(last_row['Cross_Strength']),
                'rsi': float(last_row['RSI']),
                'volume_ratio': float(last_row['Volume'] / avg_volume)
            }
        }

    @staticmethod
    def generate_ml_signal_buy_only(stock_data):
        """Versão que gera APENAS recomendações de COMPRA"""
        
        signal = RecommendationsServiceFree.generate_ml_signal(stock_data)
        
        # ✅ SÓ RETORNA SE FOR COMPRA
        if signal and signal['action'] == 'COMPRA':
            return signal
        else:
            return None
    
    @staticmethod
    def generate_monthly_recommendations():
        """Gerar apenas 2 recomendações de COMPRA por mês"""
        recommendations = []
        
        stocks = RecommendationsServiceFree.STOCKS_POOL.copy()
        random.shuffle(stocks)
        
        for ticker in stocks:
            stock_data = RecommendationsServiceFree.get_stock_data(ticker)
            if not stock_data:
                continue
            
            # ✅ USAR VERSÃO SÓ COMPRAS
            signal = RecommendationsServiceFree.generate_ml_signal_buy_only(stock_data)
            
            if signal and signal['confidence'] >= 75:  # Confiança maior para compras
                recommendations.append({
                    'ticker': ticker,
                    'company_name': stock_data['company_name'],
                    'action': signal['action'],  # Sempre COMPRA
                    'entry_price': signal['entry_price'],
                    'stop_loss': signal['stop_loss'], 
                    'target_price': signal['target_price'],
                    'current_price': signal['entry_price'],
                    'confidence': signal['confidence'],
                    'crossover_type': 'Golden Cross' if signal['crossover_signal'] == 1 else 'Trend Confirmation',
                    'technical_data': signal['technical_data']
                })
                
                # ✅ APENAS 2 RECOMENDAÇÕES
                if len(recommendations) >= 2:
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
        """Atualizar preços atuais das recomendações ativas - VERSÃO CORRIGIDA"""
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
                    hist = stock.history(period='1d')
                    
                    if hist.empty:
                        print(f"⚠️ Nenhum dado encontrado para {ticker}")
                        continue
                        
                    current_price = float(hist['Close'].iloc[-1])
                    
                    # ✅ CONVERSÕES EXPLÍCITAS PARA EVITAR CONFLITO DE TIPOS
                    entry_price_float = float(rec['entry_price'])
                    target_price_float = float(rec['target_price'])
                    stop_loss_float = float(rec['stop_loss'])
                    
                    print(f"🔄 Atualizando {ticker}: R$ {current_price}")
                    
                    # Calcular performance - USANDO APENAS FLOAT
                    if rec['action'] == 'COMPRA':
                        performance = ((current_price - entry_price_float) / entry_price_float * 100)
                    else:  # VENDA
                        performance = ((entry_price_float - current_price) / entry_price_float * 100)
                    
                    # Verificar se atingiu alvo ou stop
                    status = rec['status']
                    if rec['action'] == 'COMPRA':
                        if current_price >= target_price_float:
                            status = 'FINALIZADA_GANHO'
                        elif current_price <= stop_loss_float:
                            status = 'FINALIZADA_PERDA'
                    else:  # VENDA
                        if current_price <= target_price_float:
                            status = 'FINALIZADA_GANHO'
                        elif current_price >= stop_loss_float:
                            status = 'FINALIZADA_PERDA'
                    
                    # ✅ ATUALIZAR NO BANCO COM VALORES CONVERTIDOS
                    cursor.execute("""
                        UPDATE recommendations_free
                        SET current_price = %s, 
                            performance = %s, 
                            status = %s, 
                            updated_at = %s
                        WHERE id = %s
                    """, (
                        current_price,  # ✅ Já é float
                        round(performance, 2),  # ✅ Arredondar para evitar problemas
                        status, 
                        datetime.now(timezone.utc), 
                        rec['id']
                    ))
                    
                    if status != rec['status']:
                        print(f"🎯 {ticker} mudou status: {rec['status']} → {status}")
                        # Se mudou para finalizada, definir closed_at
                        if status.startswith('FINALIZADA'):
                            cursor.execute("""
                                UPDATE recommendations_free
                                SET closed_at = %s
                                WHERE id = %s
                            """, (datetime.now(timezone.utc), rec['id']))
                    
                except Exception as e:
                    print(f"❌ Erro ao atualizar {ticker}: {e}")
                    continue
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"❌ Erro geral ao atualizar preços: {e}")
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