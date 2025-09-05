import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from functools import lru_cache
from typing import Dict, List, Optional

class YFinanceRSLService:
    """Serviço completo para cálculo de RSL usando YFinance + banco de dados"""
    
    # ✅ DICIONÁRIO DE TICKERS E SETORES (BASE DE DADOS)
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
        'EMBR3': 'Transporte',
        'FRAS3': 'Transporte',
        'POMO4': 'Transporte',
        'RAPT4': 'Transporte',
        'TUPY3': 'Transporte',
        'AZUL4': 'Transporte',
        #'GOLL4': 'Transporte',
        'RAIL3': 'Transporte',
        'JSLG3': 'Transporte',
        'TGMA3': 'Transporte',
        'CCRO3': 'Transporte',
        'STBP3': 'Transporte',
        'PORT3': 'Transporte',
        'WEGE3': 'Máquinas',
        'ROMI3': 'Máquinas',
        'TASA4': 'Máquinas',
        'AGXY3': 'Agropecuária',
        'SOJA3': 'Agropecuária',
        'AGRO3': 'Agropecuária',
        'SLCE3': 'Agropecuária',
        'SMTO3': 'Alimentos',
        'BRFS3': 'Alimentos',
        'MRFG3': 'Alimentos',
        'BEEF3': 'Alimentos',
        'ODER4': 'Alimentos',
        'ABEV3': 'Bebidas',
        'NTCO3': 'Produtos',
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
        'BHIA3': 'Varejista',
        'MGLU3': 'Varejista',
        'PETZ3': 'Varejista',
        'FLRY3': 'Serviços Médico',
        'ODPV3': 'Serviços Médico',
        'ONCO3': 'Serviços Médico',
        'QUAL3': 'Serviços Médico',
        'RDOR3': 'Serviços Médico',
        'TRAD3': 'Serviços',
        'TOTS3': 'Serviços',
       # 'OIBR3': 'Telecomunicações',
       # 'VIVT3': 'Telecomunicações',
       # 'TIMS3': 'Telecomunicações',
        'ALUP11': 'Energia',
        'CBEE3': 'Energia',
        'AURE3': 'Energia',
        'CEBR3': 'Energia',
        'CEED3': 'Energia',
        'CLSC3': 'Energia',
        'CMIG4': 'Energia',
        'CEEB3': 'Energia',
        'COCE5': 'Energia',
        'CPLE6': 'Energia',
        'CPFE3': 'Energia',
        'ELET6': 'Energia',
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
    
    @classmethod
    def get_setor_info(cls) -> Dict:
        """Retorna estatísticas dos setores"""
        setores_stats = {}
        
        for setor in cls.get_all_setores():
            tickers = cls.get_tickers_by_setor(setor)
            setores_stats[setor] = {
                'total_empresas': len(tickers),
                'tickers': tickers
            }
        
        return setores_stats
    
    @staticmethod
    def get_historical_data(symbol: str, period: str = '1y') -> Optional[pd.Series]:
        """Busca dados históricos para cálculo do RSL"""
        try:
            # Normalizar ticker
            if not symbol.endswith('.SA'):
                symbol += '.SA'
            
            print(f" Buscando histórico de {symbol} para RSL...")
            
            stock = yf.Ticker(symbol)
            data = stock.history(period=period)
            
            if data.empty:
                print(f"⚠️ Nenhum dado histórico para {symbol}")
                return None
            
            return data['Close']
            
        except Exception as e:
            print(f"❌ Erro ao buscar histórico de {symbol}: {e}")
            return None
    
    @staticmethod
    def calculate_rsl(price_series: pd.Series, periodo_mm: int = 30) -> Optional[float]:
        """
        Calcula RSL exatamente como no MetaTrader:
        RSL = ((Close / MM) - 1) * 100
        """
        try:
            if price_series is None or len(price_series) < periodo_mm:
                return None
            
            # ✅ FÓRMULA IDÊNTICA AO METATRADER
            # Calcular Média Móvel
            mm = price_series.rolling(window=periodo_mm).mean()
            
            # Calcular RSL = ((Close / MM) - 1) * 100
            rsl_series = ((price_series / mm) - 1) * 100
            
            # Retornar o último valor válido
            rsl_atual = rsl_series.dropna().tail(1)
            
            if len(rsl_atual) == 0:
                return None
                
            return float(rsl_atual.values[0])
            
        except Exception as e:
            print(f"❌ Erro ao calcular RSL: {e}")
            return None
    
    @staticmethod
    def calculate_volatilidade(price_series: pd.Series) -> Optional[float]:
        try:
            if price_series is None or len(price_series) < 30:
                return None
            
            # ✅ FÓRMULA IDÊNTICA AO METATRADER
            # Calcular retornos percentuais
            returns = price_series.pct_change()
            
            # Volatilidade anualizada
            vol = returns.std() * np.sqrt(252) * 100
            
            return float(vol) if np.isfinite(vol) else None
            
        except Exception as e:
            print(f"❌ Erro ao calcular volatilidade: {e}")
            return None
    
    @staticmethod
    @lru_cache(maxsize=200)
    def get_rsl_data_cached(symbol: str, period: str = '1y') -> Optional[Dict]:
        """Versão com cache do get_rsl_data para otimização"""
        return YFinanceRSLService.get_rsl_data(symbol, period)
    
    @staticmethod
    def get_rsl_data(symbol: str, period: str = '1y', periodo_mm: int = 30) -> Optional[Dict]:
        """Calcula RSL e Volatilidade para um ticker específico"""
        try:
            # Buscar dados históricos
            price_data = YFinanceRSLService.get_historical_data(symbol, period)
            
            if price_data is None:
                return None
            
            # Calcular RSL
            rsl = YFinanceRSLService.calculate_rsl(price_data, periodo_mm)
            
            # Calcular Volatilidade
            volatilidade = YFinanceRSLService.calculate_volatilidade(price_data)
            
            
            if rsl is None or volatilidade is None:
                return None
            
            # Calcular MM atual
            mm_atual = price_data.rolling(window=periodo_mm).mean().iloc[-1]
            
            # Verificar se o ticker está na nossa base
            setor = YFinanceRSLService.TICKERS_SETORES.get(symbol, 'Setor Não Classificado')
            
            return {
                'symbol': symbol.replace('.SA', ''),
                'rsl': round(float(rsl), 2),
                'volatilidade': round(float(volatilidade), 2),
                'close_atual': round(float(price_data.iloc[-1]), 2),
                'mm_30': round(float(mm_atual), 2),
                'setor': setor,
                'data_calculo': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'periodo_usado': period,
                'periodo_mm': periodo_mm,
                'pontos_dados': len(price_data),
                'has_real_data': True
            }
            
        except Exception as e:
            print(f"❌ Erro ao calcular RSL para {symbol}: {e}")
            return None
    
    @classmethod
    def get_sector_rsl_data(cls, setor_nome: str, period: str = '1y') -> Optional[Dict]:
        """
        Calcula RSL médio de um setor usando nosso dicionário de tickers
        """
        try:
            print(f" Calculando RSL do setor: {setor_nome}")
            
            # ✅ BUSCAR TICKERS DO SETOR NO NOSSO DICIONÁRIO
            tickers_do_setor = cls.get_tickers_by_setor(setor_nome)
            
            if not tickers_do_setor:
                print(f"⚠️ Setor '{setor_nome}' não encontrado na base de dados")
                return None
            
            print(f"📋 Tickers encontrados: {tickers_do_setor}")
            
            resultados_individuais = []
            
            # ✅ CALCULAR RSL PARA CADA TICKER DO SETOR
            for ticker in tickers_do_setor:
                print(f"  ⚡ Processando {ticker}...")
                
                # Usar versão com cache para otimizar
                rsl_data = cls.get_rsl_data_cached(ticker, period)
                
                if rsl_data:
                    resultados_individuais.append(rsl_data)
                    print(f"    ✅ {ticker}: RSL={rsl_data['rsl']}%, Vol={rsl_data['volatilidade']}%")
                else:
                    print(f"    ❌ {ticker}: Sem dados RSL")
            
            if not resultados_individuais:
                print(f"  ⚠️ Nenhum ticker válido para RSL em {setor_nome}")
                return None
            
            # ✅ CALCULAR MÉDIAS COMO NO METATRADER
            rsl_values = [r['rsl'] for r in resultados_individuais]
            vol_values = [r['volatilidade'] for r in resultados_individuais if r.get('volatilidade') is not None and np.isfinite(r['volatilidade'])]

            
            rsl_medio = np.mean(rsl_values)
            vol_media = np.mean(vol_values)
            
            return {
                'setor': setor_nome,
                'rsl': round(float(rsl_medio), 2),
                'volatilidade': round(float(vol_media), 2),
                'empresas_com_dados': len(resultados_individuais),
                'total_empresas': len(tickers_do_setor),
                'taxa_sucesso': round((len(resultados_individuais) / len(tickers_do_setor)) * 100, 1),
                'detalhes_empresas': resultados_individuais,
                'has_real_data': True,
                'data_calculo': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'tickers_processados': [r['symbol'] for r in resultados_individuais],
                'tickers_faltantes': list(set(tickers_do_setor) - set([r['symbol'] for r in resultados_individuais]))
            }
            
        except Exception as e:
            print(f"❌ Erro ao calcular RSL do setor {setor_nome}: {e}")
            return None
    
    @classmethod
    def get_all_sectors_rsl(cls, period: str = '1y') -> Dict[str, Dict]:
        """Calcula RSL para todos os setores da nossa base"""
        print("🚀 Calculando RSL para todos os setores...")
        
        setores = cls.get_all_setores()
        resultados = {}
        
        for i, setor in enumerate(setores, 1):
            print(f" Processando setor {i}/{len(setores)}: {setor}")
            
            rsl_data = cls.get_sector_rsl_data(setor, period)
            
            if rsl_data:
                resultados[setor] = rsl_data
                print(f"✅ {setor}: RSL={rsl_data['rsl']}%, Vol={rsl_data['volatilidade']}%")
            else:
                print(f"❌ {setor}: Falha no cálculo")
        
        print(f" Concluído! {len(resultados)}/{len(setores)} setores processados")
        return resultados
    
    @classmethod
    def get_ticker_rsl(cls, ticker: str, period: str = '1y') -> Optional[Dict]:
        """Busca RSL de um ticker específico"""
        ticker = ticker.upper().replace('.SA', '')
        
        # Verificar se o ticker existe na nossa base
        if ticker not in cls.TICKERS_SETORES:
            print(f"⚠️ Ticker {ticker} não encontrado na base de dados")
            return None
        
        return cls.get_rsl_data_cached(ticker, period)
    
    @classmethod
    def get_database_info(cls) -> Dict:
        """Retorna informações sobre a base de dados"""
        setores_info = cls.get_setor_info()
        
        return {
            'total_tickers': len(cls.TICKERS_SETORES),
            'total_setores': len(setores_info),
            'setores_detalhes': setores_info,
            'maior_setor': max(setores_info.items(), key=lambda x: x[1]['total_empresas']),
            'menor_setor': min(setores_info.items(), key=lambda x: x[1]['total_empresas']),
            'media_empresas_por_setor': round(np.mean([info['total_empresas'] for info in setores_info.values()]), 1)
        }
    
    @staticmethod
    def clear_cache():
        """Limpa o cache do RSL"""
        YFinanceRSLService.get_rsl_data_cached.cache_clear()
        print("🧹 Cache RSL limpo com sucesso!")
    
    @staticmethod
    def get_cache_info() -> Dict:
        """Retorna informações sobre o cache"""
        cache_info = YFinanceRSLService.get_rsl_data_cached.cache_info()
        return {
            'hits': cache_info.hits,
            'misses': cache_info.misses,
            'maxsize': cache_info.maxsize,
            'currsize': cache_info.currsize,
            'hit_rate': round((cache_info.hits / (cache_info.hits + cache_info.misses)) * 100, 2) if (cache_info.hits + cache_info.misses) > 0 else 0
        }

# ✅ EXEMPLO DE USO (para testes)
if __name__ == "__main__":
    # Teste básico
    service = YFinanceRSLService()
    