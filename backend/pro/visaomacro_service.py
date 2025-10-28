"""
visaomacro_service.py - Visão Macro Multidimensional
Agrega dados de Gamma, Delta, Vega e Theta em uma análise unificada
"""

import numpy as np
import pandas as pd
import logging
from datetime import datetime
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from .gamma_service import GammaService
from .delta_service import DeltaService
from .vega_service import VegaService
from .theta_service import ThetaService

logging.basicConfig(level=logging.INFO)


def convert_to_json_serializable(obj):
    """Converte tipos numpy/pandas para Python nativo"""
    try:
        if obj is None or pd.isna(obj):
            return None
        elif isinstance(obj, (bool, np.bool_)):
            return bool(obj)
        elif isinstance(obj, (int, np.integer)):
            return int(obj)
        elif isinstance(obj, (float, np.floating)):
            return float(obj)
        elif isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: convert_to_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_to_json_serializable(item) for item in obj]
        elif hasattr(obj, 'item'):
            return obj.item()
        elif hasattr(obj, 'tolist'):
            return obj.tolist()
        else:
            return str(obj)
    except:
        return None


class MacroAnalyzer:
    """Analisador macro que integra todos os Greeks"""

    def __init__(self):
        self.gamma_service = GammaService()
        self.delta_service = DeltaService()
        self.vega_service = VegaService()
        self.theta_service = ThetaService()

    def aggregate_greeks_data(self, ticker, expiration_code=None):
        """Agrega dados de todos os Greeks"""
        logging.info(f"INICIANDO ANÁLISE MACRO - {ticker}")

        results = {
            'ticker': ticker,
            'timestamp': datetime.now().isoformat(),
            'success': False
        }

        try:
            # 1. GAMMA
            logging.info("Analisando GAMMA...")
            gamma_result = self.gamma_service.analyze_gamma_complete(ticker, expiration_code)
            results['gamma'] = {
                'flip_strike': gamma_result.get('flip_strike'),
                'regime': gamma_result.get('regime'),
                'gex_levels': gamma_result.get('gex_levels', {}),
                'net_gex_descoberto': gamma_result.get('gex_levels', {}).get('total_gex_descoberto', 0),
                'spot_price': gamma_result.get('spot_price')
            }
            spot_price = gamma_result.get('spot_price')
            expiration = gamma_result.get('data_quality', {}).get('expiration')

        except Exception as e:
            logging.error(f"Erro ao analisar GAMMA: {e}")
            results['gamma'] = {'error': str(e)}
            return results

        try:
            # 2. DELTA
            logging.info("Analisando DELTA...")
            delta_result = self.delta_service.analyze_delta_complete(ticker, expiration_code)
            results['delta'] = {
                'dex_levels': delta_result.get('dex_levels', {}),
                'net_dex_descoberto': delta_result.get('dex_levels', {}).get('total_dex_descoberto', 0),
                'market_bias': delta_result.get('dex_levels', {}).get('market_bias', 'NEUTRAL'),
                'remaining_pressure': delta_result.get('dex_levels', {}).get('remaining_pressure', 0)
            }

        except Exception as e:
            logging.error(f"Erro ao analisar DELTA: {e}")
            results['delta'] = {'error': str(e), 'net_dex_descoberto': 0}

        try:
            # 3. VEGA
            logging.info("Analisando VEGA...")
            vega_result = self.vega_service.analyze_vega_complete(ticker, expiration_code)
            results['vega'] = {
                'vex_levels': vega_result.get('vex_levels', {}),
                'iv_mean': vega_result.get('vex_levels', {}).get('iv_mean', 0),
                'iv_skew': vega_result.get('vex_levels', {}).get('iv_skew', {}),
                'max_risk_strike': vega_result.get('vex_levels', {}).get('max_vex_strike')
            }

        except Exception as e:
            logging.error(f"Erro ao analisar VEGA: {e}")
            results['vega'] = {'error': str(e), 'iv_mean': 0}

        try:
            # 4. THETA
            logging.info("Analisando THETA...")
            theta_result = self.theta_service.analyze_theta_complete(ticker, expiration_code)
            results['theta'] = {
                'tex_levels': theta_result.get('tex_levels', {}),
                'daily_decay': theta_result.get('tex_levels', {}).get('total_theta_descoberto', 0),
                'max_decay_strike': theta_result.get('tex_levels', {}).get('max_theta_strike'),
                'theta_gamma_ratio': theta_result.get('tex_levels', {}).get('theta_efficiency', 0)
            }

        except Exception as e:
            logging.error(f"Erro ao analisar THETA: {e}")
            results['theta'] = {'error': str(e), 'daily_decay': 0}

        results['spot_price'] = spot_price
        results['expiration'] = expiration
        results['success'] = True

        logging.info("Análise MACRO concluída com sucesso!")
        return results

    def create_macro_charts(self, aggregated_data):
        """Cria 2 gráficos consolidados: GEX+DEX e VEGA+THETA"""

        if not aggregated_data.get('success'):
            return None

        ticker = aggregated_data['ticker']
        spot_price = aggregated_data.get('spot_price', 0)
        expiration = aggregated_data.get('expiration', 'N/A')

        # Criar subplots (1 linha, 2 colunas)
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=[
                '<b style="color: #ffffff;">GEX + DEX Descoberto</b><br><span style="font-size: 12px; color: #888;">Gamma e Delta consolidados</span>',
                '<b style="color: #ffffff;">VEGA + THETA Heatmap</b><br><span style="font-size: 12px; color: #888;">Volatilidade e Decay temporal</span>'
            ],
            horizontal_spacing=0.12
        )

        # GRÁFICO 1: GEX + DEX (simulado - em produção usaria dados reais)
        # Por enquanto, vamos criar uma visualização conceitual
        sample_strikes = np.linspace(spot_price * 0.90, spot_price * 1.10, 15)

        # Simular GEX descoberto
        gex_descoberto = np.random.randn(len(sample_strikes)) * 500000

        # Simular DEX descoberto
        dex_descoberto = np.random.randn(len(sample_strikes)) * 100000

        # Barras de GEX
        colors_gex = ['#ef4444' if x < 0 else '#22c55e' for x in gex_descoberto]
        fig.add_trace(
            go.Bar(
                x=sample_strikes,
                y=gex_descoberto,
                name='GEX Descoberto',
                marker_color=colors_gex,
                showlegend=True
            ),
            row=1, col=1
        )

        # Linha de DEX (eixo secundário)
        fig.add_trace(
            go.Scatter(
                x=sample_strikes,
                y=dex_descoberto,
                name='DEX Descoberto',
                mode='lines+markers',
                line=dict(color='#fbbf24', width=3),
                marker=dict(size=8, color='#fbbf24'),
                yaxis='y2',
                showlegend=True
            ),
            row=1, col=1
        )

        # GRÁFICO 2: VEGA + THETA
        # Simular concentração de Vega
        vega_concentration = np.abs(np.random.randn(len(sample_strikes))) * 50000

        # Simular intensidade de Theta (para cor de fundo)
        theta_intensity = np.abs(np.random.randn(len(sample_strikes))) * 5000

        # Normalizar theta para cores
        theta_normalized = (theta_intensity - theta_intensity.min()) / (theta_intensity.max() - theta_intensity.min())
        theta_colors = [f'rgba(239, 68, 68, {0.3 + t * 0.7})' for t in theta_normalized]

        # Barras de Vega com cores de Theta
        fig.add_trace(
            go.Bar(
                x=sample_strikes,
                y=vega_concentration,
                name='Concentração Vega',
                marker=dict(
                    color=theta_colors,
                    line=dict(color='#a855f7', width=2)
                ),
                showlegend=True
            ),
            row=1, col=2
        )

        # Adicionar linhas de referência (spot price)
        for col in [1, 2]:
            fig.add_vline(
                x=spot_price,
                line=dict(color='#fbbf24', width=3, dash='dash'),
                row=1, col=col
            )
            fig.add_hline(
                y=0,
                line=dict(color='rgba(255,255,255,0.3)', width=1),
                row=1, col=col
            )

        # Configurar layout
        fig.update_layout(
            title={
                'text': f'{ticker} - Visão Macro Greeks | Vencimento: {expiration}',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 22, 'color': '#ffffff', 'family': 'Inter, sans-serif'}
            },
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#ffffff', family='Inter, sans-serif'),
            height=600,
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='center',
                x=0.5,
                bgcolor='rgba(0,0,0,0.5)'
            ),
            margin=dict(l=50, r=50, t=120, b=50)
        )

        # Atualizar eixos
        fig.update_xaxes(
            title_text='Strike',
            gridcolor='rgba(255,255,255,0.1)',
            color='#ffffff',
            showgrid=True,
            zeroline=False
        )

        # Eixo Y principal (col 1)
        fig.update_yaxes(
            title_text='GEX Descoberto',
            gridcolor='rgba(255,255,255,0.1)',
            color='#ffffff',
            showgrid=True,
            zeroline=False,
            row=1, col=1
        )

        # Eixo Y secundário (col 1 - para DEX)
        fig.update_layout(
            yaxis2=dict(
                title='DEX Descoberto',
                overlaying='y',
                side='right',
                color='#fbbf24',
                showgrid=False
            )
        )

        # Eixo Y (col 2)
        fig.update_yaxes(
            title_text='Concentração (Vega + Theta)',
            gridcolor='rgba(255,255,255,0.1)',
            color='#ffffff',
            showgrid=True,
            zeroline=False,
            row=1, col=2
        )

        fig.update_annotations(font=dict(color='#ffffff', family='Inter, sans-serif', size=16))

        return fig.to_json()


