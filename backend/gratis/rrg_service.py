"""
rrg_service.py - Relative Rotation Graph (RRG) Analysis
Analise de Forca Relativa Trimestral vs Anual usando EMAs 65 e 252
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO)


class YFinanceRRGService:
    """Servico completo para analise RRG usando YFinance"""
    
    TICKERS_SETORES = {
    # Petroleo, Gas e Bio
    'PETR3': 'Petroleo, Gas e Bio',
    'PETR4': 'Petroleo, Gas e Bio',
    'BRAV3': 'Petroleo, Gas e Bio',
    'CSAN3': 'Petroleo, Gas e Bio',
    'PRIO3': 'Petroleo, Gas e Bio',
    'UGPA3': 'Petroleo, Gas e Bio',
    'VBBR3': 'Petroleo, Gas e Bio',
    'RECV3': 'Petroleo, Gas e Bio',
    'RPMG3': 'Petroleo, Gas e Bio',

    # Mineracao
    'VALE3': 'Mineracao',
    'AURA33': 'Mineracao',
    'BRAP4': 'Mineracao',
    'CBAV3': 'Mineracao',
    'CMIN3': 'Mineracao',

    # Siderurgia e Metalurgia
    'GGBR4': 'Siderurgia e Metalurgia',
    'GOAU4': 'Siderurgia e Metalurgia',
    'CSNA3': 'Siderurgia e Metalurgia',
    'USIM5': 'Siderurgia e Metalurgia',

    # Quimicos
    'BRKM5': 'Quimicos',

    # Madeira e Papel
    'KLBN11': 'Madeira e Papel',
    'SUZB3': 'Madeira e Papel',

    # Transporte
    'EMBJ3': 'Transporte',
    'RAIL3': 'Transporte',
    'JSLG3': 'Transporte',
    'POMO4': 'Transporte',
    'MOTV3': 'Transporte',

    # Maquinas
    'WEGE3': 'Maquinas',
    'ROMI3': 'Maquinas',

    # Agropecuaria
    'AGXY3': 'Agropecuaria',
    'SOJA3': 'Agropecuaria',
    'AGRO3': 'Agropecuaria',
    'SLCE3': 'Agropecuaria',

    # Alimentos
    'MBRF3': 'Alimentos',
    'BEEF3': 'Alimentos',

    # Bebidas
    'ABEV3': 'Bebidas',

    # Produtos (não duráveis/cosméticos)
    'NATU3': 'Produtos',

    # Varejista
    'ASAI3': 'Varejista',
    'AZZA3': 'Varejista',
    'CEAB3': 'Varejista',
    'LREN3': 'Varejista',
    'MGLU3': 'Varejista',
    'RADL3': 'Varejista',

    # Tecidos, Ves, Cal (vestuário)
    'VIVA3': 'Tecidos, Ves, Cal',

    # Automoveis
    'MYPK3': 'Automoveis',
    'LEVE3': 'Automoveis',

    # Viagens e Lazer
    'CVCB3': 'Viagens e Lazer',

    # Diversos
    'COGN3': 'Diversos',
    'YDUQ3': 'Diversos',
    'RENT3': 'Diversos',
    'VAMO3': 'Diversos',

    # Servicos Medico
    'RDOR3': 'Servicos Medico',
    'FLRY3': 'Servicos Medico',
    'HAPV3': 'Servicos Medico',

    # Servicos (TI/comunicações)
    'TOTS3': 'Servicos',
    'VIVT3': 'Servicos',
    'TIMS3': 'Servicos',

    # Energia
    'ALUP11': 'Energia',
    'CBEE3': 'Energia',
    'AURE3': 'Energia',
    'CEBR3': 'Energia',
    'CLSC3': 'Energia',
    'CMIG4': 'Energia',
    'CPLE3': 'Energia',
    'CPFE3': 'Energia',
    'AXIA3': 'Energia',
    'AXIA6': 'Energia',
    'ENGI4': 'Energia',
    'ENEV3': 'Energia',
    'EGIE3': 'Energia',
    'EQTL3': 'Energia',
    'NEOE3': 'Energia',
    'TAEE11': 'Energia',

    # Saneamento
    'SBSP3': 'Saneamento',
    'CSMG3': 'Saneamento',
    'SAPR11': 'Saneamento',

    # Gas
    'CEGR3': 'Gas',

    # Inter Financeiros (bancos)
    'ABCB4': 'Inter Financeiros',
    'BBDC3': 'Inter Financeiros',
    'BBDC4': 'Inter Financeiros',
    'BBAS3': 'Inter Financeiros',
    'ITUB4': 'Inter Financeiros',
    'BPAC11': 'Inter Financeiros',

    # Ser Financeiros
    'B3SA3': 'Ser Financeiros',

    # Previdencia e Seguros
    'BBSE3': 'Previdencia e Seguros',
    'CXSE3': 'Previdencia e Seguros',
    'PSSA3': 'Previdencia e Seguros',
    'IRBR3': 'Previdencia e Seguros',

    # Exploracao de Imoveis
    'ALOS3': 'Exploracao de Imoveis',
    'MULT3': 'Exploracao de Imoveis',

    # Holdings Diversificadas
    'ITSA4': 'Holdings Diversificadas'
}

    
    @classmethod
    def get_all_setores(cls) -> List[str]:
        """Retorna lista unica de todos os setores"""
        return list(set(cls.TICKERS_SETORES.values()))
    
    @classmethod 
    def get_tickers_by_setor(cls, setor_nome: str) -> List[str]:
        """Retorna todos os tickers de um setor especifico"""
        return [ticker for ticker, setor in cls.TICKERS_SETORES.items() if setor == setor_nome]
    
    @staticmethod
    def get_historical_data(symbol: str, period: str = '2y') -> Optional[pd.DataFrame]:
        """Busca dados historicos"""
        try:
            if not symbol.endswith('.SA'):
                symbol += '.SA'
            
            logging.info(f"Buscando historico de {symbol} para RRG...")
            
            stock = yf.Ticker(symbol)
            data = stock.history(period=period)
            
            if data.empty:
                logging.warning(f"Nenhum dado historico para {symbol}")
                return None
            
            return data
            
        except Exception as e:
            logging.error(f"Erro ao buscar historico de {symbol}: {e}")
            return None
    
    @staticmethod
    def calculate_emas(data: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        """Calcula EMA65 (trimestre) e EMA252 (ano)"""
        try:
            if len(data) < 252:
                logging.warning(f"Dados insuficientes para EMA252 (tem {len(data)}, precisa 252+)")
                return None, None
            
            close_prices = data['Close']
            ema65 = close_prices.ewm(span=65, adjust=False).mean().iloc[-1]
            ema252 = close_prices.ewm(span=252, adjust=False).mean().iloc[-1]
            
            return float(ema65), float(ema252)
            
        except Exception as e:
            logging.error(f"Erro ao calcular EMAs: {e}")
            return None, None
    
    @staticmethod
    def calculate_slope(data: pd.DataFrame, period: int, lookback: int) -> Optional[float]:
        """Calcula inclinacao de uma EMA"""
        try:
            if len(data) < period + lookback:
                return None
            
            close_prices = data['Close']
            ema = close_prices.ewm(span=period, adjust=False).mean()
            
            ema_atual = ema.iloc[-1]
            ema_passado = ema.iloc[-(lookback + 1)]
            
            slope = ((ema_atual - ema_passado) / ema_passado) * 100
            return float(slope)
            
        except Exception as e:
            logging.error(f"Erro ao calcular slope: {e}")
            return None
    
    @staticmethod
    def calculate_momentum(data: pd.DataFrame, periods: int = 21) -> Optional[float]:
        """Calcula momentum baseado em variacao de N dias"""
        try:
            if len(data) < periods:
                return None
            
            close_prices = data['Close']
            preco_atual = close_prices.iloc[-1]
            preco_passado = close_prices.iloc[-(periods + 1)]
            
            momentum = ((preco_atual - preco_passado) / preco_passado) * 100
            return float(momentum)
            
        except Exception as e:
            logging.error(f"Erro ao calcular momentum: {e}")
            return None
    
    @staticmethod
    def calculate_volatilidade(data: pd.DataFrame, periods: int = 30) -> Optional[float]:
        """Calcula volatilidade anualizada"""
        try:
            if len(data) < periods:
                return None
            
            close_prices = data['Close'].tail(periods)
            returns = close_prices.pct_change().dropna()
            
            vol = returns.std() * np.sqrt(252) * 100
            return float(vol) if np.isfinite(vol) else None
            
        except Exception as e:
            logging.error(f"Erro ao calcular volatilidade: {e}")
            return None
    
    @staticmethod
    def classify_regime(dist_ema65: float, dist_ema252: float) -> str:
        """
        Classifica regime baseado na posicao relativa
        
        LEADING: Forte no curto E longo prazo
        IMPROVING: Ganhando forca (curto prazo positivo, longo negativo)
        WEAKENING: Perdendo forca (curto prazo negativo, longo positivo)
        LAGGING: Fraco no curto E longo prazo
        """
        if dist_ema65 > 0 and dist_ema252 > 0:
            return "Leading"
        elif dist_ema65 > 0 and dist_ema252 < 0:
            return "Improving"
        elif dist_ema65 < 0 and dist_ema252 > 0:
            return "Weakening"
        else:
            return "Lagging"
    
    @staticmethod
    def classify_forca_trimestral(dist_ema65: float) -> str:
        """Classifica forca de curto prazo"""
        if dist_ema65 > 10:
            return "Muito Forte"
        elif dist_ema65 > 5:
            return "Forte"
        elif dist_ema65 > 2:
            return "Moderadamente Forte"
        elif dist_ema65 > -2:
            return "Neutro"
        elif dist_ema65 > -5:
            return "Moderadamente Fraco"
        elif dist_ema65 > -10:
            return "Fraco"
        else:
            return "Muito Fraco"
    
    @staticmethod
    def classify_tendencia_anual(dist_ema252: float) -> str:
        """Classifica tendencia de longo prazo"""
        return "Valorizacao" if dist_ema252 > 0 else "Depreciacao"
    
    @staticmethod
    def calculate_projection(preco_atual: float, momentum: float, periods: int = 65) -> float:
        """Calcula projecao baseada no momentum"""
        try:
            fator_tempo = periods / 252
            projecao = preco_atual * (1 + (momentum / 100) * fator_tempo)
            return float(projecao)
        except Exception as e:
            logging.error(f"Erro ao calcular projecao: {e}")
            return preco_atual
    
    @classmethod
    @lru_cache(maxsize=200)
    def get_rrg_data_cached(cls, symbol: str) -> Optional[Dict]:
        """Versao com cache"""
        return cls.get_rrg_data(symbol)
    
    @classmethod
    def get_rrg_data(cls, symbol: str) -> Optional[Dict]:
        """Calcula todos os dados RRG para um ticker"""
        try:
            symbol_clean = symbol.upper().replace('.SA', '')
            
            # Validar ticker
            if not symbol_clean or len(symbol_clean) < 4:
                logging.warning(f"Ticker invalido: '{symbol_clean}'")
                return None
            
            data = cls.get_historical_data(symbol_clean, period='2y')
            
            if data is None or len(data) < 252:
                logging.warning(f"Dados insuficientes para {symbol_clean}")
                return None
            
            preco_atual = float(data['Close'].iloc[-1])
            
            ema65, ema252 = cls.calculate_emas(data)
            if ema65 is None or ema252 is None:
                return None
            
            dist_ema65 = ((preco_atual / ema65) - 1) * 100
            dist_ema252 = ((preco_atual / ema252) - 1) * 100
            
            slope_ema65 = cls.calculate_slope(data, period=65, lookback=30)
            slope_ema252 = cls.calculate_slope(data, period=252, lookback=60)
            
            momentum_21d = cls.calculate_momentum(data, periods=21)
            volatilidade = cls.calculate_volatilidade(data, periods=30)
            
            regime = cls.classify_regime(dist_ema65, dist_ema252)
            forca_trimestral = cls.classify_forca_trimestral(dist_ema65)
            tendencia_anual = cls.classify_tendencia_anual(dist_ema252)
            
            projecao_trimestral = cls.calculate_projection(preco_atual, momentum_21d or 0, periods=65)
            projecao_anual = cls.calculate_projection(preco_atual, momentum_21d or 0, periods=252)
            
            setor = cls.TICKERS_SETORES.get(symbol_clean, 'Setor Nao Classificado')
            
            return {
                'symbol': symbol_clean,
                'setor': setor,
                'preco_atual': round(preco_atual, 2),
                'ema65': round(ema65, 2),
                'ema252': round(ema252, 2),
                'dist_ema65_pct': round(dist_ema65, 2),
                'dist_ema252_pct': round(dist_ema252, 2),
                'regime': regime,
                'forca_trimestral': forca_trimestral,
                'tendencia_anual': tendencia_anual,
                'slope_ema65': round(slope_ema65, 2) if slope_ema65 else None,
                'slope_ema252': round(slope_ema252, 2) if slope_ema252 else None,
                'momentum_21d': round(momentum_21d, 2) if momentum_21d else None,
                'volatilidade_30d': round(volatilidade, 2) if volatilidade else None,
                'projecao_trimestral': round(projecao_trimestral, 2),
                'projecao_anual': round(projecao_anual, 2),
                'data_calculo': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'has_real_data': True
            }
            
        except Exception as e:
            logging.error(f"Erro ao calcular RRG para {symbol}: {e}")
            return None
    
    @classmethod
    def get_sector_rrg_data(cls, setor_nome: str) -> Optional[Dict]:
        """Calcula RRG medio de um setor"""
        try:
            logging.info(f"Calculando RRG do setor: {setor_nome}")
            
            tickers_do_setor = cls.get_tickers_by_setor(setor_nome)
            
            if not tickers_do_setor:
                logging.warning(f"Setor '{setor_nome}' nao encontrado")
                return None
            
            resultados_individuais = []
            
            for ticker in tickers_do_setor:
                logging.info(f"  Processando {ticker}...")
                rrg_data = cls.get_rrg_data_cached(ticker)
                
                if rrg_data:
                    resultados_individuais.append(rrg_data)
                    logging.info(f"    {ticker}: {rrg_data['regime']}")
            
            if not resultados_individuais:
                return None
            
            avg_dist_ema65 = np.mean([r['dist_ema65_pct'] for r in resultados_individuais])
            avg_dist_ema252 = np.mean([r['dist_ema252_pct'] for r in resultados_individuais])
            momentum_vals = [r['momentum_21d'] for r in resultados_individuais if r['momentum_21d'] is not None]
            vol_vals = [r['volatilidade_30d'] for r in resultados_individuais if r['volatilidade_30d'] is not None]

            avg_momentum = float(np.mean(momentum_vals)) if momentum_vals else 0.0
            avg_vol = float(np.mean(vol_vals)) if vol_vals else 0.0
            
            regimes = [r['regime'] for r in resultados_individuais]
            regime_predominante = max(set(regimes), key=regimes.count)
            
            return {
                'setor': setor_nome,
                'dist_ema65_pct': round(avg_dist_ema65, 2),
                'dist_ema252_pct': round(avg_dist_ema252, 2),
                'regime': regime_predominante,
                'momentum_21d': round(avg_momentum, 2),
                'volatilidade_30d': round(avg_vol, 2),
                'empresas_com_dados': len(resultados_individuais),
                'total_empresas': len(tickers_do_setor),
                'detalhes_empresas': resultados_individuais,
                'distribuicao_regimes': {
                    'Leading': regimes.count('Leading'),
                    'Improving': regimes.count('Improving'),
                    'Weakening': regimes.count('Weakening'),
                    'Lagging': regimes.count('Lagging')
                },
                'has_real_data': True,
                'data_calculo': datetime.now().strftime('%d/%m/%Y %H:%M')
            }
            
        except Exception as e:
            logging.error(f"Erro ao calcular RRG do setor {setor_nome}: {e}")
            return None
    
    @classmethod
    def get_all_sectors_rrg(cls) -> Dict[str, Dict]:
        """Calcula RRG para todos os setores"""
        logging.info("Calculando RRG para todos os setores...")
        
        setores = cls.get_all_setores()
        resultados = {}
        
        for i, setor in enumerate(setores, 1):
            logging.info(f"Processando setor {i}/{len(setores)}: {setor}")
            rrg_data = cls.get_sector_rrg_data(setor)
            
            if rrg_data:
                resultados[setor] = rrg_data
        
        logging.info(f"Concluido! {len(resultados)}/{len(setores)} setores processados")
        return resultados
    
    @staticmethod
    def clear_cache():
        """Limpa cache"""
        YFinanceRRGService.get_rrg_data_cached.cache_clear()
        logging.info("Cache RRG limpo!")
    
    @staticmethod
    def get_cache_info() -> Dict:
        """Info do cache"""
        cache_info = YFinanceRRGService.get_rrg_data_cached.cache_info()
        return {
            'hits': cache_info.hits,
            'misses': cache_info.misses,
            'maxsize': cache_info.maxsize,
            'currsize': cache_info.currsize,
            'hit_rate': round((cache_info.hits / (cache_info.hits + cache_info.misses)) * 100, 2) 
                        if (cache_info.hits + cache_info.misses) > 0 else 0
        }


if __name__ == "__main__":
    service = YFinanceRRGService()
    
    result = service.get_rrg_data('PETR4')
    if result:
        print(f"\n{result['symbol']}: {result['regime']}")
        print(f"  Curto Prazo: {result['dist_ema65_pct']}%")
        print(f"  Longo Prazo: {result['dist_ema252_pct']}%")
        print(f"  Projecao Trimestral: R$ {result['projecao_trimestral']}")