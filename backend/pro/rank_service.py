import requests
import pandas as pd
import os
import json
from datetime import datetime

class RankingService:
    def __init__(self):
        self.token = self._get_token()
        self.base_url = "https://api.oplab.com.br/v3/market/stocks"
        self.headers = {
            "Access-Token": self.token,
            "Content-Type": "application/json"
        }
        
        # Lista de ações com opções (do código original)
        self.options_stocks = [
            'ABEV3', 'ALOS3', 'ASAI3', 'AURE3', 'AZUL4', 'AZZA3', 'B3SA3', 'BBAS3', 
            'BBDC3', 'BBDC4', 'BBSE3', 'BEEF3', 'BPAC11', 'BRAP4', 'BRAV3', 'BRFS3', 
            'BRKM5', 'CMIG4', 'CMIN3', 'COGN3', 'CPFE3', 'CPLE6', 'CSAN3', 'CSNA3', 
            'CVCB3', 'CXSE3', 'CYRE3', 'DIRR3', 'EGIE3', 'ELET3', 'ELET6', 'EMBR3', 
            'ENEV3', 'ENGI11', 'EQTL3', 'FLRY3', 'GGBR4', 'GOAU4', 'HAPV3', 'HYPE3', 
            'IGTI11', 'IRBR3', 'ISAE4', 'ITSA4', 'ITUB4', 'KLBN11', 'LREN3', 'MGLU3', 
            'MOTV3', 'MRFG3', 'MRVE3', 'MULT3', 'NATU3', 'PCAR3', 'PETR3', 'PETR4', 
            'PETZ3', 'POMO4', 'PRIO3', 'PSSA3', 'RADL3', 'RAIL3', 'RAIZ4', 'RDOR3', 
            'RECV3', 'RENT3', 'SANB11', 'SBSP3', 'SLCE3', 'SMFT3', 'SMTO3', 'STBP3', 
            'SUZB3', 'TAEE11', 'TIMS3', 'TOTS3', 'UGPA3', 'USIM5', 'VALE3', 'VAMO3', 
            'VBBR3', 'VIVA3', 'VIVT3', 'WEGE3', 'YDUQ3'
        ]
        
        print(f"📊 RankingService inicializado com {len(self.options_stocks)} ações")
    
    def _get_token(self):
        token = os.environ.get('OPLAB_TOKEN')
        if token:
            print("✅ Token OpLab da variável de ambiente")
            return token
        
        # 2. Arquivo config.json
        try:
            config_paths = ['config.json', 'backend/config.json', '../config.json']
            
            for path in config_paths:
                try:
                    with open(path, 'r') as f:
                        config = json.load(f)
                        token = config.get('token') or config.get('oplab_token')
                        if token:
                            print(f"✅ Token OpLab do arquivo {path}")
                            return token
                except:
                    continue
        except:
            pass
        
        # 3. Token padrão do código original
        default_token = "Z0ZcoMO3V1kByWw4UWmnodYkZWrHs1vLCF3ry0ApsyYabWNV5jsiAQP6YOREHmPf--mQVXl2FfHYxRFCsA1qDtzw==--Y2Y3YTRmNGRjNzI5NTUzMDc3N2YwOTY2NDRhZjJjMDI="
        print("⚠️ Usando token padrão")
        return default_token
    
    def fetch_data(self, rank_by="iv_current", sort="desc", limit=100):
        """Busca dados do OpLab"""
        try:
            params = {
                "rank_by": rank_by,
                "sort": sort,
                "limit": limit  # ← USAR O PARÂMETRO LIMIT
            }
            
            print(f"🔍 Buscando dados: {rank_by} (limit: {limit})")
            
            response = requests.get(self.base_url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                print(f"📦 Recebidos: {len(data)} registros")
                
                # Filtrar apenas ações com opções
                filtered = [item for item in data if item.get('symbol') in self.options_stocks]
                print(f"✅ Filtrados: {len(filtered)} ações com opções")
                
                return filtered
            else:
                print(f"❌ Erro API: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Erro na requisição: {e}")
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
                print(f"❌ Colunas faltando: {missing}")
                return None
            
            # Limpar dados
            initial_count = len(df)
            df = df.dropna(subset=['iv_current'])
            df = df.sort_values('iv_current', ascending=False)
            
            print(f"✅ Processados: {len(df)} de {initial_count} registros")
            return df
            
        except Exception as e:
            print(f"❌ Erro no processamento: {e}")
            return None
    
    def create_ranking(self, df, top_n=20):
        """Cria ranking principal"""
        if df is None or df.empty:
            return None
        
        ranking = []
        for idx, (_, row) in enumerate(df.head(top_n).iterrows(), 1):
            ranking.append({
                'posicao': idx,
                'symbol': row['symbol'],
                'name': row.get('name', ''),
                'iv_current': float(row.get('iv_current', 0)),
                'close': float(row.get('close', 0)),
                'volume': int(row.get('volume', 0)),
                'financial_volume': float(row.get('financial_volume', 0)),
                'variation': float(row.get('variation', 0)),
                'iv_6m_percentile': float(row.get('iv_6m_percentile', 0)),
                'iv_6m_max': float(row.get('iv_6m_max', 0))
            })
        
        return ranking
    
    def calculate_statistics(self, df):
        """Calcula estatísticas básicas"""
        if df is None or df.empty:
            return {}
        
    def calculate_statistics(self, df):
        """Calcula estatísticas básicas"""
        if df is None or df.empty:
            return {}
        
        stats = {
            'iv_media': float(df['iv_current'].mean()),
            'iv_mediana': float(df['iv_current'].median()),
            'iv_max': float(df['iv_current'].max()),
            'iv_min': float(df['iv_current'].min()),
            'iv_std': float(df['iv_current'].std()),
            'total_acoes': len(df)
        }
        
        return stats
    
    def get_top_iv(self, df, tipo='alta', quantidade=5):
        """Busca top ações por IV alta/baixa"""
        if df is None or df.empty:
            return []
        
        if tipo == 'baixa':
            df_sorted = df.sort_values('iv_current', ascending=True)
        else:
            df_sorted = df.sort_values('iv_current', ascending=False)
        
        top_list = []
        for _, row in df_sorted.head(quantidade).iterrows():
            top_list.append({
                'symbol': row['symbol'],
                'name': row.get('name', ''),
                'iv_current': float(row.get('iv_current', 0)),
                'close': float(row.get('close', 0))
            })
        
        return top_list
    
    def get_scatter_data(self, df, top_n=30):
        """Prepara dados para scatter plot IV vs Volume"""
        if df is None or df.empty:
            return []
        
        scatter_data = []
        for _, row in df.head(top_n).iterrows():
            scatter_data.append({
                'symbol': row['symbol'],
                'name': row.get('name', ''),
                'iv_current': float(row.get('iv_current', 0)),
                'financial_volume': float(row.get('financial_volume', 0)),
                'close': float(row.get('close', 0)),
                'variation': float(row.get('variation', 0))
            })
        
        return scatter_data
    
    def get_comparison_data(self, df, top_n=20):
        """Prepara dados para comparação IV atual vs 6M max"""
        if df is None or df.empty:
            return [], {}
        
        comparison_data = []
        ratios = []
        
        for _, row in df.head(top_n).iterrows():
            iv_atual = float(row.get('iv_current', 0))
            iv_6m_max = float(row.get('iv_6m_max', 1))
            ratio = (iv_atual / iv_6m_max) if iv_6m_max > 0 else 0
            ratios.append(ratio)
            
            status = 'Perto do máximo' if ratio > 0.9 else \
                     'Alto' if ratio > 0.7 else \
                     'Médio' if ratio > 0.5 else 'Baixo'
            
            comparison_data.append({
                'symbol': row['symbol'],
                'name': row.get('name', ''),
                'iv_current': iv_atual,
                'iv_6m_max': iv_6m_max,
                'ratio': ratio,
                'ratio_percent': ratio * 100,
                'status': status,
                'close': float(row.get('close', 0)),
                'financial_volume': float(row.get('financial_volume', 0))
            })
        
        # Estatísticas dos ratios
        stats = {
            'ratio_medio': sum(ratios) / len(ratios) if ratios else 0,
            'acoes_perto_maximo': len([r for r in ratios if r > 0.9]),
            'acoes_alto': len([r for r in ratios if 0.7 < r <= 0.9]),
            'acoes_baixo': len([r for r in ratios if r <= 0.5])
        }
        
        return comparison_data, stats
    
    def get_full_analysis(self, rank_by="iv_current", top_n=20):
        """Análise completa - método principal"""
        try:
            print(f"🎯 Iniciando análise completa: {rank_by}")
            
            # AQUI: Buscar MAIS dados para permitir busca expandida
            # Antes: data = self.fetch_data(rank_by=rank_by)
            # Agora: Buscar 150 ações em vez de 100 (padrão)
            data = self.fetch_data(rank_by=rank_by, limit=150)  # ← MUDANÇA AQUI
            
            if not data:
                return {
                    'success': False,
                    'error': 'Erro ao buscar dados do OpLab'
                }
            
            # Processar TODOS os dados (150 ações)
            df = self.process_data(data)
            if df is None:
                return {
                    'success': False,
                    'error': 'Erro ao processar dados'
                }
            
            # Retornar análise com TODOS os dados para busca
            result = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'total_acoes': len(df),
                'rankings': {},
                'estatisticas': self.calculate_statistics(df),
                'top_5': {}
            }
            
            # Rankings principais - usar top_n para o ranking, mas manter todos os dados
            result['rankings']['iv_atual'] = self.create_ranking(df, top_n)
            
            # NOVA: Adicionar TODOS os dados para busca no frontend
            result['all_stocks'] = []
            for idx, (_, row) in enumerate(df.iterrows(), 1):
                result['all_stocks'].append({
                    'posicao': idx,
                    'symbol': row['symbol'],
                    'name': row.get('name', ''),
                    'iv_current': float(row.get('iv_current', 0)),
                    'close': float(row.get('close', 0)),
                    'volume': int(row.get('volume', 0)),
                    'financial_volume': float(row.get('financial_volume', 0)),
                    'variation': float(row.get('variation', 0)),
                    'iv_6m_percentile': float(row.get('iv_6m_percentile', 0)),
                    'iv_6m_max': float(row.get('iv_6m_max', 0))
                })
            
            # Top 5 alta e baixa
            result['top_5']['iv_alta'] = self.get_top_iv(df, 'alta', 5)
            result['top_5']['iv_baixa'] = self.get_top_iv(df, 'baixa', 5)
            
            print(f"✅ Análise completa criada: {len(df)} ações processadas")
            return result
            
        except Exception as e:
            print(f"❌ Erro na análise completa: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_full_analysis(self, rank_by="iv_current", top_n=20):
        """Análise completa - método principal"""
        try:
            print(f"🎯 Iniciando análise completa: {rank_by}")
            
            # Buscar dados
            data = self.fetch_data(rank_by=rank_by)
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
            
            # Top 5 alta e baixa
            result['top_5']['iv_alta'] = self.get_top_iv(df, 'alta', 5)
            result['top_5']['iv_baixa'] = self.get_top_iv(df, 'baixa', 5)
            
            print(f"✅ Análise completa criada: {len(df)} ações processadas")
            return result
            
        except Exception as e:
            print(f"❌ Erro na análise completa: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# Função standalone para uso direto
def get_ranking_data(rank_by="iv_current", top_n=20):
    """Função standalone para obter ranking"""
    service = RankingService()
    return service.get_full_analysis(rank_by=rank_by, top_n=top_n)

if __name__ == "__main__":
    # Teste
    resultado = get_ranking_data()
    
    if resultado['success']:
        print(f"✅ Teste executado com sucesso!")
        print(f"📊 {resultado['total_acoes']} ações analisadas")
        
        if 'rankings' in resultado and 'iv_atual' in resultado['rankings']:
            print(f"\n🏆 Top 5 IV Atual:")
            for item in resultado['rankings']['iv_atual'][:5]:
                print(f"   {item['posicao']}. {item['symbol']} - {item['iv_current']:.2f}%")
    else:
        print(f"❌ Erro no teste: {resultado['error']}")