"""
mm_temporal_service.py - Market Maker Temporal Analysis
Análise da evolução histórica das posições descobertas dos market makers
"""

import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta
import warnings
import logging
import os
from dotenv import load_dotenv
from plotly.subplots import make_subplots
import plotly.graph_objects as go

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
load_dotenv()

def convert_to_json_serializable(obj):
    """Conversão corrigida que lida com tuplas como chaves"""
    try:
        if obj is None or pd.isna(obj):
            return None
        elif isinstance(obj, dict):
            # SOLUÇÃO: Converte tuplas-chave para strings
            new_dict = {}
            for key, value in obj.items():
                if isinstance(key, tuple):
                    # Converte (140.0, 'CALL') para "140.0_CALL"
                    str_key = f"{key[0]}_{key[1]}"
                    new_dict[str_key] = convert_to_json_serializable(value)
                else:
                    new_dict[str(key)] = convert_to_json_serializable(value)
            return new_dict
        elif isinstance(obj, (list, tuple)):
            return [convert_to_json_serializable(item) for item in obj]
        elif isinstance(obj, (bool, np.bool_)):
            return bool(obj)
        elif isinstance(obj, (int, np.integer)):
            return int(obj)
        elif isinstance(obj, (float, np.floating)):
            return float(obj)
        elif isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        elif hasattr(obj, 'item'):
            return obj.item()
        elif hasattr(obj, 'tolist'):
            return obj.tolist()
        else:
            return str(obj)
    except:
        return None

class BusinessDayManager:
    """
    Gerencia a lógica de dias úteis para análise temporal
    """
    
    def __init__(self):
        # Mapeamento de vencimentos disponíveis
        self.available_expirations = {
            "20250919": datetime(2025, 9, 19).date(),
            "20251017": datetime(2025, 10, 17).date(), 
            "20251121": datetime(2025, 11, 21).date(),
            "20251219": datetime(2025, 12, 19).date(),
            "20260116": datetime(2026, 1, 16).date(),
        }
    
    @staticmethod
    def get_business_days(days_needed=5):
        """
        Coleta exatamente 'days_needed' dias úteis anteriores
        """
        dates = []
        current_date = datetime.now().date()
        i = 1  # Começa de ontem, não hoje (dados sempre são D-1)
        
        logging.info(f"Coletando {days_needed} dias úteis a partir de {current_date}")
        
        # Coleta até 20 dias atrás para garantir dias úteis suficientes
        while len(dates) < days_needed and i <= 20:
            check_date = current_date - timedelta(days=i)
            
            # Segunda=0 até Sexta=4 (weekday() retorna 0-6)
            if check_date.weekday() < 5:
                dates.append(check_date.strftime('%Y-%m-%d'))
                logging.info(f"Adicionado dia útil: {check_date.strftime('%Y-%m-%d')} (D-{i})")
            else:
                logging.debug(f"Pulando fim de semana: {check_date.strftime('%Y-%m-%d')}")
            
            i += 1
        
        if len(dates) < days_needed:
            logging.warning(f"Só foi possível coletar {len(dates)} dias úteis dos {days_needed} solicitados")
        
        # Retorna em ordem cronológica (mais antigo primeiro)
        final_dates = list(reversed(dates))
        logging.info(f"Dias úteis finais para análise: {final_dates}")
        
        return final_dates
    
    def get_expiration_for_date(self, date_str):
        """
        Mapeia data histórica para código de vencimento válido naquela época
        
        Args:
            date_str: Data no formato 'YYYY-MM-DD'
            
        Returns:
            str: Código do vencimento mais apropriado para aquela data
        """
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Encontra o vencimento mais próximo que estava ativo naquela data
            # Lógica: usar o vencimento mais próximo que não tinha expirado ainda
            valid_expirations = []
            
            for code, expiry_date in self.available_expirations.items():
                # Se a data histórica é anterior à data de vencimento, esse vencimento era válido
                if date_obj <= expiry_date:
                    days_until_expiry = (expiry_date - date_obj).days
                    valid_expirations.append((code, days_until_expiry))
            
            if not valid_expirations:
                # Se nenhum vencimento válido encontrado, usa o mais próximo disponível
                logging.warning(f"Nenhum vencimento válido para {date_str}, usando fallback")
                return "20251017"  # Fallback padrão
            
            # Ordena por dias até vencimento e pega o mais próximo (mas não muito próximo)
            valid_expirations.sort(key=lambda x: x[1])
            
            # Prefere vencimentos com pelo menos 7 dias até expirar
            for code, days_until in valid_expirations:
                if days_until >= 7:
                    logging.info(f"Selecionado vencimento {code} para {date_str} ({days_until} dias até vencer)")
                    return code
            
            # Se todos estão muito próximos do vencimento, pega o que tem mais tempo
            selected_code = valid_expirations[-1][0]
            logging.info(f"Usando vencimento {selected_code} para {date_str} (último recurso)")
            return selected_code
            
        except Exception as e:
            logging.error(f"Erro ao determinar vencimento para {date_str}: {e}")
            return "20251017"  # Fallback em caso de erro

