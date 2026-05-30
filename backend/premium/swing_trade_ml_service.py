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
        self.cyberpunk_colors = {
            'neon_green': 'rgba(0, 255, 170, 0.8)',
            'neon_red': 'rgba(255, 50, 50, 0.8)',
            'neon_blue': 'rgba(0, 191, 255, 0.8)',
            'neon_purple': 'rgba(148, 0, 211, 0.8)',
            'neon_pink': 'rgba(255, 0, 127, 0.8)',
            'neon_orange': 'rgba(255, 165, 0, 0.8)',
            'gray': 'rgba(150, 150, 150, 0.4)'
        }

        # Stops calibrados para ações B3 (alta volatilidade intradía)
        self.ATR_FACTOR = 2.0
        self.VOL_FACTOR = 2.5
        self.MIN_STOP = 0.03   # 3% mínimo — ações B3 movem isso em 1 dia
        self.MAX_STOP = 0.08   # 8% máximo
        self.MIN_TAKE = 0.06   # 6% mínimo
        self.MAX_TAKE = 0.25   # 25% máximo
        self.MIN_RR_RATIO = 1.5  # Take Profit deve ser >= 1.5x Stop Loss

    def normalize_yfinance_data(self, df):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Colunas básicas não encontradas: {missing_cols}")
        return df

    def download_data(self, ticker, years_back=10, start_date=None, end_date=None):
        try:
            ticker_symbol = ticker.upper() + ".SA" if not ticker.endswith('.SA') else ticker.upper()
            print(f"Baixando dados para {ticker_symbol}...")

            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=years_back * 365)).strftime('%Y-%m-%d')

            print(f"Período: {start_date} até {end_date}")

            df = yf.download(ticker_symbol, start=start_date, end=end_date, progress=False)

            if df.empty:
                raise ValueError(f"Nenhum dado encontrado para {ticker_symbol}")

            df = self.normalize_yfinance_data(df)
            print(f"Dados baixados: {len(df)} registros")
            return df, ticker_symbol

        except Exception as e:
            raise Exception(f"Erro ao baixar dados: {str(e)}")

    def calculate_indicators(self, df, prediction_days):
        print("Calculando indicadores técnicos...")

        if 'Close' not in df.columns:
            raise ValueError("Coluna 'Close' não encontrada nos dados")

        # RSI 14 períodos
        delta = df['Close'].diff(1)
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        df['RSI'] = np.clip(100 - (100 / (1 + rs)), 0, 100)

        # Estocástico K 14 períodos
        low_14 = df['Low'].rolling(window=14).min()
        high_14 = df['High'].rolling(window=14).max()
        denom_14 = (high_14 - low_14).replace(0, 1e-10)
        df['stochastic_k'] = np.clip(100 * (df['Close'] - low_14) / denom_14, 0, 100)

        # Williams %R
        df['Williams_%R'] = np.clip((high_14 - df['Close']) / (denom_14 + 1e-10) * -100, -100, 0)

        # PROC — Price Rate of Change 14 dias
        close_14 = df['Close'].shift(14)
        df['PROC'] = np.clip((df['Close'] - close_14) / (close_14 + 1e-10) * 100, -50, 50)

        # Posição no range anual (normalizado entre -1 e 1)
        high_252 = df['High'].rolling(window=252).max()
        low_252 = df['Low'].rolling(window=252).min()
        mid_252 = (high_252 + low_252) / 2
        range_252 = (high_252 - low_252).replace(0, 1e-10)
        df['Z_Score'] = np.clip((df['Close'] - mid_252) / range_252, -1, 1)

        # Largura das Bandas de Bollinger (volatilidade relativa)
        roll_mean = df['Close'].rolling(window=20).mean()
        roll_std = df['Close'].rolling(window=20).std()
        df['Volatility'] = np.clip(
            (4 * roll_std) / (roll_mean + 1e-10), 0, 0.5
        )

        # ATR 14 períodos
        df['HL'] = df['High'] - df['Low']
        df['HC'] = abs(df['High'] - df['Close'].shift(1))
        df['LC'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['HL', 'HC', 'LC']].max(axis=1)
        df['ATR'] = df['TR'].rolling(window=14).mean()
        df.drop(['HL', 'HC', 'LC'], axis=1, inplace=True)

        # Volatilidade realizada 60 dias
        df['Daily_Returns'] = df['Close'].pct_change()
        df['Volatility_60_Pct'] = np.clip(
            df['Daily_Returns'].rolling(window=60).std(), 0, 0.15
        )

        # MACD Histograma (normalizado pelo preço)
        ema12 = df['Close'].ewm(span=12).mean()
        ema26 = df['Close'].ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        df['MACD_Hist'] = np.clip(
            (macd_line - signal_line) / (df['Close'] + 1e-10) * 100, -5, 5
        )

        # Razão EMA20/EMA50 — tendência de médio prazo
        ema20 = df['Close'].ewm(span=20).mean()
        ema50 = df['Close'].ewm(span=50).mean()
        df['EMA_Ratio'] = np.clip((ema20 / (ema50 + 1e-10)) - 1, -0.15, 0.15)

        # Volume relativo à média de 20 dias
        vol_ma20 = df['Volume'].rolling(20).mean()
        df['Volume_Ratio'] = np.clip(
            df['Volume'] / (vol_ma20 + 1e-10) - 1, -1, 5
        )

        # Momentum do RSI (slope de 3 dias) — aceleração do oscilador
        df['RSI_Slope'] = np.clip(df['RSI'].diff(3), -20, 20)

        # Target binário: preço sobe em prediction_days?
        df['target'] = np.where(df['Close'].shift(-prediction_days) > df['Close'], 1, 0)

        # Limpeza final
        all_features = [
            'RSI', 'stochastic_k', 'Williams_%R', 'PROC', 'Z_Score',
            'Volatility', 'ATR', 'Volatility_60_Pct',
            'MACD_Hist', 'EMA_Ratio', 'Volume_Ratio', 'RSI_Slope'
        ]
        for col in all_features:
            if col in df.columns:
                df[col] = df[col].replace([np.inf, -np.inf], np.nan).ffill()

        print("Indicadores calculados com sucesso")
        return df

    def prepare_model_data(self, df):
        # Features: osciladores + tendência + volume + momentum do RSI
        # Smoothed_Close removido — era basicamente o preço atual, criava
        # correlação espúria com o target (preço futuro)
        features = [
            'RSI',          # oscilador de momentum
            'stochastic_k', # estocástico
            'Williams_%R',  # oscilador de range
            'PROC',         # variação percentual 14d
            'Z_Score',      # posição no range anual
            'Volatility',   # largura Bollinger normalizada
            'MACD_Hist',    # momentum de tendência
            'EMA_Ratio',    # direção da tendência (EMA20 vs EMA50)
            'Volume_Ratio', # confirmação por volume
            'RSI_Slope',    # aceleração do RSI
        ]

        missing_features = [f for f in features if f not in df.columns]
        if missing_features:
            raise ValueError(f"Features não encontradas: {missing_features}")

        print("Limpando dados...")
        df_clean = df.replace([np.inf, -np.inf], np.nan).dropna()
        print(f"Shape após limpeza básica: {df_clean.shape}")

        # Remover outliers extremos (z-score > 10) — apenas limpeza de dados corrompidos
        for feature in features:
            std = df_clean[feature].std()
            if std > 0:
                z = np.abs((df_clean[feature] - df_clean[feature].mean()) / std)
                outliers = z > 10
                if outliers.sum() > 0:
                    print(f"Removendo {outliers.sum()} outliers de {feature}")
                    df_clean = df_clean[~outliers]

        print(f"Shape final: {df_clean.shape}")

        X = df_clean[features].copy()
        y = df_clean['target'].copy()

        for feature in features:
            if X[feature].isna().any() or np.isinf(X[feature]).any():
                raise ValueError(f"Feature {feature} ainda contém valores inválidos após limpeza")
            if X[feature].std() == 0:
                print(f"AVISO: {feature} tem variação zero")

        if len(X) < 100:
            raise ValueError(f"Dados insuficientes após limpeza: {len(X)} amostras")
        if len(np.unique(y)) < 2:
            raise ValueError("Target sem variação suficiente")

        print(f"Dados preparados: {len(X)} amostras, {len(features)} features")
        print(f"Distribuição do target: {np.bincount(y)}")
        return X, y, features

    def train_model(self, X, y):
        print("Treinando modelo ensemble...")

        # shuffle=False é OBRIGATÓRIO para séries temporais:
        # com shuffle=True, dados futuros vazam para o treino (look-ahead bias)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, shuffle=False
        )

        if len(np.unique(y_train)) < 2:
            raise ValueError("Dados insuficientes — sem variação nos targets")

        smote = SMOTE(random_state=42)
        X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_resampled)
        X_test_scaled = scaler.transform(X_test)

        # RandomForest: depth reduzida para evitar overfitting
        # max_depth=13 anterior memorizava o treino sem generalizar
        rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            min_samples_split=10,
            min_samples_leaf=4,
            max_features='sqrt',
            bootstrap=True,
            random_state=42
        )

        # XGBoost: learning_rate menor + regularização explícita
        xgb_model = XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.05,
            colsample_bytree=0.7,
            subsample=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            min_child_weight=5,
            random_state=42,
            eval_metric='logloss'
        )

        # soft voting usa as probabilidades dos dois modelos — mais preciso que hard
        ensemble_model = VotingClassifier(
            estimators=[('rf', rf_model), ('xgb', xgb_model)],
            voting='soft'
        )

        ensemble_model.fit(X_train_scaled, y_train_resampled)

        y_pred = ensemble_model.predict(X_test_scaled)

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

        print(f"Modelo treinado — Acurácia: {accuracy:.3f} | Precisão: {precision:.3f} | Recall: {recall:.3f}")
        return ensemble_model, scaler, metrics

    def calculate_dynamic_stops(self, df):
        print("Calculando stops dinâmicos...")

        required_cols = ['ATR', 'Close', 'Volatility_60_Pct']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Colunas não encontradas: {missing_cols}")

        atr_series = df['ATR'].iloc[:, 0] if isinstance(df['ATR'], pd.DataFrame) else df['ATR']
        close_series = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        vol_series = df['Volatility_60_Pct'].iloc[:, 0] if isinstance(df['Volatility_60_Pct'], pd.DataFrame) else df['Volatility_60_Pct']

        df['ATR_Pct'] = atr_series / close_series

        df['Stop_Loss'] = df.apply(
            lambda x: min(max(x['ATR_Pct'] * self.ATR_FACTOR, self.MIN_STOP), self.MAX_STOP),
            axis=1
        )
        df['Take_Profit'] = df.apply(
            lambda x: min(max(x['Volatility_60_Pct'] * self.VOL_FACTOR, self.MIN_TAKE), self.MAX_TAKE),
            axis=1
        )

        # Garantir relação risco/retorno mínima de 1.5:1
        df['Take_Profit'] = df.apply(
            lambda x: max(x['Take_Profit'], x['Stop_Loss'] * self.MIN_RR_RATIO),
            axis=1
        ).clip(upper=self.MAX_TAKE)

        print("Stops dinâmicos calculados com sucesso")
        return df

    def generate_predictions(self, df, model, scaler, features):
        print("Gerando previsões...")

        X_pred = df[features].copy()
        X_pred = X_pred.replace([np.inf, -np.inf], np.nan).ffill().bfill()

        for feature in features:
            if X_pred[feature].isna().any():
                X_pred[feature] = X_pred[feature].fillna(X_pred[feature].median())
            if np.isinf(X_pred[feature]).any():
                X_pred[feature] = np.clip(
                    X_pred[feature],
                    X_pred[feature].quantile(0.01),
                    X_pred[feature].quantile(0.99)
                )

        try:
            X_scaled = scaler.transform(X_pred)
            if np.isnan(X_scaled).any() or np.isinf(X_scaled).any():
                raise ValueError("Dados escalados contêm valores inválidos")
            predictions = model.predict(X_scaled)
            df['prediction'] = predictions
        except Exception as e:
            print(f"Erro na predição: {e}")
            # Fallback conservador: sinal neutro/venda em vez de ruído aleatório
            df['prediction'] = 0
            print("Aviso: usando fallback conservador (prediction=0) por falha no modelo")

        df['color'] = np.where(
            df['prediction'] == 1,
            self.cyberpunk_colors['neon_green'],
            self.cyberpunk_colors['neon_red']
        )

        print("Previsões geradas com sucesso")
        return df

    def create_chart(self, df, ticker, prediction_days):
        """Gráfico principal com sinais de compra/venda e níveis de TP/SL"""
        print("Criando gráfico de análise...")

        try:
            recent = df.tail(252).copy()

            last_price = float(recent['Close'].iloc[-1])
            last_pred = int(recent['prediction'].iloc[-1])
            last_sl = float(recent['Stop_Loss'].iloc[-1])
            last_tp = float(recent['Take_Profit'].iloc[-1])

            tp_price = last_price * (1 + last_tp) if last_pred == 1 else last_price * (1 - last_tp)
            sl_price = last_price * (1 - last_sl) if last_pred == 1 else last_price * (1 + last_sl)

            fig = go.Figure()

            # Linha de preço principal
            fig.add_trace(go.Scatter(
                x=recent.index,
                y=recent['Close'],
                mode='lines',
                name='Preço',
                line=dict(color=self.cyberpunk_colors['neon_blue'], width=1.5)
            ))

            # Sinais de compra
            buy_idx = recent[recent['prediction'] == 1]
            if not buy_idx.empty:
                fig.add_trace(go.Scatter(
                    x=buy_idx.index,
                    y=buy_idx['Close'],
                    mode='markers',
                    name='COMPRA',
                    marker=dict(
                        symbol='triangle-up',
                        size=7,
                        color=self.cyberpunk_colors['neon_green'],
                        line=dict(width=1, color='white')
                    )
                ))

            # Sinais de venda
            sell_idx = recent[recent['prediction'] == 0]
            if not sell_idx.empty:
                fig.add_trace(go.Scatter(
                    x=sell_idx.index,
                    y=sell_idx['Close'],
                    mode='markers',
                    name='VENDA',
                    marker=dict(
                        symbol='triangle-down',
                        size=7,
                        color=self.cyberpunk_colors['neon_red'],
                        line=dict(width=1, color='white')
                    )
                ))

            # Linhas horizontais de TP e SL para o sinal atual
            fig.add_hline(
                y=tp_price,
                line=dict(color='rgba(0,255,100,0.6)', dash='dash', width=1.5),
                annotation_text=f"TP {tp_price:.2f} (+{last_tp*100:.1f}%)",
                annotation_position="right"
            )
            fig.add_hline(
                y=sl_price,
                line=dict(color='rgba(255,80,80,0.6)', dash='dash', width=1.5),
                annotation_text=f"SL {sl_price:.2f} (-{last_sl*100:.1f}%)",
                annotation_position="right"
            )

            direction_label = "COMPRA" if last_pred == 1 else "VENDA"
            fig.update_layout(
                title=dict(
                    text=f'{ticker} — Swing Trade ML | Sinal: {direction_label}',
                    font=dict(size=16)
                ),
                template='plotly_dark',
                autosize=True,
                showlegend=True,
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                xaxis_title='Data',
                yaxis_title='Preço (R$)',
                margin=dict(r=100)
            )

            html_output = fig.to_html(include_plotlyjs='cdn', config={'responsive': True})
            print(f"Gráfico gerado — {len(html_output)} chars")
            return html_output

        except Exception as e:
            print(f"Erro no gráfico: {e}")
            return self.create_fallback_chart(df, ticker)

    def create_fallback_chart(self, df, ticker):
        """Gráfico de emergência simples"""
        print("Criando gráfico de emergência...")
        try:
            recent_data = df.tail(100).copy()
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                y=recent_data['Close'].values,
                mode='lines',
                name='Preço',
                line=dict(color='#00aaff', width=2)
            ))

            buy_mask = recent_data['prediction'] == 1 if 'prediction' in recent_data.columns else pd.Series(False, index=recent_data.index)
            sell_mask = ~buy_mask

            for i, (idx, row) in enumerate(recent_data.iterrows()):
                if 'prediction' in row and row['prediction'] == 1:
                    fig.add_trace(go.Scatter(
                        x=[i], y=[row['Close']],
                        mode='markers',
                        marker=dict(symbol='triangle-up', size=8, color='green'),
                        showlegend=False
                    ))
                elif 'prediction' in row:
                    fig.add_trace(go.Scatter(
                        x=[i], y=[row['Close']],
                        mode='markers',
                        marker=dict(symbol='triangle-down', size=8, color='red'),
                        showlegend=False
                    ))

            fig.update_layout(
                title=f'{ticker} — Análise',
                template='plotly_dark',
                height=400,
                xaxis_title="Período",
                yaxis_title="Preço"
            )
            return fig.to_html(include_plotlyjs='cdn', div_id="fallback-chart")

        except Exception as e:
            print(f"Erro no gráfico de emergência: {e}")
            return f"<div style='color:white;padding:20px;'>Erro ao gerar gráfico: {str(e)}</div>"

    def get_analysis_data(self, df, ticker, prediction_days, metrics):
        """Retorna os dados para análise em cards"""
        print("Preparando dados de análise...")

        today_price = df['Close'].iloc[-1]
        today_prediction = df['prediction'].iloc[-1]
        current_atr = df['ATR'].iloc[-1]
        current_vol = df['Volatility_60_Pct'].iloc[-1]

        stop_loss = min(max(current_atr / today_price * self.ATR_FACTOR, self.MIN_STOP), self.MAX_STOP)
        take_profit = min(max(current_vol * self.VOL_FACTOR, self.MIN_TAKE), self.MAX_TAKE)
        # Aplicar R/R mínimo
        take_profit = max(take_profit, stop_loss * self.MIN_RR_RATIO)
        take_profit = min(take_profit, self.MAX_TAKE)

        if today_prediction == 1:
            take_profit_price = today_price * (1 + take_profit)
            stop_loss_price = today_price * (1 - stop_loss)
        else:
            take_profit_price = today_price * (1 - take_profit)
            stop_loss_price = today_price * (1 + stop_loss)

        historical_date = df.index[-prediction_days]
        historical_price = df['Close'].iloc[-prediction_days]
        historical_prediction = df['prediction'].iloc[-prediction_days]

        if historical_prediction == 1:
            resultado_historico = ((today_price - historical_price) / historical_price * 100)
        else:
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
            'rr_ratio': float(round(take_profit / stop_loss, 2)),
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

        rr = take_profit / stop_loss if stop_loss > 0 else 0

        analysis_text = f"""
{'='*70}
ANÁLISE DE TRADING — {ticker}
{'='*70}
Data atual : {datetime.now().strftime('%Y-%m-%d')}
Preço atual: {today_price:.2f}
Direção    : {'COMPRA' if today_prediction == 1 else 'VENDA'}
{'-'*70}
NÍVEIS DE OPERAÇÃO:
Take Profit: {take_profit_price:.2f} (+{take_profit*100:.1f}%)
Stop Loss  : {stop_loss_price:.2f} (-{stop_loss*100:.1f}%)
R/R Ratio  : {rr:.2f}:1
{'-'*70}
MÉTRICAS DE VOLATILIDADE:
ATR atual     : {current_atr:.4f} ({(current_atr/today_price*100):.2f}% do preço)
ATR médio     : {(df['ATR'].mean()/df['Close'].mean()*100):.2f}%
Volatilidade 60d : {(current_vol*100):.2f}%
Vol máxima 60d   : {(df['Volatility_60_Pct'].max()*100):.2f}%
{'-'*70}
DESEMPENHO DO STOP DINÂMICO:
Stop Loss médio   : {(df['Stop_Loss'].mean()*100):.2f}%
Take Profit médio : {(df['Take_Profit'].mean()*100):.2f}%
{'-'*70}
ANÁLISE HISTÓRICA:
Data histórica  : {historical_date.strftime('%Y-%m-%d')}
Preço histórico : {historical_price:.2f}
Preço atual     : {today_price:.2f}
Sinal histórico : {'COMPRA' if historical_prediction == 1 else 'VENDA'}
"""
        if historical_prediction == 1:
            analysis_text += f"Resultado (Compra): {resultado_historico:.2f}% {'LUCRO' if resultado_historico > 0 else 'PREJUÍZO'}\n"
        else:
            analysis_text += f"Resultado (Venda): {resultado_historico:.2f}% {'LUCRO' if resultado_historico > 0 else 'PREJUÍZO'}\n"

        analysis_text += f"Preço {'subiu' if variacao_percentual > 0 else 'caiu'} {abs(variacao_percentual):.2f}% desde a previsão\n"
        analysis_text += f"{'-'*70}\n"

        return analysis_text

    def debug_chart_data(self, df):
        required_cols = ['Open', 'High', 'Low', 'Close', 'prediction']
        for col in required_cols:
            status = "✓" if col in df.columns else "✗"
            print(f"{status} {col}: {'OK' if col in df.columns else 'FALTANDO'}")
        return True

    def run_analysis(self, ticker, prediction_days, years_back=10):
        try:
            print(f"=== INICIANDO ANÁLISE SWING TRADE ML ===")
            print(f"Ticker: {ticker}, Dias: {prediction_days}")

            df, ticker_symbol = self.download_data(ticker, years_back=years_back)

            if len(df) < 300:
                raise ValueError(f"Dados insuficientes: {len(df)} registros (mínimo 300)")

            df = self.calculate_indicators(df, prediction_days)
            X, y, features = self.prepare_model_data(df)
            model, scaler, metrics = self.train_model(X, y)
            df = self.calculate_dynamic_stops(df)
            df = self.generate_predictions(df, model, scaler, features)

            self.debug_chart_data(df)

            chart_html = self.create_chart(df, ticker_symbol, prediction_days)

            if not chart_html or len(chart_html) < 100:
                print("HTML muito pequeno — usando fallback chart")
                chart_html = self.create_fallback_chart(df, ticker_symbol)

            analysis_data = self.get_analysis_data(df, ticker_symbol, prediction_days, metrics)

            print("=== ANÁLISE CONCLUÍDA COM SUCESSO ===")

            return {
                'success': True,
                'chart_html': chart_html,
                'analysis_data': analysis_data,
                'dataframe': df,
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
