import requests
import pandas as pd
import os
from datetime import datetime

class RankingService:
    def __init__(self):
        self.token = self._get_token()
        self.base_url = "https://api.oplab.com.br/v3/market/stocks"
        self.headers = {
            "Access-Token": self.token,
            "Content-Type": "application/json"
        }
        
        # Lista de ações com opções
        self.options_stocks = [
            'ABEV3', 'ALOS3', 'ASAI3', 'AURE3', 'AZUL4', 'AZZA3', 'B3SA3', 'BBAS3', 
            'BBDC3', 'BBDC4', 'BBSE3', 'BEEF3', 'BPAC11', 'BRAP4', 'BRAV3', 'MBRF', 
            'BRKM5', 'CMIG4', 'CMIN3', 'COGN3', 'CPFE3', 'CPLE6', 'CSAN3', 'CSNA3', 
            'CVCB3', 'CXSE3', 'CYRE3', 'DIRR3', 'EGIE3', 'AXIA3', 'AXIA6', 'EMBJ3', 
            'ENEV3', 'ENGI11', 'EQTL3', 'FLRY3', 'GGBR4', 'GOAU4', 'HAPV3', 'HYPE3', 
            'IGTI11', 'IRBR3', 'ISAE4', 'ITSA4', 'ITUB4', 'KLBN11', 'LREN3', 'MGLU3', 
            'MOTV3', 'MRFG3', 'MRVE3', 'MULT3', 'NATU3', 'PCAR3', 'PETR3', 'PETR4', 
            'PETZ3', 'POMO4', 'PRIO3', 'PSSA3', 'RADL3', 'RAIL3', 'RAIZ4', 'RDOR3', 
            'RECV3', 'RENT3', 'SANB11', 'SBSP3', 'SLCE3', 'SMFT3', 'SMTO3', 'STBP3', 
            'SUZB3', 'TAEE11', 'TIMS3', 'TOTS3', 'UGPA3', 'USIM5', 'VALE3', 'VAMO3', 
            'VBBR3', 'VIVA3', 'VIVT3', 'WEGE3', 'YDUQ3'
        ]
        
        print(f" RankingService inicializado com {len(self.options_stocks)} ações")
    
    def _get_token(self):
        """Busca token do .env ou Railway"""
        token = os.environ.get('OPLAB_TOKEN')
        if token:
            print(" Token OpLab da variável de ambiente")
            return token
        
        # Fallback se não encontrar (não deve acontecer em produção)
        raise Exception(" Token OPLAB_TOKEN não encontrado nas variáveis de ambiente")
    
    def fetch_data(self, rank_by="iv_current", sort="desc", limit=150):
        """Busca dados do OpLab"""
        try:
            params = {
                "rank_by": rank_by,
                "sort": sort,
                "limit": limit
            }
            
            print(f"🔍 Buscando dados: {rank_by} (limit: {limit})")
            
            response = requests.get(self.base_url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                print(f"📦 Recebidos: {len(data)} registros")
                
                # Filtrar apenas ações com opções
                filtered = [item for item in data if item.get('symbol') in self.options_stocks]
                print(f" Filtrados: {len(filtered)} ações com opções")
                
                return filtered
            else:
                print(f" Erro API: {response.status_code}")
                return None
                
        except Exception as e:
            print(f" Erro na requisição: {e}")
            return None
    
    def process_data(self, data):
        """Processa dados em DataFrame"""
        if not data:
            return None
        
        try:
            df = pd.DataFrame(data)
            
            # Verificar colunas essenciais
            required = ['symbol', 'iv_current']
            missing = [col for col in required if col not in df.columns]
            if missing:
                print(f" Colunas faltando: {missing}")
                return None
            
            # Limpar dados
            initial_count = len(df)
            df = df.dropna(subset=['iv_current'])
            df = df.sort_values('iv_current', ascending=False)
            
            print(f" Processados: {len(df)} de {initial_count} registros")
            return df
            
        except Exception as e:
            print(f" Erro no processamento: {e}")
            return None
    
    def calculate_statistics(self, df):
        """Calcula estatísticas da IV"""
        if df is None or df.empty:
            return {}
        
        try:
            stats = {}
            if 'iv_current' in df.columns:
                iv_data = df['iv_current'].dropna()
                if len(iv_data) > 0:
                    stats = {
                        'iv_media': float(iv_data.mean()) if not pd.isna(iv_data.mean()) else 0.0,
                        'iv_mediana': float(iv_data.median()) if not pd.isna(iv_data.median()) else 0.0,
                        'iv_min': float(iv_data.min()) if not pd.isna(iv_data.min()) else 0.0,
                        'iv_max': float(iv_data.max()) if not pd.isna(iv_data.max()) else 0.0,
                        'iv_std': float(iv_data.std()) if not pd.isna(iv_data.std()) else 0.0
                    }
                else:
                    stats = {
                        'iv_media': 0.0,
                        'iv_mediana': 0.0,
                        'iv_min': 0.0,
                        'iv_max': 0.0,
                        'iv_std': 0.0
                    }
            return stats
        except Exception as e:
            print(f" Erro no cálculo de estatísticas: {e}")
            return {
                'iv_media': 0.0,
                'iv_mediana': 0.0,
                'iv_min': 0.0,
                'iv_max': 0.0,
                'iv_std': 0.0
            }
    
    def _clean_numeric_value(self, value):
        """Limpa valores numéricos - converte NaN, None, etc para 0"""
        if value is None or pd.isna(value):
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def create_ranking(self, df, top_n):
        """Cria ranking das ações"""
        if df is None or df.empty:
            return []
        
        try:
            ranking = []
            for idx, (_, row) in enumerate(df.head(top_n).iterrows(), 1):
                ranking.append({
                    'posicao': idx,
                    'symbol': row['symbol'],
                    'name': row.get('name', ''),
                    'iv_current': self._clean_numeric_value(row.get('iv_current')),
                    'close': self._clean_numeric_value(row.get('close')),
                    'volume': int(self._clean_numeric_value(row.get('volume'))),
                    'financial_volume': max(1.0, self._clean_numeric_value(row.get('financial_volume'))),  # Mínimo 1 para log
                    'variation': self._clean_numeric_value(row.get('variation')),
                    'iv_6m_percentile': self._clean_numeric_value(row.get('iv_6m_percentile')),
                    'iv_6m_max': self._clean_numeric_value(row.get('iv_6m_max'))
                })
            return ranking
        except Exception as e:
            print(f" Erro na criação do ranking: {e}")
            return []
    
    def get_top_iv(self, df, tipo, quantidade):
        """Obtém top ações por IV alta ou baixa"""
        if df is None or df.empty:
            return []
        
        try:
            if tipo.lower() == 'alta':
                top_df = df.nlargest(quantidade, 'iv_current')
            else:
                top_df = df.nsmallest(quantidade, 'iv_current')
            
            result = []
            for _, row in top_df.iterrows():
                result.append({
                    'symbol': row['symbol'],
                    'name': row.get('name', ''),
                    'iv_current': self._clean_numeric_value(row.get('iv_current')),
                    'close': self._clean_numeric_value(row.get('close')),
                    'variation': self._clean_numeric_value(row.get('variation'))
                })
            return result
        except Exception as e:
            print(f" Erro no top IV: {e}")
            return []
    
    def get_scatter_data(self, df, top_n):
        """Dados para scatter plot IV vs Volume"""
        if df is None or df.empty:
            return []
        
        try:
            scatter_data = []
            for _, row in df.head(top_n).iterrows():
                scatter_data.append({
                    'symbol': row['symbol'],
                    'iv_current': self._clean_numeric_value(row.get('iv_current')),
                    'financial_volume': max(1.0, self._clean_numeric_value(row.get('financial_volume'))),  # Mínimo 1 para log
                    'close': self._clean_numeric_value(row.get('close'))
                })
            return scatter_data
        except Exception as e:
            print(f" Erro no scatter data: {e}")
            return []
    
    def get_percentil_data(self, df, top_n):
        """Dados de percentil IV 6M"""
        if df is None or df.empty:
            return [], {}
        
        try:
            ranking = []
            for _, row in df.head(top_n).iterrows():
                percentil = self._clean_numeric_value(row.get('iv_6m_percentile'))
                ranking.append({
                    'symbol': row['symbol'],
                    'iv_6m_percentile': percentil,
                    'iv_current': self._clean_numeric_value(row.get('iv_current')),
                    'categoria': self._get_percentil_category(percentil)
                })
            
            # Resumo por categoria
            categorias = {}
            for item in ranking:
                cat = item['categoria']
                if cat not in categorias:
                    categorias[cat] = 0
                categorias[cat] += 1
            
            return ranking, categorias
        except Exception as e:
            print(f" Erro no percentil data: {e}")
            return [], {}
    
    def _get_percentil_category(self, percentil):
        """Categoriza percentil"""
        if percentil > 80:
            return 'Muito Alto'
        elif percentil > 60:
            return 'Alto'
        elif percentil > 40:
            return 'Médio'
        elif percentil > 20:
            return 'Baixo'
        else:
            return 'Muito Baixo'
    
    def get_comparison_data(self, df, top_n):
        """Dados de comparação IV atual vs 6M max"""
        if df is None or df.empty:
            return [], {}
        
        try:
            comparison_data = []
            ratios = []
            
            for _, row in df.head(top_n).iterrows():
                iv_current = self._clean_numeric_value(row.get('iv_current'))
                iv_6m_max = self._clean_numeric_value(row.get('iv_6m_max'))
                
                ratio = (iv_current / iv_6m_max * 100) if iv_6m_max > 0 else 0.0
                ratios.append(ratio)
                
                comparison_data.append({
                    'symbol': row['symbol'],
                    'iv_current': iv_current,
                    'iv_6m_max': iv_6m_max,
                    'ratio': ratio
                })
            
            # Estatísticas
            if ratios:
                stats = {
                    'ratio_medio': sum(ratios) / len(ratios),
                    'acima_media': len([r for r in ratios if r > 50]),
                    'abaixo_media': len([r for r in ratios if r <= 50])
                }
            else:
                stats = {
                    'ratio_medio': 0.0,
                    'acima_media': 0,
                    'abaixo_media': 0
                }
            
            return comparison_data, stats
        except Exception as e:
            print(f" Erro no comparison data: {e}")
            return [], {}
    
    def get_full_analysis(self, rank_by="iv_current", top_n=20):
        """Análise completa - método principal"""
        try:
            print(f" Iniciando análise completa: {rank_by}")
            
            # Buscar dados
            data = self.fetch_data(rank_by=rank_by, limit=150)
            if not data:
                return {
                    'success': False,
                    'error': 'Erro ao buscar dados do OpLab'
                }
            
            # Processar dados
            df = self.process_data(data)
            if df is None:
                return {
                    'success': False,
                    'error': 'Erro ao processar dados'
                }
            
            # Criar análise completa
            result = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'total_acoes': len(df),
                'rankings': {},
                'estatisticas': self.calculate_statistics(df),
                'top_5': {}
            }
            
            # Rankings principais
            result['rankings']['iv_atual'] = self.create_ranking(df, top_n)
            
            # Adicionar TODOS os dados para busca no frontend
            result['all_stocks'] = []
            for idx, (_, row) in enumerate(df.iterrows(), 1):
                result['all_stocks'].append({
                    'posicao': idx,
                    'symbol': row['symbol'],
                    'name': row.get('name', ''),
                    'iv_current': self._clean_numeric_value(row.get('iv_current')),
                    'close': self._clean_numeric_value(row.get('close')),
                    'volume': int(self._clean_numeric_value(row.get('volume'))),
                    'financial_volume': max(1.0, self._clean_numeric_value(row.get('financial_volume'))),  # Mínimo 1 para log
                    'variation': self._clean_numeric_value(row.get('variation')),
                    'iv_6m_percentile': self._clean_numeric_value(row.get('iv_6m_percentile')),
                    'iv_6m_max': self._clean_numeric_value(row.get('iv_6m_max'))
                })
            
            # Top 5 alta e baixa
            result['top_5']['iv_alta'] = self.get_top_iv(df, 'alta', 5)
            result['top_5']['iv_baixa'] = self.get_top_iv(df, 'baixa', 5)
            
            print(f" Análise completa criada: {len(df)} ações processadas")
            return result
            
        except Exception as e:
            print(f" Erro na análise completa: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# Função standalone
def get_ranking_data(rank_by="iv_current", top_n=20):
    """Função standalone para obter ranking"""
    service = RankingService()
    return service.get_full_analysis(rank_by=rank_by, top_n=top_n)

if __name__ == "__main__":
    # Teste
    resultado = get_ranking_data()
    
    if resultado['success']:
        print(f" Teste executado!")
        print(f" {resultado['total_acoes']} ações analisadas")
        
        if resultado['rankings']['iv_atual']:
            print(f"\n🏆 Top 5:")
            for item in resultado['rankings']['iv_atual'][:5]:
                print(f"   {item['posicao']}. {item['symbol']} - {item['iv_current']:.2f}%")
    else:
        print(f" Erro: {resultado['error']}")