class HistoricalDataProvider:
    """
    Provedor de dados históricos do Floqui com formato de URL correto
    """
    
    def __init__(self):
        self.cache = {}
        
    def get_oi_breakdown_for_date(self, symbol, date_str, expiration_code):
        """Versão SIMPLIFICADA como no GammaService"""
        cache_key = f"{symbol}_{date_str}_{expiration_code}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # URL e request
            dt_formatada = date_str.replace('-', '')
            url = f"https://floqui.com.br/api/posicoes_em_aberto/{symbol.lower()}/{expiration_code}/{dt_formatada}"
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                return {}
            
            data = response.json()
            if not data:
                return {}
            
            # PROCESSAMENTO IDÊNTICO AO GAMMA SERVICE
            oi_breakdown = {}
            for item in data:
                strike = float(item.get('preco_exercicio', 0))
                option_type = item.get('tipo_opcao', '').upper()
                oi_total = int(item.get('qtd_total', 0))
                oi_descoberto = int(item.get('qtd_descoberto', 0))
                
                if strike > 0 and oi_total > 0:
                    # CHAVE IDÊNTICA AO GAMMA SERVICE
                    key = (strike, 'CALL' if option_type == 'CALL' else 'PUT')
                    oi_breakdown[key] = {
                        'total': oi_total,
                        'descoberto': oi_descoberto,
                        'travado': int(item.get('qtd_trava', 0)),
                        'coberto': int(item.get('qtd_coberto', 0)),
                        'data': date_str
                    }
            
            # Cache sem conversões adicionais
            self.cache[cache_key] = oi_breakdown
            return oi_breakdown
            
        except Exception as e:
            logging.error(f"Erro: {e}")
            return {}

