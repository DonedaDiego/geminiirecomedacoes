"""
mm_temporal_service.py - Market Maker Temporal Analysis RENOVADO
Análise simples e eficaz da evolução das posições descobertas dos MMs
"""

import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta
import warnings
import logging
import os
from dotenv import load_dotenv

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
load_dotenv()

def convert_to_json_serializable(obj):
    """Conversão simples para JSON"""
    try:
        if obj is None or pd.isna(obj):
            return None
        elif isinstance(obj, dict):
            return {str(key): convert_to_json_serializable(value) for key, value in obj.items()}
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
    """Gerencia dias úteis para análise"""
    
    @staticmethod
    def get_business_days(days_needed=5):
        """Coleta 5 dias úteis anteriores (D-1 até D-5)"""
        dates = []
        current_date = datetime.now().date()
        i = 1  # Começa de ontem (D-1)
        
        while len(dates) < days_needed and i <= 10:
            check_date = current_date - timedelta(days=i)
            
            if check_date.weekday() < 5:  # Segunda=0 até Sexta=4
                dates.append(check_date.strftime('%Y-%m-%d'))
            
            i += 1
        
        return list(reversed(dates))  # Ordem cronológica

class HistoricalDataProvider:
    """Provedor de dados do Floqui para análise temporal"""
    
    def __init__(self):
        self.available_expirations = {
            "20250919": datetime(2025, 9, 19).date(),
            "20251017": datetime(2025, 10, 17).date(), 
            "20251121": datetime(2025, 11, 21).date(),
            "20251219": datetime(2025, 12, 19).date(),
            "20260116": datetime(2026, 1, 16).date(),
        }
    
    def get_expiration_for_date(self, date_str):
        """Mapeia data para vencimento mais apropriado"""
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Pega o vencimento mais próximo que não expirou
            for code, expiry_date in self.available_expirations.items():
                if date_obj <= expiry_date:
                    days_until_expiry = (expiry_date - date_obj).days
                    if days_until_expiry >= 7:  # Pelo menos 7 dias até vencer
                        return code
            
            return "20251017"  # Fallback
            
        except Exception:
            return "20251017"
    
    def get_oi_breakdown_for_date(self, symbol, date_str, expiration_code):
        """Busca dados de OI para uma data específica"""
        try:
            dt_formatada = date_str.replace('-', '')
            url = f"https://floqui.com.br/api/posicoes_em_aberto/{symbol.lower()}/{expiration_code}/{dt_formatada}"
            
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                return {}
            
            data = response.json()
            if not data:
                return {}
            
            oi_breakdown = {}
            for item in data:
                strike = float(item.get('preco_exercicio', 0))
                option_type = item.get('tipo_opcao', '').upper()
                oi_descoberto = int(item.get('qtd_descoberto', 0))
                
                if strike > 0 and oi_descoberto > 0:
                    key = f"{strike}_{option_type}"
                    oi_breakdown[key] = oi_descoberto
            
            return oi_breakdown
            
        except Exception as e:
            logging.error(f"Erro buscando dados para {date_str}: {e}")
            return {}

