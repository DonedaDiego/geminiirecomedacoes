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
        """Calcula os stops dinâmicos"""
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
        
        # Calcular ATR como percentual do preço
        df['ATR_Pct'] = atr_series / close_series
        
        # Calcular Stop Loss (limitado entre MIN_STOP e MAX_STOP)
        df['Stop_Loss'] = (df['ATR_Pct'] * self.ATR_FACTOR).clip(
            lower=self.MIN_STOP, 
            upper=self.MAX_STOP
        )
        
        # Calcular Take Profit (limitado entre MIN_TAKE e MAX_TAKE)
        df['Take_Profit'] = (vol_series * self.VOL_FACTOR).clip(
            lower=self.MIN_TAKE,
            upper=self.MAX_TAKE
        )
        
        print("Stops dinâmicos calculados com sucesso")
        return df

    def generate_predictions(self, df, model, scaler, features):
        """Gera as previsões e cores"""
        print("Gerando previsões...")
        
        X_scaled = scaler.transform(df[features])
        df['prediction'] = model.predict(X_scaled)
        
        # Aplicar cores baseadas nas previsões
        df['color'] = df['prediction'].apply(
            lambda x: self.cyberpunk_colors['neon_green'] if x == 1 else self.cyberpunk_colors['neon_red']
        )
        
        print("Previsões geradas")
        return df

    def create_chart(self, df, ticker, prediction_days):
        """Cria o gráfico interativo"""
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

            # Usar dados mais recentes para melhor performance
            recent_data = df.tail(252).copy()  # Último ano de dados
            
            # Converter index para string se for datetime
            if hasattr(recent_data.index, 'strftime'):
                recent_data.index = recent_data.index.strftime('%Y-%m-%d')

            # Criação do gráfico principal - Estilo MetaTrader
            fig = go.Figure()

            # Candlestick principal
            fig.add_trace(go.Candlestick(
                x=recent_data.index,
                open=recent_data['Open'],
                high=recent_data['High'],
                low=recent_data['Low'],
                close=recent_data['Close'],
                name='Preço',
                increasing_line_color='#00ff00',
                decreasing_line_color='#ff0000'
            ))

            # Linha de previsões coloridas
            buy_signals = recent_data[recent_data['prediction'] == 1]
            sell_signals = recent_data[recent_data['prediction'] == 0]

            # Pontos de compra
            if not buy_signals.empty:
                fig.add_trace(go.Scatter(
                    x=buy_signals.index,
                    y=buy_signals['Close'],
                    mode='markers',
                    marker=dict(
                        symbol='triangle-up',
                        size=10,
                        color='#00ff88',
                        line=dict(width=2, color='#ffffff')
                    ),
                    name='Sinal de COMPRA'
                ))

            # Pontos de venda
            if not sell_signals.empty:
                fig.add_trace(go.Scatter(
                    x=sell_signals.index,
                    y=sell_signals['Close'],
                    mode='markers',
                    marker=dict(
                        symbol='triangle-down',
                        size=10,
                        color='#ff4444',
                        line=dict(width=2, color='#ffffff')
                    ),
                    name='Sinal de VENDA'
                ))

            # Níveis atuais - Stop Loss e Take Profit
            last_date = recent_data.index[-1]
            
            if today_prediction == 1:
                # Take Profit linha
                fig.add_trace(go.Scatter(
                    x=[last_date, last_date],
                    y=[today_price, take_profit_price],
                    mode='lines',
                    line=dict(color='#00ff00', width=3, dash='dash'),
                    name=f'Take Profit: R$ {take_profit_price:.2f}',
                    showlegend=True
                ))
                
                # Stop Loss linha
                fig.add_trace(go.Scatter(
                    x=[last_date, last_date],
                    y=[today_price, stop_loss_price],
                    mode='lines',
                    line=dict(color='#ff0000', width=3, dash='dash'),
                    name=f'Stop Loss: R$ {stop_loss_price:.2f}',
                    showlegend=True
                ))

            # Layout estilo MetaTrader
            fig.update_layout(
                title=dict(
                    text=f'{ticker} - Análise Swing Trade ML | Previsão: {"COMPRA" if today_prediction == 1 else "VENDA"}',
                    font=dict(size=20, color='white'),
                    x=0.5
                ),
                template='plotly_dark',
                plot_bgcolor='#1a1a1a',
                paper_bgcolor='#1a1a1a',
                font=dict(color='white', size=12),
                height=600,
                showlegend=True,
                legend=dict(
                    bgcolor='rgba(26, 26, 26, 0.8)',
                    bordercolor='rgba(255, 255, 255, 0.2)',
                    borderwidth=1,
                    font=dict(size=11)
                ),
                margin=dict(l=50, r=50, t=80, b=50)
            )

            # Configurações dos eixos
            fig.update_xaxes(
                gridcolor='rgba(255, 255, 255, 0.1)',
                showgrid=True,
                rangeslider_visible=False,
                type='category'
            )
            
            fig.update_yaxes(
                gridcolor='rgba(255, 255, 255, 0.1)',
                showgrid=True,
                title_text="Preço (R$)",
                side='right'
            )

            # Anotações informativas
            fig.add_annotation(
                text=f"<b>Informações Atuais:</b><br>" +
                     f"Preço: R$ {today_price:.2f}<br>" +
                     f"ATR: {(current_atr/today_price*100):.2f}%<br>" +
                     f"Stop: {stop_loss*100:.1f}% | Take: {take_profit*100:.1f}%",
                xref="paper", yref="paper",
                x=0.02, y=0.98,
                showarrow=False,
                font=dict(size=10, color='white'),
                bgcolor='rgba(0, 0, 0, 0.7)',
                bordercolor='rgba(255, 255, 255, 0.3)',
                borderwidth=1,
                align='left'
            )

            print("Gráfico criado com sucesso")
            
            # Retornar HTML mais robusto
            config = {
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d'],
                'responsive': True
            }
            
            html_str = fig.to_html(
                include_plotlyjs='cdn',
                config=config,
                div_id="trading-chart"
            )
            
            return html_str
            
        except Exception as e:
            print(f"Erro ao criar gráfico: {e}")
            # Retornar gráfico simples em caso de erro
            return self.create_simple_chart(df, ticker)

    def create_simple_chart(self, df, ticker):
        """Cria um gráfico simples em caso de erro no principal"""
        print("Criando gráfico simples...")
        
        try:
            recent_data = df.tail(100)
            
            fig = go.Figure()
            
            # Linha simples de preços
            fig.add_trace(go.Scatter(
                x=list(range(len(recent_data))),
                y=recent_data['Close'].values,
                mode='lines',
                name='Preço',
                line=dict(color='#00aaff', width=2)
            ))
            
            # Sinais
            buy_points = recent_data[recent_data['prediction'] == 1]
            sell_points = recent_data[recent_data['prediction'] == 0]
            
            if not buy_points.empty:
                buy_indices = [list(recent_data.index).index(idx) for idx in buy_points.index]
                fig.add_trace(go.Scatter(
                    x=buy_indices,
                    y=buy_points['Close'].values,
                    mode='markers',
                    marker=dict(symbol='triangle-up', size=8, color='green'),
                    name='Compra'
                ))
            
            if not sell_points.empty:
                sell_indices = [list(recent_data.index).index(idx) for idx in sell_points.index]
                fig.add_trace(go.Scatter(
                    x=sell_indices,
                    y=sell_points['Close'].values,
                    mode='markers',
                    marker=dict(symbol='triangle-down', size=8, color='red'),
                    name='Venda'
                ))
            
            fig.update_layout(
                title=f'{ticker} - Análise Simplificada',
                template='plotly_dark',
                height=400,
                showlegend=True
            )
            
            return fig.to_html(include_plotlyjs='cdn', div_id="simple-chart")
            
        except Exception as e:
            print(f"Erro no gráfico simples: {e}")
            return f"<div style='color: white; padding: 20px;'>Erro ao gerar gráfico: {str(e)}</div>"

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