class TemporalMetricsCalculator:
   
    def __init__(self):
        pass
    
    def _normalize_strike_key(self, strike, option_type):
        """Normaliza chave de strike para garantir consistência de tipos"""
        try:
            strike_float = float(strike)
            option_str = str(option_type).strip().upper()
            return (strike_float, option_str)
        except (ValueError, TypeError):
            logging.warning(f"Erro normalizando chave: strike={strike}, type={option_type}")
            return None

    def _get_validated_strikes(self, data_dict):
        """Retorna apenas strikes com chaves válidas e normalizadas"""
        validated = {}
        for key, value in data_dict.items():
            if isinstance(key, tuple) and len(key) == 2:
                normalized_key = self._normalize_strike_key(key[0], key[1])
                if normalized_key:
                    validated[normalized_key] = value
        return validated
    
    
    def calculate_descoberto_context(self, historical_data, current_data):
        """Contexto Histórico dos Descobertos - VERSÃO CORRIGIDA"""
        context = {}
        
        try:
            # Coleta strikes sem validação desnecessária
            all_strikes = set()
            
            for data_dict in historical_data.values():
                all_strikes.update(data_dict.keys())
            
            all_strikes.update(current_data.keys())
            
            logging.info(f"Processando contexto para {len(all_strikes)} strikes únicos")
            
            for strike_key in all_strikes:
                # REMOVE VALIDAÇÃO QUE CAUSAVA WARNING
                # As chaves (140.0, 'CALL') são perfeitamente válidas
                
                try:
                    historical_values = []
                    
                    # Coleta valores históricos
                    for date, data_dict in historical_data.items():
                        if strike_key in data_dict:
                            descoberto_value = data_dict[strike_key].get('descoberto', 0)
                            historical_values.append(descoberto_value)
                        else:
                            historical_values.append(0)
                    
                    # Valor atual
                    current_value = current_data.get(strike_key, {}).get('descoberto', 0)
                    
                    if len(historical_values) >= 3:
                        avg_historical = float(np.mean(historical_values))
                        std_historical = float(np.std(historical_values))
                        
                        # Z-score
                        z_score = 0
                        if std_historical > 0:
                            z_score = (current_value - avg_historical) / std_historical
                        
                        # Classificação
                        if z_score > 1.5:
                            classification = 'MUITO_ALTO'
                        elif z_score > 0.5:
                            classification = 'ALTO'
                        elif z_score < -1.5:
                            classification = 'MUITO_BAIXO'
                        elif z_score < -0.5:
                            classification = 'BAIXO'
                        else:
                            classification = 'NORMAL'
                        
                        context[strike_key] = {
                            'current': int(current_value),
                            'historical_avg': avg_historical,
                            'z_score': float(z_score),
                            'classification': classification
                        }
                        
                except Exception as e:
                    logging.debug(f"Erro processando strike {strike_key}: {e}")
                    continue
            
            logging.info(f"Contexto histórico calculado para {len(context)} strikes")
            return context
            
        except Exception as e:
            logging.error(f"Erro no cálculo do contexto histórico: {e}")
            return {}
    
    def calculate_flip_evolution(self, historical_data, current_data, spot_price):
        """Evolução do Gamma Flip - VERSÃO CORRIGIDA"""
        flip_evolution = []
        
        # FORÇA CONVERSÃO DO SPOT_PRICE
        try:
            spot_price = float(spot_price)
        except (ValueError, TypeError):
            logging.error(f"Spot price inválido: {spot_price}")
            return {'evolution': [], 'trend_analysis': {'direction': 'ERRO'}}
        
        # Calcula flip para cada dia histórico
        for date in sorted(historical_data.keys()):
            flip_point = self._calculate_gamma_flip_for_data(historical_data[date], spot_price)
            flip_evolution.append({
                'date': date,
                'flip_strike': flip_point,
                'distance_from_spot': abs(flip_point - spot_price) / spot_price * 100 if flip_point else None
            })
        
        # Adiciona flip atual
        current_flip = self._calculate_gamma_flip_for_data(current_data, spot_price)
        flip_evolution.append({
            'date': 'current',
            'flip_strike': current_flip,
            'distance_from_spot': abs(current_flip - spot_price) / spot_price * 100 if current_flip else None
        })
        
        # Análise de tendência
        flip_strikes = [item['flip_strike'] for item in flip_evolution if item['flip_strike']]
        if len(flip_strikes) >= 3:
            # Regressão linear simples para detectar tendência
            x = np.arange(len(flip_strikes))
            slope, intercept = np.polyfit(x, flip_strikes, 1)
            
            trend_analysis = {
                'slope': float(slope),
                'direction': 'SUBINDO' if slope > 0.1 else 'DESCENDO' if slope < -0.1 else 'ESTAVEL',
                'velocity': abs(float(slope)),  # Velocidade da mudança
                'consistency': self._calculate_trend_consistency(flip_strikes)
            }
        else:
            trend_analysis = {'direction': 'INSUFICIENTE', 'slope': 0, 'velocity': 0, 'consistency': 0}
        
        return {
            'evolution': flip_evolution,
            'trend_analysis': trend_analysis
        }
    
    def calculate_pressure_dynamics(self, historical_data, current_data, spot_price):
        """Versão simplificada que funciona"""
        pressure_dynamics = {}
        
        try:
            spot_price = float(spot_price)
        except:
            return {}
        
        price_range = spot_price * 0.15
        
        # Processa TODAS as chaves sem validação excessiva
        for strike_key, strike_data in current_data.items():
            try:
                # Se a chave já é tupla, usa diretamente
                if isinstance(strike_key, tuple) and len(strike_key) == 2:
                    strike_price = float(strike_key[0])
                    
                    # Verifica range
                    if spot_price - price_range <= strike_price <= spot_price + price_range:
                        
                        # Coleta série temporal
                        time_series = []
                        for date in sorted(historical_data.keys()):
                            value = historical_data[date].get(strike_key, {}).get('descoberto', 0)
                            time_series.append(value)
                        
                        current_value = current_data.get(strike_key, {}).get('descoberto', 0)
                        time_series.append(current_value)
                        
                        if len(time_series) >= 3:
                            max_pressure = max(time_series)
                            current_pressure = time_series[-1]
                            pressure_consumed = max_pressure - current_pressure
                            consumption_rate = pressure_consumed / max_pressure if max_pressure > 0 else 0
                            
                            pressure_dynamics[strike_key] = {
                                'strike': float(strike_price),
                                'current_pressure': int(current_pressure),
                                'max_pressure': int(max_pressure),
                                'consumption_rate': float(consumption_rate),
                                'pressure_status': 'ESGOTANDO' if consumption_rate > 0.3 else 'ACUMULANDO' if current_pressure > time_series[-2] else 'ESTAVEL'
                            }
            except:
                continue
        
        return pressure_dynamics
    
    def calculate_regime_persistence(self, historical_data, current_data):
        """
        Regime de Persistência
        Analisa estabilidade do regime Long/Short Gamma ao longo do tempo
        """
        regime_history = []
        
        # Calcula regime para cada dia
        for date in sorted(historical_data.keys()):
            net_gex = self._calculate_net_gex_for_data(historical_data[date])
            regime = 'LONG_GAMMA' if net_gex > 0 else 'SHORT_GAMMA'
            regime_history.append(regime)
        
        # Adiciona regime atual
        current_net_gex = self._calculate_net_gex_for_data(current_data)
        current_regime = 'LONG_GAMMA' if current_net_gex > 0 else 'SHORT_GAMMA'
        regime_history.append(current_regime)
        
        # Análise de persistência
        persistence_count = 1
        current_regime_in_sequence = regime_history[-1]
        
        # Conta quantos dias consecutivos no mesmo regime
        for i in range(len(regime_history) - 2, -1, -1):
            if regime_history[i] == current_regime_in_sequence:
                persistence_count += 1
            else:
                break
        
        # Estatísticas de estabilidade
        regime_changes = sum(1 for i in range(1, len(regime_history)) 
                           if regime_history[i] != regime_history[i-1])
        
        stability_score = 1 - (regime_changes / max(1, len(regime_history) - 1))
        
        return {
            'current_regime': current_regime,
            'persistence_days': persistence_count,
            'total_changes': regime_changes,
            'stability_score': float(stability_score),
            'regime_history': regime_history,
            'interpretation': self._interpret_regime_persistence(persistence_count, stability_score)
        }
    
    def calculate_accumulation_velocity(self, historical_data, current_data):
        """Velocidade de Acumulação - VERSÃO CORRIGIDA"""
        velocity_analysis = {}
        
        # Coleta strikes válidos
        all_strikes = set()
        for data_dict in historical_data.values():
            all_strikes.update(data_dict.keys())
        all_strikes.update(current_data.keys())
        
        for strike_key in all_strikes:
            # MESMA VALIDAÇÃO RIGOROSA
            if not isinstance(strike_key, tuple) or len(strike_key) != 2:
                continue
                
            try:
                strike_value = strike_key[0]
                if isinstance(strike_value, str):
                    strike_price = float(strike_value)
                elif isinstance(strike_value, (int, float)):
                    strike_price = float(strike_value)
                else:
                    continue
            except (ValueError, TypeError):
                continue
            
            # Constrói série temporal
            time_series = []
            dates = sorted(historical_data.keys())
            
            for date in dates:
                value = historical_data[date].get(strike_key, {}).get('descoberto', 0)
                time_series.append(value)
            
            current_value = current_data.get(strike_key, {}).get('descoberto', 0)
            time_series.append(current_value)
            
            if len(time_series) >= 3:
                velocities = []
                for i in range(1, len(time_series)):
                    velocity = time_series[i] - time_series[i-1]
                    velocities.append(velocity)
                
                avg_velocity = np.mean(velocities)
                current_velocity = velocities[-1] if velocities else 0
                
                if current_velocity > abs(avg_velocity) * 1.5:
                    trend = 'ACELERANDO_POSITIVO'
                elif current_velocity < -abs(avg_velocity) * 1.5:
                    trend = 'ACELERANDO_NEGATIVO'
                elif abs(current_velocity) < abs(avg_velocity) * 0.5:
                    trend = 'DESACELERANDO'
                else:
                    trend = 'ESTAVEL'
                
                velocity_analysis[strike_key] = {
                    'strike': float(strike_price),
                    'current_velocity': int(current_velocity),
                    'avg_velocity': float(avg_velocity),
                    'trend': trend,
                    'velocity_magnitude': abs(current_velocity)
                }
        
        return velocity_analysis
    
    def calculate_temporal_distortions(self, historical_data, current_data):
        """
        Distorções Temporais
        Detecta quando distribuição atual difere significativamente do padrão histórico
        """
        distortions = []
        
        # Calcula distribuição histórica por tipo de opção
        historical_call_concentration = []
        historical_put_concentration = []
        
        for date, data_dict in historical_data.items():
            call_total = sum(item['descoberto'] for key, item in data_dict.items() if key[1] == 'CALL')
            put_total = sum(item['descoberto'] for key, item in data_dict.items() if key[1] == 'PUT')
            total = call_total + put_total
            
            if total > 0:
                call_pct = call_total / total
                put_pct = put_total / total
                historical_call_concentration.append(call_pct)
                historical_put_concentration.append(put_pct)
        
        # Distribuição atual
        current_call_total = sum(item['descoberto'] for key, item in current_data.items() if key[1] == 'CALL')
        current_put_total = sum(item['descoberto'] for key, item in current_data.items() if key[1] == 'PUT')
        current_total = current_call_total + current_put_total
        
        if current_total > 0 and len(historical_call_concentration) >= 3:
            current_call_pct = current_call_total / current_total
            current_put_pct = current_put_total / current_total
            
            avg_historical_call = np.mean(historical_call_concentration)
            std_historical_call = np.std(historical_call_concentration)
            
            # Z-score da distorção
            call_distortion = (current_call_pct - avg_historical_call) / std_historical_call if std_historical_call > 0 else 0
            
            # Detecção de distorção significativa
            if abs(call_distortion) > 1.5:  # Mais de 1.5 desvios padrão
                distortion_type = 'CALLS_CONCENTRADAS' if call_distortion > 0 else 'PUTS_CONCENTRADAS'
                severity = 'EXTREMA' if abs(call_distortion) > 2.0 else 'MODERADA'
                
                distortions.append({
                    'type': 'DISTRIBUICAO_TIPO',
                    'distortion_type': distortion_type,
                    'severity': severity,
                    'z_score': float(call_distortion),
                    'current_call_pct': float(current_call_pct * 100),
                    'historical_call_pct': float(avg_historical_call * 100),
                    'interpretation': f"Concentração atual em {distortion_type.split('_')[0].lower()} está {severity.lower()} vs padrão histórico"
                })
        
        return distortions
    
    # Métodos auxiliares privados
    def _calculate_gamma_flip_for_data(self, data_dict, spot_price):
        """Calcula gamma flip para um dataset específico"""
        try:
            spot_price = float(spot_price)
            strikes_with_oi = []
            for key, oi_data in data_dict.items():
                if isinstance(key, tuple) and len(key) >= 2:
                    strike = key[0]  # Primeiro elemento é o strike
                    option_type = key[1]  # Segundo elemento é o tipo
                    oi_descoberto = oi_data.get('descoberto', 0)
                    
                    if strike > 0 and oi_descoberto > 0:
                        strikes_with_oi.append((strike, oi_descoberto))
            
            if not strikes_with_oi:
                logging.warning("Nenhum strike com OI descoberto encontrado para cálculo de flip")
                return float(spot_price)
            
            # Encontra strike com maior concentração próximo ao spot
            nearby_strikes = [
                (strike, oi) for strike, oi in strikes_with_oi 
                if abs(strike - spot_price) <= spot_price * 0.1
            ]
            
            if nearby_strikes:
                # Retorna strike com maior OI descoberto próximo ao spot
                max_oi_strike = max(nearby_strikes, key=lambda x: x[1])[0]
                return float(max_oi_strike)
            else:
                # Se não há strikes próximos, retorna o spot price
                return float(spot_price)
                
        except Exception as e:
            logging.error(f"Erro no cálculo de gamma flip: {e}")
            return float(spot_price)
    
    def _calculate_net_gex_for_data(self, data_dict):
        """Calcula GEX líquido simplificado para um dataset"""
        try:
            call_oi = 0
            put_oi = 0
            
            for key, oi_data in data_dict.items():
                if isinstance(key, tuple) and len(key) >= 2:
                    strike = key[0]
                    option_type = key[1]
                    oi_descoberto = oi_data.get('descoberto', 0)
                    
                    if option_type == 'CALL':
                        call_oi += oi_descoberto
                    elif option_type == 'PUT':
                        put_oi += oi_descoberto
            
            # GEX simplificado (put - call para aproximação)
            net_gex = put_oi - call_oi
            logging.debug(f"Net GEX calculado: {net_gex} (Calls: {call_oi}, Puts: {put_oi})")
            
            return net_gex
            
        except Exception as e:
            logging.error(f"Erro no cálculo de net GEX: {e}")
            return 0
    
    def _calculate_trend_consistency(self, values):
        """Calcula consistência de uma tendência (0-1)"""
        if len(values) < 3:
            return 0
        
        # Calcula quantos pontos seguem a tendência geral
        slopes = []
        for i in range(1, len(values)):
            slope = values[i] - values[i-1]
            slopes.append(slope)
        
        positive_slopes = sum(1 for s in slopes if s > 0)
        negative_slopes = sum(1 for s in slopes if s < 0)
        
        # Consistência = proporção de slopes na mesma direção
        max_direction = max(positive_slopes, negative_slopes)
        return max_direction / len(slopes) if slopes else 0
    
    def _interpret_regime_persistence(self, persistence_days, stability_score):
        """Interpreta persistência do regime"""
        if persistence_days >= 4 and stability_score > 0.8:
            return "Regime altamente estável - padrão consistente de comportamento"
        elif persistence_days >= 3 and stability_score > 0.6:
            return "Regime moderadamente estável - tendência clara"
        elif persistence_days >= 2:
            return "Regime em formação - aguardar confirmação"
        else:
            return "Regime instável - alta volatilidade de comportamento"

