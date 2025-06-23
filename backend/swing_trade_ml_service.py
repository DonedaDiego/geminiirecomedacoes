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
        self.VOL_FACTOR = 1.5
        self.MIN_STOP = 0.02
        self.MAX_STOP = 0.08
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
        """Calcula todos os indicadores técnicos"""
        print("Calculando indicadores técnicos...")
        
        # Verificar se temos a coluna Close
        if 'Close' not in df.columns:
            raise ValueError("Coluna 'Close' não encontrada nos dados")
        
        # Smoothed Close
        df['Smoothed_Close'] = df['Close'].ewm(alpha=0.1).mean()

        # RSI
        delta = df['Close'].diff(1)
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # Estocástico
        low_14 = df['Low'].rolling(window=14).min()
        high_14 = df['High'].rolling(window=14).max()
        df['stochastic_k'] = 100 * (df['Close'] - low_14) / (high_14 - low_14)

        # Williams %R
        df['Williams_%R'] = (high_14 - df['Close']) / (high_14 - low_14) * -100

        # PROC
        df['PROC'] = (df['Close'] - df['Close'].shift(14)) / df['Close'].shift(14) * 100

        # Z-Score
        highest_252 = df['High'].rolling(window=252).max()
        lowest_252 = df['Low'].rolling(window=252).min()
        middle_252 = (highest_252 + lowest_252) / 2
        df['Z_Score'] = (df['Close'] - middle_252) / (highest_252 - lowest_252)

        # Volatilidade
        rolling_mean = df['Close'].rolling(window=20).mean()
        rolling_std = df['Close'].rolling(window=20).std()
        upper_band = rolling_mean + (rolling_std * 2)
        lower_band = rolling_mean - (rolling_std * 2)
        df['Volatility'] = (upper_band - lower_band) / rolling_mean

        # ATR - Método simples e direto
        print("Calculando ATR...")
        
        # Calcular True Range de forma direta
        df['HL'] = df['High'] - df['Low']
        df['HC'] = abs(df['High'] - df['Close'].shift(1))
        df['LC'] = abs(df['Low'] - df['Close'].shift(1))
        
        # True Range é o máximo dos três valores
        df['TR'] = df[['HL', 'HC', 'LC']].max(axis=1)
        
        # ATR é a média móvel do TR
        df['ATR'] = df['TR'].rolling(window=14).mean()
        
        # Limpar colunas auxiliares
        df.drop(['HL', 'HC', 'LC'], axis=1, inplace=True)
        
        print(f"ATR calculado - Shape: {df['ATR'].shape}")
        print("ATR calculado com sucesso")

        # Volatilidade dos últimos 60 dias
        df['Daily_Returns'] = df['Close'].pct_change()
        df['Volatility_60_Pct'] = df['Daily_Returns'].rolling(window=60).std()

        # Target
        df['target'] = np.where(df['Close'].shift(-prediction_days) > df['Close'], 1, 0)

        print("Indicadores calculados com sucesso")
        return df

    def prepare_model_data(self, df):
        """Prepara os dados para o modelo"""
        print("Preparando dados para o modelo...")
        
        # Debug: verificar estrutura do DataFrame
        print(f"Shape do DataFrame: {df.shape}")
        print(f"Colunas disponíveis: {df.columns.tolist()}")
        
        # Limpeza dos dados
        df = df.replace([np.inf, -np.inf], np.nan).dropna()
        print(f"Shape após limpeza: {df.shape}")

        # Features
        features = ['Smoothed_Close', 'RSI', 'stochastic_k', 'Williams_%R', 'PROC', 'Z_Score', 'Volatility']
        
        # Verificar se todas as features existem
        missing_features = [f for f in features if f not in df.columns]
        if missing_features:
            raise ValueError(f"Features não encontradas: {missing_features}")
        
        # Debug: tipo de cada coluna
        for feature in features:
            col_type = type(df[feature])
            print(f"Feature {feature}: tipo = {col_type}")
        
        X = df[features]
        y = df['target']
        
        # Verificar se temos dados suficientes
        if len(X) < 100:
            raise ValueError(f"Dados insuficientes após limpeza. Restaram {len(X)} amostras, necessário pelo menos 100")
        
        print(f"Dados preparados: {len(X)} amostras, {len(features)} features")
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
        """Gera as previsões e cores - EXATAMENTE como o MetaTrader"""
        print("Gerando previsões...")
        
        X_scaled = scaler.transform(df[features])
        df['prediction'] = model.predict(X_scaled)
        
        # Aplicar cores - EXATAMENTE como no MetaTrader
        df['color'] = np.where(df['prediction'] == 1, self.cyberpunk_colors['neon_green'], self.cyberpunk_colors['neon_red'])
        
        print("Previsões geradas")
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
        """Cria o gráfico interativo - EXATAMENTE como o MetaTrader"""
        print("Criando gráfico...")
        
        try:
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

            # Criação do gráfico - EXATAMENTE como o MetaTrader
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True,
                vertical_spacing=0.05,
                row_heights=[0.75, 0.25],
                subplot_titles=('Preço, Previsões e Níveis', 'Sinais de Trading')
            )

            # Gráfico de preços - linha principal
            fig.add_trace(
                go.Scatter(
                    x=df.index, 
                    y=df['Close'],
                    mode='lines',
                    name='Preço',
                    line=dict(color=self.cyberpunk_colors['neon_blue'], width=1)
                ),
                row=1, col=1
            )

            # Linhas coloridas das previsões - EXATAMENTE como o MetaTrader
            for i in range(1, len(df)):
                fig.add_trace(
                    go.Scatter(
                        x=[df.index[i-1], df.index[i]], 
                        y=[df['Close'].iloc[i-1], df['Close'].iloc[i]],
                        mode='lines',
                        line=dict(color=df['color'].iloc[i], width=2),
                        showlegend=False
                    ),
                    row=1, col=1
                )

            # Níveis de stop e take atuais - EXATAMENTE como o MetaTrader
            if today_prediction == 1:
                fig.add_trace(
                    go.Scatter(
                        x=[df.index[-1], df.index[-1]],
                        y=[today_price, take_profit_price],
                        mode='lines',
                        name='Take Profit',
                        line=dict(color=self.cyberpunk_colors['neon_green'], width=2, dash='dash')
                    ),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Scatter(
                        x=[df.index[-1], df.index[-1]],
                        y=[today_price, stop_loss_price],
                        mode='lines',
                        name='Stop Loss',
                        line=dict(color=self.cyberpunk_colors['neon_red'], width=2, dash='dash')
                    ),
                    row=1, col=1
                )

            # Sinais - EXATAMENTE como o MetaTrader
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['prediction'],
                    mode='lines',
                    name='Sinais',
                    line=dict(color=self.cyberpunk_colors['neon_purple'], width=1),
                    fill='tozeroy',
                    fillcolor=self.cyberpunk_colors['neon_purple'].replace('0.8', '0.2')
                ),
                row=2, col=1
            )

            # Layout - EXATAMENTE como o MetaTrader
            fig.update_layout(
                template='plotly_dark',
                plot_bgcolor='rgb(27, 27, 50)',
                paper_bgcolor='rgb(27, 27, 50)',
                font=dict(color='rgb(170, 170, 220)'),
                title=dict(
                    text=f'Análise Preditiva com Stops Dinâmicos - {ticker}',
                    font=dict(color='rgb(200, 200, 250)', size=24)
                ),
                showlegend=True,
                width=1200,  # MESMO TAMANHO do MetaTrader
                height=600,  # MESMO TAMANHO do MetaTrader
                legend=dict(
                    bgcolor='rgba(27, 27, 50, 0.8)',
                    bordercolor='rgba(70, 70, 120, 0.8)',
                    borderwidth=1
                )
            )

            # Atualizar eixos - EXATAMENTE como o MetaTrader
            for i in range(1, 3):  # Corrigido para 1, 3 (era 1, 4 no MetaTrader)
                fig.update_xaxes(
                    gridcolor='rgba(70, 70, 120, 0.2)',
                    zerolinecolor='rgba(70, 70, 120, 0.2)',
                    showgrid=True,
                    gridwidth=1,
                    row=i, col=1
                )
                
                fig.update_yaxes(
                    gridcolor='rgba(70, 70, 120, 0.2)',
                    zerolinecolor='rgba(70, 70, 120, 0.2)',
                    showgrid=True,
                    gridwidth=1,
                    row=i, col=1
                )

            # Títulos dos eixos - EXATAMENTE como o MetaTrader
            fig.update_yaxes(title_text="Preço", row=1, col=1)
            fig.update_yaxes(title_text="Sinal", row=2, col=1)

            # Marca d'água - EXATAMENTE como o MetaTrader
            fig.add_annotation(
                text=f"Geminii Research - {datetime.now().strftime('%Y-%m-%d')}",
                xref="paper",
                yref="paper",
                x=0.98,
                y=0.02,
                showarrow=False,
                font=dict(size=10, color='rgba(170, 170, 220, 0.7)'),
                opacity=0.7
            )

            # Anotação com métricas atuais - EXATAMENTE como o MetaTrader
            fig.add_annotation(
                text=f"Stop Loss: {stop_loss*100:.1f}%<br>Take Profit: {take_profit*100:.1f}%",
                xref="paper",
                yref="paper",
                x=0.98,
                y=0.98,
                showarrow=False,
                font=dict(size=12, color='rgba(170, 170, 220, 1)'),
                bgcolor='rgba(27, 27, 50, 0.8)',
                bordercolor='rgba(70, 70, 120, 0.8)',
                borderwidth=1,
                align='right'
            )

            print("Gráfico criado com sucesso - versão MetaTrader")
            
            # Retornar HTML com configuração explícita
            html_output = fig.to_html(
                include_plotlyjs='cdn',
                div_id="trading-chart-mt5",
                config={
                    'displayModeBar': True,
                    'displaylogo': False,
                    'toImageButtonOptions': {
                        'format': 'png',
                        'filename': f'analise_{ticker}',
                        'height': 600,
                        'width': 1200,
                        'scale': 1
                    },
                    'responsive': True
                }
            )
            
            return html_output
            
        except Exception as e:
            print(f"Erro ao criar gráfico MetaTrader: {e}")
            import traceback
            traceback.print_exc()
            return self.create_fallback_chart(df, ticker)

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
        print("=== DEBUG DOS DADOS DO GRÁFICO ===")
        print(f"Shape do DataFrame: {df.shape}")
        print(f"Colunas disponíveis: {df.columns.tolist()}")
        print(f"Index type: {type(df.index)}")
        print(f"Últimas 5 linhas:")
        print(df.tail())
        
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