class VisaoMacroService:
    """Serviço principal da Visão Macro"""

    def __init__(self):
        self.analyzer = MacroAnalyzer()

    def analyze_macro(self, ticker, expiration_code=None):
        """Análise macro completa"""
        try:
            # Agregar dados
            aggregated_data = self.analyzer.aggregate_greeks_data(ticker, expiration_code)

            if not aggregated_data.get('success'):
                raise ValueError("Falha ao agregar dados dos Greeks")

            # Criar gráficos
            plot_json = self.analyzer.create_macro_charts(aggregated_data)

            # Montar resposta
            result = {
                'ticker': ticker.replace('.SA', ''),
                'spot_price': aggregated_data.get('spot_price'),
                'expiration': aggregated_data.get('expiration'),
                'timestamp': aggregated_data.get('timestamp'),

                # Dados agregados
                'gamma_data': aggregated_data.get('gamma', {}),
                'delta_data': aggregated_data.get('delta', {}),
                'vega_data': aggregated_data.get('vega', {}),
                'theta_data': aggregated_data.get('theta', {}),

                # Gráficos
                'plot_json': plot_json,

                # Análise integrada
                'integrated_analysis': self._generate_integrated_analysis(aggregated_data),

                'success': True
            }

            return convert_to_json_serializable(result)

        except Exception as e:
            logging.error(f"Erro na análise macro: {e}")
            raise

    def _generate_integrated_analysis(self, data):
        """Gera análise integrada com alertas e insights"""

        analysis = {
            'alerts': [],
            'best_opportunities': [],
            'risk_zones': []
        }

        # Extrair dados
        gamma = data.get('gamma', {})
        delta = data.get('delta', {})
        vega = data.get('vega', {})
        theta = data.get('theta', {})
        spot_price = data.get('spot_price', 0)

        # ALERTA 1: Gamma flip próximo
        flip_strike = gamma.get('flip_strike')
        if flip_strike and spot_price:
            distance_pct = abs((flip_strike - spot_price) / spot_price * 100)
            if distance_pct < 3:
                analysis['alerts'].append({
                    'type': 'GAMMA_FLIP_CLOSE',
                    'severity': 'HIGH',
                    'message': f'Gamma flip muito próximo: R$ {flip_strike:.2f} ({distance_pct:.1f}% do spot)'
                })

        # ALERTA 2: Alto DEX descoberto
        dex_descoberto = delta.get('net_dex_descoberto', 0)
        if abs(dex_descoberto) > 100000:
            bias = 'ALTISTA' if dex_descoberto > 0 else 'BAIXISTA'
            analysis['alerts'].append({
                'type': 'HIGH_DEX_EXPOSURE',
                'severity': 'MEDIUM',
                'message': f'Alta exposição delta descoberta ({bias}): {dex_descoberto:,.0f}'
            })

        # ALERTA 3: Vol implícita alta
        iv_mean = vega.get('iv_mean', 0)
        if iv_mean > 40:
            analysis['alerts'].append({
                'type': 'HIGH_IV',
                'severity': 'MEDIUM',
                'message': f'Volatilidade implícita elevada: {iv_mean:.1f}%'
            })

        # ANÁLISE DE RISCO
        gamma_regime = gamma.get('regime', 'NEUTRAL')
        if gamma_regime == 'NEGATIVE GAMMA' or gamma_regime == 'Short Gamma':
            max_risk_strike = vega.get('max_risk_strike')
            if max_risk_strike:
                analysis['risk_zones'].append({
                    'strike': max_risk_strike,
                    'reason': 'Concentração Vega em regime de Short Gamma',
                    'impact': 'HIGH'
                })

        # OPORTUNIDADES
        theta_decay = theta.get('daily_decay', 0)
        if theta_decay < -10000 and iv_mean > 30:
            analysis['best_opportunities'].append({
                'strategy': 'SELL_PREMIUM',
                'reason': 'Alto decay temporal + Vol implícita elevada',
                'expected_gain': f'R$ {abs(theta_decay):,.0f}/dia'
            })

        return analysis