class MMTemporalAnalyzer:
    """
    Analisador principal que coordena todas as métricas temporais
    Orquestra coleta de dados e cálculos para gerar insights acionáveis
    """
    
    def __init__(self):
        self.data_provider = HistoricalDataProvider()
        self.metrics_calculator = TemporalMetricsCalculator()
        self.business_day_manager = BusinessDayManager()
    
    def analyze(self, symbol, spot_price, current_oi_breakdown, days_back=5):
        """
        Análise temporal completa dos market makers
        
        Args:
            symbol: Código da ação (ex: 'PETR4')
            spot_price: Preço atual da ação
            current_oi_breakdown: Dados atuais de OI descoberto
            days_back: Quantidade de dias úteis para análise histórica
        
        Returns:
            Dict com todas as métricas temporais calculadas
        """
        logging.info(f"INICIANDO ANÁLISE TEMPORAL MM - {symbol}")
        
        # 1. Coleta dias úteis históricos
        business_days = self.business_day_manager.get_business_days(days_back)
        if len(business_days) < 3:
            raise ValueError("Histórico insuficiente - mínimo 3 dias úteis necessários")
        
        logging.info(f"Coletando dados para {len(business_days)} dias úteis: {business_days}")
        
        # 2. Coleta dados históricos para cada dia
        historical_data = {}
        for date_str in business_days:
            expiration = self.business_day_manager.get_expiration_for_date(date_str)
            oi_data = self.data_provider.get_oi_breakdown_for_date(symbol, date_str, expiration)
            
            if oi_data:  # Só adiciona se conseguiu dados
                historical_data[date_str] = oi_data
                logging.info(f"Dados coletados para {date_str}: {len(oi_data)} strikes")
            else:
                logging.warning(f"Falha ao coletar dados para {date_str}")
        
        if len(historical_data) < 3:
            raise ValueError("Dados históricos insuficientes - mínimo 3 dias com dados válidos")
        
        # 3. Executar todas as análises temporais
        logging.info("Calculando métricas temporais...")
        
        # Contexto histórico dos descobertos
        descoberto_context = self.metrics_calculator.calculate_descoberto_context(
            historical_data, current_oi_breakdown
        )
        
        # Evolução do gamma flip
        flip_evolution = self.metrics_calculator.calculate_flip_evolution(
            historical_data, current_oi_breakdown, spot_price
        )
        
        # Dinâmica de pressão
        pressure_dynamics = self.metrics_calculator.calculate_pressure_dynamics(
            historical_data, current_oi_breakdown, spot_price
        )
        
        # Persistência do regime
        regime_persistence = self.metrics_calculator.calculate_regime_persistence(
            historical_data, current_oi_breakdown
        )
        
        # Velocidade de acumulação
        accumulation_velocity = self.metrics_calculator.calculate_accumulation_velocity(
            historical_data, current_oi_breakdown
        )
        
        # Distorções temporais
        temporal_distortions = self.metrics_calculator.calculate_temporal_distortions(
            historical_data, current_oi_breakdown
        )
        
        # 4. Compilar resultado final
        analysis_result = {
            'symbol': symbol,
            'analysis_date': datetime.now().isoformat(),
            'historical_period': {
                'start_date': business_days[0],
                'end_date': business_days[-1],
                'days_analyzed': len(business_days),
                'successful_data_days': len(historical_data)
            },
            'descoberto_context': descoberto_context,
            'flip_evolution': flip_evolution,
            'pressure_dynamics': pressure_dynamics,
            'regime_persistence': regime_persistence,
            'accumulation_velocity': accumulation_velocity,
            'temporal_distortions': temporal_distortions,
            'summary_insights': self._generate_summary_insights(
                descoberto_context, flip_evolution, regime_persistence, temporal_distortions
            )
        }
        
        logging.info("Análise temporal concluída com sucesso")
        return analysis_result
    
    def _generate_summary_insights(self, descoberto_context, flip_evolution, regime_persistence, distortions):
        """Gera insights resumidos da análise temporal"""
        insights = []
        
        # Insight sobre persistência do regime
        regime_info = regime_persistence
        if regime_info['persistence_days'] >= 4:
            insights.append({
                'type': 'REGIME_STABILITY',
                'priority': 'HIGH',
                'message': f"Regime {regime_info['current_regime']} persistente há {regime_info['persistence_days']} dias - alta previsibilidade"
            })
        
        # Insight sobre evolução do flip
        flip_trend = flip_evolution['trend_analysis']['direction']
        if flip_trend != 'ESTAVEL':
            insights.append({
                'type': 'FLIP_TREND',
                'priority': 'MEDIUM',
                'message': f"Gamma flip {flip_trend} - MMs reposicionando estruturalmente"
            })
        
        # Insights sobre distorções
        for distortion in distortions:
            if distortion['severity'] == 'EXTREMA':
                insights.append({
                    'type': 'TEMPORAL_DISTORTION',
                    'priority': 'HIGH',
                    'message': distortion['interpretation']
                })
        
        return insights

