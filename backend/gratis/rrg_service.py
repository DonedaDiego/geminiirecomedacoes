"""
rrg_service.py - Relative Rotation Graph (RRG) Analysis
Análise de Força Relativa Trimestral vs Anual usando EMAs 65 e 252
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
    """Serviço completo para análise RRG usando YFinance"""
    
    #  DICIONÁRIO DE TICKERS E SETORES (mesma base do RSL)
    TICKERS_SETORES = {
        'BRAV3': 'Petróleo, Gás e Bio',
        'CSAN3': 'Petróleo, Gás e Bio',
        'RPMG3': 'Petróleo, Gás e Bio',
        'PETR4': 'Petróleo, Gás e Bio',
        'RECV3': 'Petróleo, Gás e Bio',
        'PRIO3': 'Petróleo, Gás e Bio',
        'RAIZ4': 'Petróleo, Gás e Bio',
        'UGPA3': 'Petróleo, Gás e Bio',
        'VBBR3': 'Petróleo, Gás e Bio',
        'AURA33': 'Mineração',
        'BRAP4': 'Mineração',
        'CBAV3': 'Mineração',
        'VALE3': 'Mineração',
        'GGBR4': 'Siderurgia e Metalurgia',
        'GOAU4': 'Siderurgia e Metalurgia',
        'CSNA3': 'Siderurgia e Metalurgia',
        'USIM5': 'Siderurgia e Metalurgia',
        'BRKM5': 'Químicos',
        'KLBN11': 'Madeira e Papel',
        'SUZB3': 'Madeira e Papel',
        'EMBJ3': 'Transporte',
        'FRAS3': 'Transporte',
        'POMO4': 'Transporte',
        'RAPT4': 'Transporte',
        'RAIL3': 'Transporte',
        'JSLG3': 'Transporte',
        'TGMA3': 'Transporte',
        '3': 'Transporte',        
        '': 'Transporte',
        'WEGE3': 'Máquinas',
        'ROMI3': 'Máquinas',
        'TASA4': 'Máquinas',
        'AGXY3': 'Agropecuária',
        'SOJA3': 'Agropecuária',
        'AGRO3': 'Agropecuária',
        'SLCE3': 'Agropecuária',
        'SMTO3': 'Alimentos',
        'MRFG3': 'Alimentos',
        'BEEF3': 'Alimentos',
        'ODER4': 'Alimentos',
        'ABEV3': 'Bebidas',
        'NATU3': 'Produtos',
        'ASAI3': 'Produtos',
        'CEDO4': 'Tecidos, Ves, Cal',
        'SGPS3': 'Tecidos, Ves, Cal',
        'ALPA4': 'Tecidos, Ves, Cal',
        'CAMB3': 'Tecidos, Ves, Cal',
        'GRND3': 'Tecidos, Ves, Cal',
        'VULC3': 'Tecidos, Ves, Cal',
        'MNDL3': 'Tecidos, Ves, Cal',
        'TECN3': 'Tecidos, Ves, Cal',
        'VIVA3': 'Tecidos, Ves, Cal',
        'MYPK3': 'Automóveis',
        'LEVE3': 'Automóveis',
        'BMKS3': 'Viagens e Lazer',
        'ESTR3': 'Viagens e Lazer',
        'SHOW3': 'Viagens e Lazer',
        'CVCB3': 'Viagens e Lazer',
        'BHIA3': 'Diversos',
        'COGN3': 'Diversos',
        'CSED3': 'Diversos',
        'YDUQ3': 'Diversos',
        'RENT3': 'Diversos',
        'MOVI3': 'Diversos',
        'VAMO3': 'Diversos',
        'DOTZ3': 'Diversos',
        'AZZA3': 'Varejista',
        'CEAB3': 'Varejista',
        'CGRA4': 'Varejista',
        'GUAR3': 'Varejista',
        'AMAR3': 'Varejista',
        'LREN3': 'Varejista',
        'ALLD3': 'Varejista',
        'MGLU3': 'Varejista',
        'PETZ3': 'Varejista',
        'FLRY3': 'Serviços Médico',
        'ODPV3': 'Serviços Médico',
        'ONCO3': 'Serviços Médico',
        'QUAL3': 'Serviços Médico',
        'RDOR3': 'Serviços Médico',
        'TRAD3': 'Serviços',
        'TOTS3': 'Serviços',
        'ALUP11': 'Energia',
        'CBEE3': 'Energia',
        'AURE3': 'Energia',
        'CEBR3': 'Energia',
        'CEED3': 'Energia',
        'CLSC3': 'Energia',
        'CMIG4': 'Energia',
        'CEEB3': 'Energia',
        'COCE5': 'Energia',
        'CPLE3': 'Energia',
        'CPFE3': 'Energia',
        'AXIA6': 'Energia',
        'ENGI4': 'Energia',
        'ENEV3': 'Energia',
        'EGIE3': 'Energia',
        'EQTL3': 'Energia',
        'GEPA3': 'Energia',
        'LIGT3': 'Energia',
        'NEOE3': 'Energia',
        'TAEE11': 'Energia',
        'AMBP3': 'Saneamento',
        'CASN3': 'Saneamento',
        'CSMG3': 'Saneamento',
        'SAPR4': 'Saneamento',
        'CEGR3': 'Gás',
        'ABCB4': 'Inter Financeiros',
        'BMGB4': 'Inter Financeiros',
        'BPAN4': 'Inter Financeiros',
        'BEES3': 'Inter Financeiros',
        'BPAR3': 'Inter Financeiros',
        'BBDC4': 'Inter Financeiros',
        'BBAS3': 'Inter Financeiros',
        'BPAC11': 'Inter Financeiros',
        'ITUB4': 'Inter Financeiros',
        'BMEB4': 'Inter Financeiros',
        'BNBR3': 'Inter Financeiros',
        'PINE4': 'Inter Financeiros',
        'SANB11': 'Inter Financeiros',
        'B3SA3': 'Ser Financeiros',
        'BBSE3': 'Previdência e Seguros',
        'CXSE3': 'Previdência e Seguros',
        'PSSA3': 'Previdência e Seguros',
        'IRBR3': 'Previdência e Seguros',
        'WIZC3': 'Previdência e Seguros',
        'ALOS3': 'Exploração de Imóveis',
        'HBRE3': 'Exploração de Imóveis',
        'LOGG3': 'Exploração de Imóveis',
        'MULT3': 'Exploração de Imóveis',
        'SYNE3': 'Exploração de Imóveis',
        'ITSA4': 'Holdings Diversificadas',
        'MOAR3': 'Holdings Diversificadas',
        'SIMH3': 'Holdings Diversificadas'
    }
    
    @classmethod
    def get_all_setores(cls) -> List[str]:
        """Retorna lista única de todos os setores"""
        return list(set(cls.TICKERS_SETORES.values()))
    
    @classmethod 
    def get_tickers_by_setor(cls, setor_nome: str) -> List[str]:
        """Retorna todos os tickers de um setor específico"""
        return [ticker for ticker, setor in cls.TICKERS_SETORES.items() if setor == setor_nome]
    
    @staticmethod
    def get_historical_data(symbol: str, period: str = '2y') -> Optional[pd.DataFrame]:
        """Busca dados históricos (precisa de 2 anos para calcular EMA252 corretamente)"""
        try:
            if not symbol.endswith('.SA'):
                symbol += '.SA'
            
            logging.info(f" Buscando histórico de {symbol} para RRG...")
            
            stock = yf.Ticker(symbol)
            data = stock.history(period=period)
            
            if data.empty:
                logging.warning(f" Nenhum dado histórico para {symbol}")
                return None
            
            return data
            
        except Exception as e:
            logging.error(f"❌ Erro ao buscar histórico de {symbol}: {e}")
            return None
    
    @staticmethod
    def calculate_emas(data: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        """Calcula EMA65 (trimestre) e EMA252 (ano)"""
        try:
            if len(data) < 252:
                logging.warning(f" Dados insuficientes para EMA252 (tem {len(data)}, precisa 252+)")
                return None, None
            
            close_prices = data['Close']
            
            
            ema65 = close_prices.ewm(span=65, adjust=False).mean().iloc[-1]
            
            
            ema252 = close_prices.ewm(span=252, adjust=False).mean().iloc[-1]
            
            return float(ema65), float(ema252)
            
        except Exception as e:
            logging.error(f"❌ Erro ao calcular EMAs: {e}")
            return None, None
    
    @staticmethod
    def calculate_slope(data: pd.DataFrame, period: int, lookback: int) -> Optional[float]:
        """
        Calcula inclinação (taxa de variação) de uma EMA
        period: período da EMA (65 ou 252)
        lookback: quantos dias atrás comparar (30 para EMA65, 60 para EMA252)
        """
        try:
            if len(data) < period + lookback:
                return None
            
            close_prices = data['Close']
            ema = close_prices.ewm(span=period, adjust=False).mean()
            
            ema_atual = ema.iloc[-1]
            ema_passado = ema.iloc[-(lookback + 1)]
            
            # Taxa de variação percentual
            slope = ((ema_atual - ema_passado) / ema_passado) * 100
            
            return float(slope)
            
        except Exception as e:
            logging.error(f"❌ Erro ao calcular slope: {e}")
            return None
    
    @staticmethod
    def calculate_momentum(data: pd.DataFrame, periods: int = 21) -> Optional[float]:
        """Calcula velocidade/momentum baseado em variação de N dias"""
        try:
            if len(data) < periods:
                return None
            
            close_prices = data['Close']
            
            preco_atual = close_prices.iloc[-1]
            preco_passado = close_prices.iloc[-(periods + 1)]
            
            momentum = ((preco_atual - preco_passado) / preco_passado) * 100
            
            return float(momentum)
            
        except Exception as e:
            logging.error(f"❌ Erro ao calcular momentum: {e}")
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
            logging.error(f"❌ Erro ao calcular volatilidade: {e}")
            return None
    
    @staticmethod
    def classify_regime(dist_ema65: float, dist_ema252: float) -> str:
        """
        Classifica regime baseado na posição relativa às EMAs
        
        LEADING (🟢): Acima EMA65 E EMA252
        IMPROVING (🔵): Abaixo EMA252, mas acima EMA65 (recuperação)
        WEAKENING (🟡): Acima EMA252, mas abaixo EMA65 (enfraquecendo)
        LAGGING (🔴): Abaixo EMA65 E EMA252
        """
        if dist_ema65 > 0 and dist_ema252 > 0:
            return "Leading"
        elif dist_ema65 > 0 and dist_ema252 < 0:
            return "Improving"
        elif dist_ema65 < 0 and dist_ema252 > 0:
            return "Weakening"
        else:  # ambos negativos
            return "Lagging"
    
    @staticmethod
    def classify_forca_trimestral(dist_ema65: float) -> str:
        """Classifica força trimestral baseado na distância do EMA65"""
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
        """Classifica tendência anual baseado na distância do EMA252"""
        return "Valorização" if dist_ema252 > 0 else "Depreciação"
    
    @staticmethod
    def calculate_projection(preco_atual: float, momentum: float, periods: int = 65) -> float:
        """
        Calcula projeção baseada no momentum
        periods=65 para trimestre, periods=252 para ano
        """
        try:
            # Projeção simples: preço atual + (momentum ajustado pelo período)
            fator_tempo = periods / 252  # Normaliza para base anual
            projecao = preco_atual * (1 + (momentum / 100) * fator_tempo)
            
            return float(projecao)
            
        except Exception as e:
            logging.error(f"❌ Erro ao calcular projeção: {e}")
            return preco_atual
    
    @classmethod
    @lru_cache(maxsize=200)
    def get_rrg_data_cached(cls, symbol: str) -> Optional[Dict]:
        """Versão com cache"""
        return cls.get_rrg_data(symbol)
    
    @classmethod
    def get_rrg_data(cls, symbol: str) -> Optional[Dict]:
        """
        Calcula todos os dados RRG para um ticker
        """
        try:
            symbol_clean = symbol.upper().replace('.SA', '')
            
            # 1️⃣ BUSCAR DADOS HISTÓRICOS
            data = cls.get_historical_data(symbol_clean, period='2y')
            
            if data is None or len(data) < 252:
                logging.warning(f" Dados insuficientes para {symbol_clean}")
                return None
            
            # 2️⃣ PREÇO ATUAL
            preco_atual = float(data['Close'].iloc[-1])
            
            # 3️⃣ CALCULAR EMAs
            ema65, ema252 = cls.calculate_emas(data)
            
            if ema65 is None or ema252 is None:
                return None
            
            # 4️⃣ DISTÂNCIAS PERCENTUAIS
            dist_ema65 = ((preco_atual / ema65) - 1) * 100
            dist_ema252 = ((preco_atual / ema252) - 1) * 100
            
            # 5️⃣ INCLINAÇÕES (SLOPES)
            slope_ema65 = cls.calculate_slope(data, period=65, lookback=30)
            slope_ema252 = cls.calculate_slope(data, period=252, lookback=60)
            
            # 6️⃣ MOMENTUM
            momentum_21d = cls.calculate_momentum(data, periods=21)
            
            # 7️⃣ VOLATILIDADE
            volatilidade = cls.calculate_volatilidade(data, periods=30)
            
            # 8️⃣ CLASSIFICAÇÕES
            regime = cls.classify_regime(dist_ema65, dist_ema252)
            forca_trimestral = cls.classify_forca_trimestral(dist_ema65)
            tendencia_anual = cls.classify_tendencia_anual(dist_ema252)
            
            # 9️⃣ PROJEÇÕES
            projecao_trimestral = cls.calculate_projection(preco_atual, momentum_21d or 0, periods=65)
            projecao_anual = cls.calculate_projection(preco_atual, momentum_21d or 0, periods=252)
            
            # 🔟 SETOR
            setor = cls.TICKERS_SETORES.get(symbol_clean, 'Setor Não Classificado')
            
            #  RESULTADO FINAL
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
            logging.error(f"❌ Erro ao calcular RRG para {symbol}: {e}")
            return None
    
    @classmethod
    def get_sector_rrg_data(cls, setor_nome: str) -> Optional[Dict]:
        """Calcula RRG médio de um setor"""
        try:
            logging.info(f" Calculando RRG do setor: {setor_nome}")
            
            tickers_do_setor = cls.get_tickers_by_setor(setor_nome)
            
            if not tickers_do_setor:
                logging.warning(f" Setor '{setor_nome}' não encontrado")
                return None
            
            resultados_individuais = []
            
            for ticker in tickers_do_setor:
                logging.info(f"   Processando {ticker}...")
                
                rrg_data = cls.get_rrg_data_cached(ticker)
                
                if rrg_data:
                    resultados_individuais.append(rrg_data)
                    logging.info(f"      {ticker}: {rrg_data['regime']}")
            
            if not resultados_individuais:
                return None
            
            #  MÉDIAS DO SETOR
            avg_dist_ema65 = np.mean([r['dist_ema65_pct'] for r in resultados_individuais])
            avg_dist_ema252 = np.mean([r['dist_ema252_pct'] for r in resultados_individuais])
            avg_momentum = np.mean([r['momentum_21d'] for r in resultados_individuais if r['momentum_21d']])
            avg_vol = np.mean([r['volatilidade_30d'] for r in resultados_individuais if r['volatilidade_30d']])
            
            # Regime predominante
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
            logging.error(f"❌ Erro ao calcular RRG do setor {setor_nome}: {e}")
            return None
    
    @classmethod
    def get_all_sectors_rrg(cls) -> Dict[str, Dict]:
        """Calcula RRG para todos os setores"""
        logging.info(" Calculando RRG para todos os setores...")
        
        setores = cls.get_all_setores()
        resultados = {}
        
        for i, setor in enumerate(setores, 1):
            logging.info(f" Processando setor {i}/{len(setores)}: {setor}")
            
            rrg_data = cls.get_sector_rrg_data(setor)
            
            if rrg_data:
                resultados[setor] = rrg_data
        
        logging.info(f" Concluído! {len(resultados)}/{len(setores)} setores processados")
        return resultados
    
    @staticmethod
    def clear_cache():
        """Limpa cache"""
        YFinanceRRGService.get_rrg_data_cached.cache_clear()
        logging.info("🧹 Cache RRG limpo!")
    
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


# 🧪 TESTE
if __name__ == "__main__":
    service = YFinanceRRGService()
    
    # Teste individual
    result = service.get_rrg_data('PETR4')
    if result:
        print(f"\n {result['symbol']}: {result['regime']}")
        print(f"   EMA65: {result['dist_ema65_pct']}%")
        print(f"   EMA252: {result['dist_ema252_pct']}%")
        print(f"   Projeção Trimestral: R$ {result['projecao_trimestral']}")