class MMTemporalCalculator:
    """Calculadora de métricas temporais focadas"""
    
    def calculate_pressure_evolution(self, historical_data, current_data, spot_price):
        """MÉTRICA 1: Evolução da pressão descoberta por região"""
        
        regions = {
            'calls_atm': [],     # Calls próximas do money
            'puts_atm': [],      # Puts próximas do money  
            'calls_otm': [],     # Calls fora do money
            'puts_otm': []       # Puts fora do money
        }
        
        # Para cada dia, soma por região
        all_dates = list(historical_data.keys()) + ['current']
        
        for date in all_dates:
            data_dict = current_data if date == 'current' else historical_data[date]
            
            day_regions = {'calls_atm': 0, 'puts_atm': 0, 'calls_otm': 0, 'puts_otm': 0}
            
            for key, oi_descoberto in data_dict.items():
                try:
                    parts = key.split('_')
                    strike = float(parts[0])
                    option_type = parts[1]
                    
                    # Classificar por região
                    distance_pct = abs(strike - spot_price) / spot_price
                    
                    if option_type == 'CALL':
                        if distance_pct <= 0.05:  # ATM = ±5%
                            day_regions['calls_atm'] += oi_descoberto
                        else:
                            day_regions['calls_otm'] += oi_descoberto
                    else:  # PUT
                        if distance_pct <= 0.05:  # ATM = ±5%
                            day_regions['puts_atm'] += oi_descoberto
                        else:
                            day_regions['puts_otm'] += oi_descoberto
                            
                except Exception:
                    continue
            
            # Adicionar aos arrays
            for region in regions:
                regions[region].append(day_regions[region])
        
        return {
            'dates': all_dates,
            'regions': regions,
            'total_evolution': [sum([regions[r][i] for r in regions]) for i in range(len(all_dates))]
        }
    
    def calculate_liquidity_consumption(self, historical_data, current_data, spot_price):
        """MÉTRICA 2: Análise se liquidez está sendo consumida"""
        
        liquidity_metrics = []
        all_dates = list(historical_data.keys()) + ['current']
        
        for i, date in enumerate(all_dates):
            data_dict = current_data if date == 'current' else historical_data[date]
            
            # Foco na região ATM (±10% do spot)
            atm_range = spot_price * 0.10
            atm_liquidity = 0
            
            for key, oi_descoberto in data_dict.items():
                try:
                    strike = float(key.split('_')[0])
                    if abs(strike - spot_price) <= atm_range:
                        atm_liquidity += oi_descoberto
                except Exception:
                    continue
            
            # Calcular velocidade de consumo
            if i > 0:
                previous_liquidity = liquidity_metrics[-1]['atm_liquidity']
                consumption_rate = (previous_liquidity - atm_liquidity) / previous_liquidity if previous_liquidity > 0 else 0
            else:
                consumption_rate = 0
            
            liquidity_metrics.append({
                'date': date,
                'atm_liquidity': atm_liquidity,
                'consumption_rate': consumption_rate
            })
        
        return liquidity_metrics
    
    def calculate_imbalance_shifts(self, historical_data, current_data):
        """MÉTRICA 3: Mudanças no desequilíbrio Call/Put"""
        
        imbalance_evolution = []
        all_dates = list(historical_data.keys()) + ['current']
        
        for date in all_dates:
            data_dict = current_data if date == 'current' else historical_data[date]
            
            total_calls = sum(oi for key, oi in data_dict.items() if '_CALL' in key)
            total_puts = sum(oi for key, oi in data_dict.items() if '_PUT' in key)
            
            total = total_calls + total_puts
            
            if total > 0:
                call_ratio = total_calls / total
                put_ratio = total_puts / total
                imbalance = call_ratio - put_ratio  # Positivo = mais calls
            else:
                call_ratio = put_ratio = imbalance = 0
            
            imbalance_evolution.append({
                'date': date,
                'call_ratio': call_ratio,
                'put_ratio': put_ratio,
                'imbalance': imbalance,
                'total_oi': total
            })
        
        return imbalance_evolution
    
    def generate_actionable_insights(self, pressure_evolution, liquidity_consumption, imbalance_shifts):
        """INSIGHTS ACIONÁVEIS baseados nas 3 métricas"""
        
        insights = []
        
        # 1. TENDÊNCIA DA PRESSÃO TOTAL
        total_trend = pressure_evolution['total_evolution']
        if len(total_trend) >= 3:
            recent_change = (total_trend[-1] - total_trend[-3]) / total_trend[-3] if total_trend[-3] > 0 else 0
            
            if recent_change > 0.15:
                insights.append({
                    'type': 'PRESSURE_BUILDING',
                    'message': f"Posições descobertas AUMENTARAM {recent_change*100:.1f}% - MMs aumentando exposição",
                    'priority': 'HIGH'
                })
            elif recent_change < -0.15:
                insights.append({
                    'type': 'PRESSURE_REDUCING',
                    'message': f"Posições descobertas DIMINUÍRAM {abs(recent_change)*100:.1f}% - MMs reduzindo risco",
                    'priority': 'HIGH'
                })
        
        # 2. CONSUMO DE LIQUIDEZ ATM
        current_consumption = liquidity_consumption[-1]['consumption_rate']
        if current_consumption > 0.10:
            insights.append({
                'type': 'LIQUIDITY_CONSUMED',
                'message': f"Liquidez ATM sendo consumida rapidamente ({current_consumption*100:.1f}%/dia)",
                'priority': 'MEDIUM'
            })
        
        # 3. MUDANÇA NO DESEQUILÍBRIO
        current_imbalance = imbalance_shifts[-1]['imbalance']
        previous_imbalance = imbalance_shifts[-2]['imbalance'] if len(imbalance_shifts) >= 2 else 0
        
        imbalance_change = current_imbalance - previous_imbalance
        
        if abs(imbalance_change) > 0.10:
            direction = "CALLS" if imbalance_change > 0 else "PUTS" 
            insights.append({
                'type': 'IMBALANCE_SHIFT',
                'message': f"Desequilíbrio mudando para {direction} - MMs reposicionando",
                'priority': 'MEDIUM'
            })
        
        return insights