class MMTemporalService:
    """
    Serviço principal para análise temporal de market makers
    Interface pública para integração com API
    """
    
    def __init__(self):
        self.analyzer = MMTemporalAnalyzer()
    
    def analyze_mm_temporal_complete(self, ticker, spot_price, current_oi_breakdown, days_back=5):
        """Versão simplificada que funciona"""
        try:
            result = self.analyzer.analyze(ticker, spot_price, current_oi_breakdown, days_back)
            
            # Resposta simples sem complexidade excessiva
            api_result = {
                'ticker': ticker.replace('.SA', ''),
                'success': True,
                'temporal_metrics': {
                    'regime_persistence': result.get('regime_persistence', {}),
                    'pressure_dynamics': result.get('pressure_dynamics', {}),
                    'flip_evolution': result.get('flip_evolution', {})
                },
                'insights': result.get('summary_insights', [])
            }
            
            # Usa a função corrigida de serialização
            return convert_to_json_serializable(api_result)
            
        except Exception as e:
            logging.error(f"Erro na análise temporal MM: {e}")
            return {
                'ticker': ticker.replace('.SA', ''),
                'error': str(e),
                'success': False
            }
    
    def get_available_analysis_dates(self, ticker, days_back=10):
        """
        Retorna datas disponíveis para análise histórica
        Útil para debugging e validação de dados
        """
        try:
            business_days = self.analyzer.business_day_manager.get_business_days(days_back)
            availability = []
            
            for date_str in business_days:
                expiration = self.analyzer.business_day_manager.get_expiration_for_date(date_str)
                data_count = len(self.analyzer.data_provider.get_oi_breakdown_for_date(ticker, date_str, expiration))
                
                availability.append({
                    'date': date_str,
                    'expiration_used': expiration,
                    'data_points': data_count,
                    'available': data_count > 0
                })
            
            return {
                'ticker': ticker,
                'dates_checked': len(business_days),
                'dates_available': sum(1 for item in availability if item['available']),
                'availability_details': availability,
                'success': True
            }
            
        except Exception as e:
            logging.error(f"Erro verificando disponibilidade: {e}")
            return {
                'ticker': ticker,
                'error': str(e),
                'success': False
            }

# Instância global do serviço para uso nas rotas
mm_temporal_service = MMTemporalService()
        
        