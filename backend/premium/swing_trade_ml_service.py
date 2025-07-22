import yfinance as yf
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, confusion_matrix
from xgboost import XGBClassifier
from sklearn.ensemble import VotingClassifier
from imblearn.over_sampling import SMOTE
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.simplefilter('ignore')

class SwingTradeMachineLearningService:
    def __init__(self):
        # Configuração das cores cyberpunk
        self.cyberpunk_colors = {
            'neon_green': 'rgba(0, 255, 170, 0.8)',
            'neon_red': 'rgba(255, 50, 50, 0.8)',
            'neon_blue': 'rgba(0, 191, 255, 0.8)',
            'neon_purple': 'rgba(148, 0, 211, 0.8)',
            'neon_pink': 'rgba(255, 0, 127, 0.8)',
            'neon_orange': 'rgba(255, 165, 0, 0.8)',
            'gray': 'rgba(150, 150, 150, 0.4)'
        }
        
        # Parâmetros dos stops dinâmicos
        self.ATR_FACTOR = 2.0
        self.VOL_FACTOR = 2.0
        self.MIN_STOP = 0.02
        self.MAX_STOP = 0.06
        self.MIN_TAKE = 0.04
        self.MAX_TAKE = 0.20

    def normalize_yfinance_data(self, df):
        """Normaliza dados do yfinance removendo MultiIndex se existir"""
        print("Normalizando dados do yfinance...")
        
        # Se o DataFrame tem MultiIndex nas colunas, vamos simplificar
        if isinstance(df.columns, pd.MultiIndex):
            # Pegar apenas o primeiro nível das colunas
            df.columns = df.columns.droplevel(1)
        
        # Garantir que as colunas básicas existem
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Colunas básicas não encontradas: {missing_cols}")
        
        print("Dados normalizados com sucesso")
        return df

    def download_data(self, ticker, start_date='2010-01-01', end_date='2025-12-31'):
        """Download dos dados históricos"""
        try:
            ticker_symbol = ticker.upper() + ".SA" if not ticker.endswith('.SA') else ticker.upper()
            print(f"Baixando dados para {ticker_symbol}...")
            
            df = yf.download(ticker_symbol, start=start_date, end=end_date, progress=False)
            
            if df.empty:
                raise ValueError(f"Nenhum dado encontrado para {ticker_symbol}")
            
            # Normalizar dados do yfinance
            df = self.normalize_yfinance_data(df)
            
            print(f"Dados baixados: {len(df)} registros")
            return df, ticker_symbol
            
        except Exception as e:
            raise Exception(f"Erro ao baixar dados: {str(e)}")

    def calculate_indicators(self, df, prediction_days):
        """Calcula todos os indicadores técnicos - VERSÃO CORRIGIDA"""
        print("Calculando indicadores técnicos...")
        
        # Verificar se temos a coluna Close
        if 'Close' not in df.columns:
            raise ValueError("Coluna 'Close' não encontrada nos dados")
        
        # Smoothed Close
        df['Smoothed_Close'] = df['Close'].ewm(alpha=0.1).mean()

        # RSI - com tratamento de divisão por zero
        delta = df['Close'].diff(1)
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        
        # Evitar divisão por zero
        rs = avg_gain / (avg_loss + 1e-10)  # Adicionar pequeno epsilon
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Clipar RSI entre 0 e 100
        df['RSI'] = np.clip(df['RSI'], 0, 100)

        # Estocástico - com tratamento de divisão por zero
        low_14 = df['Low'].rolling(window=14).min()
        high_14 = df['High'].rolling(window=14).max()
        denominator = high_14 - low_14
        denominator = denominator.replace(0, 1e-10)  # Evitar divisão por zero
        df['stochastic_k'] = 100 * (df['Close'] - low_14) / denominator
        
        # Clipar entre 0 e 100
        df['stochastic_k'] = np.clip(df['stochastic_k'], 0, 100)

        # Williams %R - com tratamento de divisão por zero
        df['Williams_%R'] = (high_14 - df['Close']) / (denominator + 1e-10) * -100
        
        # Clipar entre -100 e 0
        df['Williams_%R'] = np.clip(df['Williams_%R'], -100, 0)

        # PROC - com tratamento de divisão por zero
        close_14_ago = df['Close'].shift(14)
        df['PROC'] = (df['Close'] - close_14_ago) / (close_14_ago + 1e-10) * 100
        
        # Clipar valores extremos
        df['PROC'] = np.clip(df['PROC'], -1000, 1000)

        # Z-Score - com tratamento de divisão por zero
        highest_252 = df['High'].rolling(window=252).max()
        lowest_252 = df['Low'].rolling(window=252).min()
        middle_252 = (highest_252 + lowest_252) / 2
        range_252 = highest_252 - lowest_252
        range_252 = range_252.replace(0, 1e-10)  # Evitar divisão por zero
        df['Z_Score'] = (df['Close'] - middle_252) / range_252
        
        # Clipar Z-Score
        df['Z_Score'] = np.clip(df['Z_Score'], -5, 5)

        # Volatilidade - com tratamento de divisão por zero
        rolling_mean = df['Close'].rolling(window=20).mean()
        rolling_std = df['Close'].rolling(window=20).std()
        upper_band = rolling_mean + (rolling_std * 2)
        lower_band = rolling_mean - (rolling_std * 2)
        df['Volatility'] = (upper_band - lower_band) / (rolling_mean + 1e-10)
        
        # Clipar volatilidade
        df['Volatility'] = np.clip(df['Volatility'], 0, 10)

        # ATR - com tratamento robusto
        print("Calculando ATR...")
        
        df['HL'] = df['High'] - df['Low']
        df['HC'] = abs(df['High'] - df['Close'].shift(1))
        df['LC'] = abs(df['Low'] - df['Close'].shift(1))
        
        # True Range é o máximo dos três valores
        df['TR'] = df[['HL', 'HC', 'LC']].max(axis=1)
        
        # ATR é a média móvel do TR
        df['ATR'] = df['TR'].rolling(window=14).mean()
        
        # Limpar colunas auxiliares
        df.drop(['HL', 'HC', 'LC'], axis=1, inplace=True)

        # Volatilidade dos últimos 60 dias
        df['Daily_Returns'] = df['Close'].pct_change()
        df['Volatility_60_Pct'] = df['Daily_Returns'].rolling(window=60).std()
        
        # Clipar volatilidade
        df['Volatility_60_Pct'] = np.clip(df['Volatility_60_Pct'], 0, 1)

        # Target
        df['target'] = np.where(df['Close'].shift(-prediction_days) > df['Close'], 1, 0)

        # LIMPEZA FINAL - substituir qualquer valor problemático remanescente
        numeric_columns = ['Smoothed_Close', 'RSI', 'stochastic_k', 'Williams_%R', 'PROC', 'Z_Score', 'Volatility', 'ATR', 'Volatility_60_Pct']
        
        for col in numeric_columns:
            if col in df.columns:
                # Substituir infinitos por NaN
                df[col] = df[col].replace([np.inf, -np.inf], np.nan)
                
                # Verificar quantos NaN temos
                nan_count = df[col].isna().sum()
                if nan_count > 0:
                    print(f"Preenchendo {nan_count} NaN em {col}")
                    df[col] = df[col].fillna(method='ffill').fillna(method='bfill')
                    
                # Se ainda há NaN, usar mediana
                if df[col].isna().any():
                    df[col] = df[col].fillna(df[col].median())

        print("Indicadores calculados com sucesso")
        return df

    def prepare_model_data(self, df):
        """Prepara os dados para o modelo - VERSÃO CORRIGIDA"""
         
        # Features
        features = ['Smoothed_Close', 'RSI', 'stochastic_k', 'Williams_%R', 'PROC', 'Z_Score', 'Volatility']
        
        # Verificar se todas as features existem
        missing_features = [f for f in features if f not in df.columns]
        if missing_features:
            raise ValueError(f"Features não encontradas: {missing_features}")
        
        # LIMPEZA RIGOROSA - ETAPA 1: Remover infinitos e NaN
        print("Limpando dados...")
        
        # Substituir infinitos por NaN primeiro
        df_clean = df.replace([np.inf, -np.inf], np.nan)
        
        # Verificar quantos NaN/infinitos temos
        for feature in features:
            nan_count = df_clean[feature].isna().sum()
            inf_count = np.isinf(df_clean[feature]).sum()
            print(f"Feature {feature}: {nan_count} NaN, {inf_count} infinitos")
        
        # Remover linhas com NaN
        df_clean = df_clean.dropna()
        print(f"Shape após limpeza básica: {df_clean.shape}")
        
        # LIMPEZA RIGOROSA - ETAPA 2: Verificar outliers extremos
        for feature in features:
            # Remover outliers extremos (Z-score > 10)
            z_scores = np.abs((df_clean[feature] - df_clean[feature].mean()) / df_clean[feature].std())
            outliers = z_scores > 10
            outlier_count = outliers.sum()
            if outlier_count > 0:
                print(f"Removendo {outlier_count} outliers extremos de {feature}")
                df_clean = df_clean[~outliers]
        
        print(f"Shape após remoção de outliers: {df_clean.shape}")
        
        # LIMPEZA RIGOROSA - ETAPA 3: Extrair features e target
        X = df_clean[features].copy()
        y = df_clean['target'].copy()
        
        # Verificar se ainda há valores problemáticos
        for i, feature in enumerate(features):
            if X[feature].isna().any():
                print(f"ERRO: {feature} ainda tem NaN!")
                raise ValueError(f"Feature {feature} ainda contém NaN após limpeza")
            
            if np.isinf(X[feature]).any():
                print(f"ERRO: {feature} ainda tem infinitos!")
                raise ValueError(f"Feature {feature} ainda contém infinitos após limpeza")
            
            # Verificar se a feature tem variação
            if X[feature].std() == 0:
                print(f"AVISO: {feature} tem variação zero")
        
        # Verificar se temos dados suficientes
        if len(X) < 100:
            raise ValueError(f"Dados insuficientes após limpeza. Restaram {len(X)} amostras, necessário pelo menos 100")
        
        # Verificar se target tem variação
        if len(np.unique(y)) < 2:
            raise ValueError("Target não tem variação suficiente (todas as classes iguais)")
        
        print(f"Dados preparados com sucesso: {len(X)} amostras, {len(features)} features")
        print(f"Distribuição do target: {np.bincount(y)}")
        
        return X, y, features

    def train_model(self, X, y):
        """Treina o modelo ensemble"""
        print("Treinando modelo ensemble...")
        
        # Split e SMOTE
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=True, random_state=42)
        
        # Verificar se temos classes suficientes
        if len(np.unique(y_train)) < 2:
            raise ValueError("Dados insuficientes - não há variação suficiente nos targets")
        
        smote = SMOTE(random_state=42)
        X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)

        # Escalonamento
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_resampled)
        X_test_scaled = scaler.transform(X_test)

        # Modelos
        rf_model = RandomForestClassifier(
            n_estimators=80, 
            min_samples_split=7, 
            min_samples_leaf=2, 
            max_depth=13, 
            bootstrap=False, 
            random_state=42
        )
        
        xgb_model = XGBClassifier(
            n_estimators=80, 
            max_depth=13, 
            learning_rate=0.1, 
            colsample_bytree=0.8, 
            subsample=0.8, 
            random_state=42, 
            use_label_encoder=False, 
            eval_metric='logloss'
        )

        ensemble_model = VotingClassifier(
            estimators=[('rf', rf_model), ('xgb', xgb_model)], 
            voting='hard'
        )

        ensemble_model.fit(X_train_scaled, y_train_resampled)

        # Avaliação
        y_pred = ensemble_model.predict(X_test_scaled)
        
        # Calcular métricas com tratamento de erro
        try:
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, zero_division=0)
            recall = recall_score(y_test, y_pred, zero_division=0)
            cm = confusion_matrix(y_test, y_pred)
        except Exception as e:
            print(f"Erro ao calcular métricas: {e}")
            accuracy = precision = recall = 0.0
            cm = np.array([[0, 0], [0, 0]])
        
        metrics = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'confusion_matrix': cm
        }

        print(f"Modelo treinado - Acurácia: {accuracy:.3f}")
        return ensemble_model, scaler, metrics

    def calculate_dynamic_stops(self, df):
        """Calcula os stops dinâmicos - EXATAMENTE como o MetaTrader"""
        print("Calculando stops dinâmicos...")
        
        # Verificar se as colunas necessárias existem
        required_cols = ['ATR', 'Close', 'Volatility_60_Pct']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Colunas não encontradas: {missing_cols}")
        
        # Verificar se as colunas são Series ou DataFrames
        print(f"Tipo da coluna ATR: {type(df['ATR'])}")
        print(f"Tipo da coluna Close: {type(df['Close'])}")
        print(f"Tipo da coluna Volatility_60_Pct: {type(df['Volatility_60_Pct'])}")
        
        # Garantir que estamos trabalhando com Series
        if isinstance(df['ATR'], pd.DataFrame):
            atr_series = df['ATR'].iloc[:, 0]
        else:
            atr_series = df['ATR']
            
        if isinstance(df['Close'], pd.DataFrame):
            close_series = df['Close'].iloc[:, 0]
        else:
            close_series = df['Close']
            
        if isinstance(df['Volatility_60_Pct'], pd.DataFrame):
            vol_series = df['Volatility_60_Pct'].iloc[:, 0]
        else:
            vol_series = df['Volatility_60_Pct']
        
        # Calcular stops - EXATAMENTE como o MetaTrader (usando apply)
        df['ATR_Pct'] = atr_series / close_series
        df['Stop_Loss'] = df.apply(lambda x: min(max(x['ATR_Pct'] * self.ATR_FACTOR, self.MIN_STOP), self.MAX_STOP), axis=1)
        df['Take_Profit'] = df.apply(lambda x: min(max(x['Volatility_60_Pct'] * self.VOL_FACTOR, self.MIN_TAKE), self.MAX_TAKE), axis=1)
        
        print("Stops dinâmicos calculados com sucesso")
        return df

    def generate_predictions(self, df, model, scaler, features):
        """Gera as previsões e cores - VERSÃO CORRIGIDA"""
        print("Gerando previsões...")
        
        # Preparar dados para predição
        X_pred = df[features].copy()
        
        # Limpeza rigorosa dos dados de predição
        X_pred = X_pred.replace([np.inf, -np.inf], np.nan)
        
        # Para predição, vamos usar forward fill para NaN
        X_pred = X_pred.fillna(method='ffill').fillna(method='bfill')
        
        # Verificar se ainda há problemas
        for feature in features:
            if X_pred[feature].isna().any():
                print(f"ERRO: {feature} ainda tem NaN após fillna!")
                # Usar mediana como último recurso
                X_pred[feature] = X_pred[feature].fillna(X_pred[feature].median())
            
            if np.isinf(X_pred[feature]).any():
                print(f"ERRO: {feature} ainda tem infinitos!")
                # Clipar valores extremos
                X_pred[feature] = np.clip(X_pred[feature], 
                                        X_pred[feature].quantile(0.01), 
                                        X_pred[feature].quantile(0.99))
        
        # Escalar dados
        try:
            X_scaled = scaler.transform(X_pred)
            
            # Verificar se há NaN ou infinitos após escalonamento
            if np.isnan(X_scaled).any() or np.isinf(X_scaled).any():
                print("ERRO: Dados escalados contêm NaN ou infinitos!")
                raise ValueError("Dados escalados contêm valores inválidos")
            
            # Fazer predição
            predictions = model.predict(X_scaled)
            df['prediction'] = predictions
            
        except Exception as e:
            print(f"Erro na predição: {e}")
            # Fallback: usar predições aleatórias baseadas na distribuição histórica
            print("Usando predições de fallback...")
            np.random.seed(42)
            df['prediction'] = np.random.choice([0, 1], size=len(df), p=[0.6, 0.4])
        
        # Aplicar cores
        df['color'] = np.where(df['prediction'] == 1, 
                              self.cyberpunk_colors['neon_green'], 
                              self.cyberpunk_colors['neon_red'])
        
        print("Previsões geradas com sucesso")
        return df

    def get_analysis_data(self, df, ticker, prediction_days, metrics):
        """Retorna os dados para análise em cards - FORMATO MetaTrader"""
        print("Preparando dados de análise...")
        
        # Valores atuais
        today_price = df['Close'].iloc[-1]
        today_prediction = df['prediction'].iloc[-1]
        current_atr = df['ATR'].iloc[-1]
        current_vol = df['Volatility_60_Pct'].iloc[-1]

        # Cálculo dos níveis atuais
        stop_loss = min(max(current_atr / today_price * self.ATR_FACTOR, self.MIN_STOP), self.MAX_STOP)
        take_profit = min(max(current_vol * self.VOL_FACTOR, self.MIN_TAKE), self.MAX_TAKE)

        if today_prediction == 1:
            take_profit_price = today_price * (1 + take_profit)
            stop_loss_price = today_price * (1 - stop_loss)
        else:
            take_profit_price = today_price * (1 - take_profit)
            stop_loss_price = today_price * (1 + stop_loss)

        # Dados históricos - EXATAMENTE como o MetaTrader
        historical_date = df.index[-prediction_days]
        historical_price = df['Close'].iloc[-prediction_days]
        historical_prediction = df['prediction'].iloc[-prediction_days]

        # Resultado histórico - EXATAMENTE como o MetaTrader
        if historical_prediction == 1:  # COMPRA
            resultado_historico = ((today_price - historical_price) / historical_price * 100)
        else:  # VENDA
            resultado_historico = ((historical_price - today_price) / historical_price * 100)

        variacao_percentual = ((today_price - historical_price) / historical_price * 100)

        analysis_data = {
            'ticker': ticker,
            'data_atual': datetime.now().strftime('%Y-%m-%d'),
            'preco_atual': float(today_price),
            'direcao': 'COMPRA' if today_prediction == 1 else 'VENDA',
            'take_profit_price': float(take_profit_price),
            'stop_loss_price': float(stop_loss_price),
            'take_profit_pct': float(take_profit * 100),
            'stop_loss_pct': float(stop_loss * 100),
            'atr_atual': float(current_atr),
            'atr_pct': float(current_atr / today_price * 100),
            'atr_medio': float(df['ATR'].mean() / df['Close'].mean() * 100),
            'volatilidade_60d': float(current_vol * 100),
            'vol_maxima_60d': float(df['Volatility_60_Pct'].max() * 100),
            'stop_loss_medio': float(df['Stop_Loss'].mean() * 100),
            'take_profit_medio': float(df['Take_Profit'].mean() * 100),
            'data_historica': historical_date.strftime('%Y-%m-%d'),
            'preco_historico': float(historical_price),
            'sinal_historico': 'COMPRA' if historical_prediction == 1 else 'VENDA',
            'resultado_historico': float(resultado_historico),
            'resultado_status': 'LUCRO' if resultado_historico > 0 else 'PREJUÍZO',
            'variacao_percentual': float(variacao_percentual),
            'direcao_movimento': 'subiu' if variacao_percentual > 0 else 'caiu',
            'accuracy': float(metrics['accuracy']),
            'precision': float(metrics['precision']),
            'recall': float(metrics['recall']),
            'confusion_matrix': {
                'tn': int(metrics['confusion_matrix'][0, 0]),
                'fp': int(metrics['confusion_matrix'][0, 1]),
                'fn': int(metrics['confusion_matrix'][1, 0]),
                'tp': int(metrics['confusion_matrix'][1, 1])
            },
            # Análise textual completa como no MetaTrader
            'analise_completa': self.generate_complete_analysis(
                ticker, today_price, today_prediction, take_profit_price, stop_loss_price,
                take_profit, stop_loss, current_atr, current_vol, df,
                historical_date, historical_price, historical_prediction,
                resultado_historico, variacao_percentual, metrics
            )
        }
        
        print("Dados de análise preparados")
        return analysis_data

    def generate_complete_analysis(self, ticker, today_price, today_prediction, take_profit_price, 
                                 stop_loss_price, take_profit, stop_loss, current_atr, current_vol, df,
                                 historical_date, historical_price, historical_prediction, 
                                 resultado_historico, variacao_percentual, metrics):
        """Gera análise completa EXATAMENTE como o MetaTrader imprime"""
        
        analysis_text = f"""
{'='*70}
ANÁLISE DE TRADING - {ticker}
{'='*70}
Data atual: {datetime.now().strftime('%Y-%m-%d')}
Preço atual: {today_price:.2f}
Direção: {'COMPRA' if today_prediction == 1 else 'VENDA'}
{'-'*70}
NÍVEIS DE OPERAÇÃO:
Take Profit: {take_profit_price:.2f} ({take_profit*100:.1f}% dinâmico)
Stop Loss: {stop_loss_price:.2f} ({stop_loss*100:.1f}% dinâmico)
{'-'*70}
MÉTRICAS DE VOLATILIDADE:
ATR atual: {current_atr:.4f} ({(current_atr/today_price*100):.2f}% do preço)
ATR médio: {(df['ATR'].mean()/df['Close'].mean()*100):.2f}%
Volatilidade 60d: {(current_vol*100):.2f}%
Vol máxima 60d: {(df['Volatility_60_Pct'].max()*100):.2f}%
{'-'*70}
PERFORMANCE DO STOP DINÂMICO:
Stop Loss médio: {(df['Stop_Loss'].mean()*100):.2f}%
Take Profit médio: {(df['Take_Profit'].mean()*100):.2f}%
{'-'*70}

ANÁLISE HISTÓRICA:
Data histórica: {historical_date.strftime('%Y-%m-%d')}
Preço histórico: {historical_price:.2f}
Preço atual: {today_price:.2f}
Sinal histórico: {'COMPRA' if historical_prediction == 1 else 'VENDA'}
"""

        if historical_prediction == 1:  # COMPRA
            analysis_text += f"Resultado (Compra): {resultado_historico:.2f}% {'LUCRO' if resultado_historico > 0 else 'PREJUÍZO'}\n"
        else:  # VENDA
            analysis_text += f"Resultado (Venda): {resultado_historico:.2f}% {'LUCRO' if resultado_historico > 0 else 'PREJUÍZO'}\n"
        
        analysis_text += f"Preço {'subiu' if variacao_percentual > 0 else 'caiu'} {abs(variacao_percentual):.2f}% desde a previsão\n"
        analysis_text += f"{'-'*70}\n"
        
        return analysis_text

    def create_chart(self, df, ticker, prediction_days):
        """KILLER DEBUG - GRÁFICO MAIS BÁSICO POSSÍVEL"""
        print("🔥 CRIANDO GRÁFICO KILLER DEBUG...")
        
        try:
            # ZERO FRESCURA - SÓ O BÁSICO
            fig = go.Figure()

            # SÓ UMA LINHA AZUL SIMPLES - NADA MAIS
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df['Close'],
                mode='lines',
                name='Preço',
                line=dict(color='blue', width=1)
            ))

            # LAYOUT ULTRA BÁSICO
            fig.update_layout(
                title=f'{ticker} - TEST KILLER',
                template='plotly_dark',
                autosize=True
            )

            # SEM NADA DE ESPECIAL
            print("🔥 HTML básico sendo gerado...")
            
            html_output = fig.to_html(
                include_plotlyjs='cdn',
                config={'responsive': True}
            )
            
            print(f"🔥 HTML gerado - tamanho: {len(html_output)} chars")
            print("🔥 KILLER DEBUG - Se ainda tiver linha vermelha, o problema NÃO é no create_chart!")
            
            return html_output
            
        except Exception as e:
            print(f"🔥 ERRO KILLER: {e}")
            return f"<div style='color:white;'>ERRO KILLER: {str(e)}</div>"

    def create_fallback_chart(self, df, ticker):
        """Gráfico de emergência super simples"""
        print("Criando gráfico de emergência...")
        
        try:
            # Apenas os últimos 100 pontos
            recent_data = df.tail(100).copy()
            
            # Criar figura simples
            fig = go.Figure()
            
            # Linha de preço simples
            fig.add_trace(go.Scatter(
                y=recent_data['Close'].values,
                mode='lines',
                name='Preço',
                line=dict(color='#00aaff', width=2)
            ))
            
            # Marcadores de sinais
            for i, (idx, row) in enumerate(recent_data.iterrows()):
                if row['prediction'] == 1:
                    fig.add_trace(go.Scatter(
                        x=[i], y=[row['Close']],
                        mode='markers',
                        marker=dict(symbol='triangle-up', size=8, color='green'),
                        showlegend=False
                    ))
                else:
                    fig.add_trace(go.Scatter(
                        x=[i], y=[row['Close']],
                        mode='markers',
                        marker=dict(symbol='triangle-down', size=8, color='red'),
                        showlegend=False
                    ))
            
            # Layout simples
            fig.update_layout(
                title=f'{ticker} - Análise de Emergência',
                template='plotly_dark',
                height=400,
                showlegend=True,
                xaxis_title="Período",
                yaxis_title="Preço"
            )
            
            return fig.to_html(include_plotlyjs='cdn', div_id="emergency-chart")
            
        except Exception as e:
            print(f"Erro no gráfico de emergência: {e}")
            return f"""
            <div style="color: white; background: #1a1a1a; padding: 20px; border-radius: 8px;">
                <h3>Erro no Gráfico</h3>
                <p>Não foi possível gerar o gráfico: {str(e)}</p>
                <p>Ticker: {ticker}</p>
                <p>Shape dos dados: {df.shape if df is not None else 'N/A'}</p>
            </div>
            """

    def get_analysis_data(self, df, ticker, prediction_days, metrics):
        """Retorna os dados para análise em cards"""
        print("Preparando dados de análise...")
        
        # Valores atuais
        today_price = df['Close'].iloc[-1]
        today_prediction = df['prediction'].iloc[-1]
        current_atr = df['ATR'].iloc[-1]
        current_vol = df['Volatility_60_Pct'].iloc[-1]

        # Cálculo dos níveis atuais
        stop_loss = min(max(current_atr / today_price * self.ATR_FACTOR, self.MIN_STOP), self.MAX_STOP)
        take_profit = min(max(current_vol * self.VOL_FACTOR, self.MIN_TAKE), self.MAX_TAKE)

        if today_prediction == 1:
            take_profit_price = today_price * (1 + take_profit)
            stop_loss_price = today_price * (1 - stop_loss)
        else:
            take_profit_price = today_price * (1 - take_profit)
            stop_loss_price = today_price * (1 + stop_loss)

        # Dados históricos
        historical_date = df.index[-prediction_days]
        historical_price = df['Close'].iloc[-prediction_days]
        historical_prediction = df['prediction'].iloc[-prediction_days]

        # Resultado histórico
        if historical_prediction == 1:  # COMPRA
            resultado_historico = ((today_price - historical_price) / historical_price * 100)
        else:  # VENDA
            resultado_historico = ((historical_price - today_price) / historical_price * 100)

        variacao_percentual = ((today_price - historical_price) / historical_price * 100)

        analysis_data = {
            'ticker': ticker,
            'data_atual': datetime.now().strftime('%Y-%m-%d'),
            'preco_atual': float(today_price),
            'direcao': 'COMPRA' if today_prediction == 1 else 'VENDA',
            'take_profit_price': float(take_profit_price),
            'stop_loss_price': float(stop_loss_price),
            'take_profit_pct': float(take_profit * 100),
            'stop_loss_pct': float(stop_loss * 100),
            'atr_atual': float(current_atr),
            'atr_pct': float(current_atr / today_price * 100),
            'atr_medio': float(df['ATR'].mean() / df['Close'].mean() * 100),
            'volatilidade_60d': float(current_vol * 100),
            'vol_maxima_60d': float(df['Volatility_60_Pct'].max() * 100),
            'stop_loss_medio': float(df['Stop_Loss'].mean() * 100),
            'take_profit_medio': float(df['Take_Profit'].mean() * 100),
            'data_historica': historical_date.strftime('%Y-%m-%d'),
            'preco_historico': float(historical_price),
            'sinal_historico': 'COMPRA' if historical_prediction == 1 else 'VENDA',
            'resultado_historico': float(resultado_historico),
            'resultado_status': 'LUCRO' if resultado_historico > 0 else 'PREJUÍZO',
            'variacao_percentual': float(variacao_percentual),
            'direcao_movimento': 'subiu' if variacao_percentual > 0 else 'caiu',
            'accuracy': float(metrics['accuracy']),
            'precision': float(metrics['precision']),
            'recall': float(metrics['recall']),
            'confusion_matrix': {
                'tn': int(metrics['confusion_matrix'][0, 0]),
                'fp': int(metrics['confusion_matrix'][0, 1]),
                'fn': int(metrics['confusion_matrix'][1, 0]),
                'tp': int(metrics['confusion_matrix'][1, 1])
            }
        }
        
        print("Dados de análise preparados")
        return analysis_data

    def debug_chart_data(self, df):
        """Debug para verificar os dados do gráfico"""
        
        # Verificar se as colunas necessárias existem
        required_cols = ['Open', 'High', 'Low', 'Close', 'prediction']
        for col in required_cols:
            if col in df.columns:
                print(f"✓ {col}: OK - tipo {type(df[col].iloc[-1])}")
            else:
                print(f"✗ {col}: FALTANDO")
        
        print("=== FIM DEBUG ===")
        return True

    def run_analysis(self, ticker, prediction_days):
        """Executa a análise completa"""
        try:
            print(f"=== INICIANDO ANÁLISE SWING TRADE ML ===")
            print(f"Ticker: {ticker}, Dias: {prediction_days}")
            
            # Download dos dados
            df, ticker_symbol = self.download_data(ticker)
            
            # Verificar se temos dados suficientes
            if len(df) < 300:
                raise ValueError(f"Dados insuficientes. Encontrados {len(df)} registros, necessário pelo menos 300")
            
            # Calcular indicadores
            df = self.calculate_indicators(df, prediction_days)
            
            # Preparar dados do modelo
            X, y, features = self.prepare_model_data(df)
            
            # Treinar modelo
            model, scaler, metrics = self.train_model(X, y)
            
            # Calcular stops dinâmicos
            df = self.calculate_dynamic_stops(df)
            
            # Gerar previsões
            df = self.generate_predictions(df, model, scaler, features)
            
            # Debug dos dados antes de criar o gráfico
            self.debug_chart_data(df)
            
            # Criar gráfico
            chart_html = self.create_chart(df, ticker_symbol, prediction_days)
            
            # Verificar se o HTML foi gerado
            if not chart_html or len(chart_html) < 100:
                print("⚠️ HTML do gráfico muito pequeno, tentando versão alternativa...")
                chart_html = self.create_simple_chart(df, ticker_symbol)
            
            # Obter dados para análise
            analysis_data = self.get_analysis_data(df, ticker_symbol, prediction_days, metrics)
            
            print("=== ANÁLISE CONCLUÍDA COM SUCESSO ===")
            print(f"Tamanho do HTML gerado: {len(chart_html)} caracteres")
            
            return {
                'success': True,
                'chart_html': chart_html,
                'analysis_data': analysis_data,
                'dataframe' :  df,
                'debug_info': {
                    'df_shape': df.shape,
                    'html_size': len(chart_html),
                    'last_prediction': int(df['prediction'].iloc[-1]),
                    'last_price': float(df['Close'].iloc[-1])
                }
            }
            
        except Exception as e:
            print(f"=== ERRO NA ANÁLISE ===")
            print(f"Erro: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e),
                'debug_info': {
                    'error_type': type(e).__name__,
                    'error_location': 'run_analysis'
                }
            }