class MMTemporalAnalyzer:
    """Analisador principal - SIMPLES E FOCADO"""
    
    def __init__(self):
        self.data_provider = HistoricalDataProvider()
        self.calculator = MMTemporalCalculator()
        self.business_manager = BusinessDayManager()
    
    def analyze(self, symbol, spot_price, current_oi_breakdown, days_back=5):
        """Análise temporal focada em 3 métricas essenciais"""
        
        logging.info(f"INICIANDO ANÁLISE MM TEMPORAL - {symbol}")
        
        # 1. Coletar dias úteis
        business_days = self.business_manager.get_business_days(days_back)
        
        # 2. Coletar dados históricos
        historical_data = {}
        for date_str in business_days:
            expiration = self.data_provider.get_expiration_for_date(date_str)
            oi_data = self.data_provider.get_oi_breakdown_for_date(symbol, date_str, expiration)
            
            if oi_data:
                historical_data[date_str] = oi_data
        
        if len(historical_data) < 3:
            raise ValueError("Dados históricos insuficientes - mínimo 3 dias")
        
        # 3. Converter current_oi_breakdown para formato simples
        current_data_simple = {}
        for key, value in current_oi_breakdown.items():
            if isinstance(key, tuple) and len(key) == 2:
                strike, option_type = key
                simple_key = f"{strike}_{option_type}"
                current_data_simple[simple_key] = value.get('descoberto', 0)
        
        # 4. CALCULAR AS 3 MÉTRICAS ESSENCIAIS
        logging.info("Calculando métricas temporais...")
        
        pressure_evolution = self.calculator.calculate_pressure_evolution(
            historical_data, current_data_simple, spot_price
        )
        
        liquidity_consumption = self.calculator.calculate_liquidity_consumption(
            historical_data, current_data_simple, spot_price  
        )
        
        imbalance_shifts = self.calculator.calculate_imbalance_shifts(
            historical_data, current_data_simple
        )
        
        # 5. GERAR INSIGHTS ACIONÁVEIS
        insights = self.calculator.generate_actionable_insights(
            pressure_evolution, liquidity_consumption, imbalance_shifts
        )
        
        # 6. RESUMO EXECUTIVO
        current_total = pressure_evolution['total_evolution'][-1]
        d1_total = pressure_evolution['total_evolution'][-2] if len(pressure_evolution['total_evolution']) >= 2 else current_total
        
        trend_direction = "CRESCENDO" if current_total > d1_total else "DIMINUINDO"
        trend_magnitude = abs(current_total - d1_total) / d1_total if d1_total > 0 else 0
        
        summary = {
            'total_descoberto_current': current_total,
            'trend_direction': trend_direction,
            'trend_magnitude_pct': trend_magnitude * 100,
            'days_analyzed': len(historical_data),
            'liquidity_status': 'BEING_CONSUMED' if liquidity_consumption[-1]['consumption_rate'] > 0.05 else 'STABLE',
            'dominant_side': 'CALLS' if imbalance_shifts[-1]['imbalance'] > 0.1 else 'PUTS' if imbalance_shifts[-1]['imbalance'] < -0.1 else 'BALANCED'
        }
        
        return {
            'symbol': symbol,
            'analysis_date': datetime.now().isoformat(),
            'summary': summary,
            'pressure_evolution': pressure_evolution,
            'liquidity_consumption': liquidity_consumption, 
            'imbalance_shifts': imbalance_shifts,
            'insights': insights
        }

class MMTemporalService:
    """Serviço principal - Interface pública"""
    
    def __init__(self):
        self.analyzer = MMTemporalAnalyzer()
    
    def analyze_mm_temporal_complete(self, ticker, spot_price, current_oi_breakdown, days_back=5):
        """Análise temporal completa - VERSÃO RENOVADA"""
        
        try:
            result = self.analyzer.analyze(ticker, spot_price, current_oi_breakdown, days_back)
            
            # Resposta limpa e focada
            api_result = {
                'ticker': ticker.replace('.SA', ''),
                'success': True,
                'summary': result['summary'],
                'temporal_metrics': {
                    'pressure_evolution': result['pressure_evolution'],
                    'liquidity_consumption': result['liquidity_consumption'],
                    'imbalance_shifts': result['imbalance_shifts']
                },
                'insights': result['insights'],
                'analysis_metadata': {
                    'analysis_date': result['analysis_date'],
                    'days_analyzed': result['summary']['days_analyzed']
                }
            }
            
            return convert_to_json_serializable(api_result)
            
        except Exception as e:
            logging.error(f"Erro na análise temporal MM: {e}")
            return {
                'ticker': ticker.replace('.SA', ''),
                'error': str(e),
                'success': False
            }

# Instância global
mm_temporal_service = MMTemporalService()