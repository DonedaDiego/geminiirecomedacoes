from flask import Blueprint, request, jsonify
from datetime import datetime
import traceback
import requests
import pandas as pd
import os

# Blueprint
rank_bp = Blueprint('rank', __name__, url_prefix='/api/rank')

# Configuração do token - múltiplas fontes
def get_oplab_token():
    """Busca token do OpLab de múltiplas fontes"""
    
    # 1. Variável de ambiente (Railway/produção)
    token = os.environ.get('OPLAB_TOKEN')
    if token:
        print("✅ Token OpLab encontrado em variável de ambiente")
        return token
    
    # 2. Arquivo config.json local
    try:
        import json
        config_paths = [
            'config.json',
            'backend/config.json',
            '../config.json'
        ]
        
        for path in config_paths:
            try:
                with open(path, 'r') as f:
                    config = json.load(f)
                    token = config.get('token') or config.get('oplab_token')
                    if token:
                        print(f"✅ Token OpLab encontrado em {path}")
                        return token
            except:
                continue
    except:
        pass
    
    # 3. Token fixo do código original
    default_token = "Z0ZcoMO3V1kByWw4UWmnodYkZWrHs1vLCF3ry0ApsyYabWNV5jsiAQP6YOREHmPf--mQVXl2FfHYxRFCsA1qDtzw==--Y2Y3YTRmNGRjNzI5NTUzMDc3N2YwOTY2NDRhZjJjMDI="
    print("⚠️ Usando token padrão")
    return default_token

# Token global
OPLAB_TOKEN = get_oplab_token()

# Lista de ações com opções (do código original)
OPTIONS_STOCKS = [
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

def fetch_oplab_data(rank_by="iv_current", sort="desc", limit=100):
    """Busca dados do OpLab API"""
    try:
        url = "https://api.oplab.com.br/v3/market/stocks"
        headers = {
            "Access-Token": OPLAB_TOKEN,
            "Content-Type": "application/json"
        }
        params = {
            "rank_by": rank_by,
            "sort": sort,
            "limit": limit
        }
        
        print(f"🔍 Buscando dados OpLab: {rank_by}")
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print(f"📦 Dados recebidos: {len(data)} ações")
            
            # Filtrar apenas ações com opções
            filtered_data = [stock for stock in data if stock.get('symbol') in OPTIONS_STOCKS]
            print(f"✅ Ações filtradas: {len(filtered_data)} com opções")
            
            return filtered_data
        else:
            print(f"❌ Erro OpLab: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Erro na requisição OpLab: {e}")
        return None

def process_data(data):
    """Processa dados em DataFrame"""
    if not data:
        return None
    
    try:
        df = pd.DataFrame(data)
        
        # Colunas principais
        required_cols = ['symbol', 'iv_current', 'close', 'financial_volume']
        for col in required_cols:
            if col not in df.columns:
                print(f"⚠️ Coluna {col} não encontrada")
                return None
        
        # Limpar dados
        df = df.dropna(subset=['iv_current'])
        df = df.sort_values('iv_current', ascending=False)
        
        print(f"✅ Dados processados: {len(df)} ações")
        return df
        
    except Exception as e:
        print(f"❌ Erro no processamento: {e}")
        return None

@rank_bp.route('/health', methods=['GET'])
def health_check():
    """Health check"""
    return jsonify({
        'status': 'OK',
        'message': 'Ranking de Volatilidade Implícita funcionando',
        'timestamp': datetime.now().isoformat(),
        'acoes_monitoradas': len(OPTIONS_STOCKS),
        'token_configurado': bool(OPLAB_TOKEN)
    })

@rank_bp.route('/iv-ranking', methods=['GET'])
def get_iv_ranking():
    """Ranking principal de IV"""
    try:
        # Parâmetros
        rank_by = request.args.get('rank_by', 'iv_current')
        top_n = int(request.args.get('top_n', 20))
        
        print(f"📊 Ranking solicitado: {rank_by}, top {top_n}")
        
        # Buscar dados
        data = fetch_oplab_data(rank_by=rank_by)
        if not data:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados do OpLab'
            }), 500
        
        # Processar
        df = process_data(data)
        if df is None:
            return jsonify({
                'success': False,
                'error': 'Erro ao processar dados'
            }), 500
        
        # Criar ranking
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
        
        # Estatísticas
        stats = {
            'iv_media': float(df['iv_current'].mean()),
            'iv_max': float(df['iv_current'].max()),
            'iv_min': float(df['iv_current'].min()),
            'total_acoes': len(df)
        }
        
        return jsonify({
            'success': True,
            'total_acoes': len(df),
            'rankings': {
                'iv_atual': ranking
            },
            'estatisticas': stats,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro no ranking: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@rank_bp.route('/top-iv', methods=['GET'])
def get_top_iv():
    """Top ações por IV alta/baixa"""
    try:
        tipo = request.args.get('tipo', 'alta').lower()
        quantidade = int(request.args.get('quantidade', 5))
        
        print(f"🎯 Top IV {tipo}: {quantidade} ações")
        
        # Buscar dados
        data = fetch_oplab_data()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados'
            }), 500
        
        # Processar
        df = process_data(data)
        if df is None:
            return jsonify({
                'success': False,
                'error': 'Erro ao processar dados'
            }), 500
        
        # Ordenar conforme tipo
        if tipo == 'baixa':
            df_sorted = df.sort_values('iv_current', ascending=True)
        else:
            df_sorted = df.sort_values('iv_current', ascending=False)
        
        # Top N
        top_acoes = []
        for _, row in df_sorted.head(quantidade).iterrows():
            top_acoes.append({
                'symbol': row['symbol'],
                'name': row.get('name', ''),
                'iv_current': float(row.get('iv_current', 0)),
                'close': float(row.get('close', 0))
            })
        
        return jsonify({
            'success': True,
            'tipo': tipo,
            'quantidade': len(top_acoes),
            'top_acoes': top_acoes,
            'descricao': f'Top {quantidade} ações com IV {"mais alta" if tipo == "alta" else "mais baixa"}',
            'ideal_para': 'vendedores de opções' if tipo == 'alta' else 'compradores de opções',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro no top IV: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@rank_bp.route('/iv-vs-volume', methods=['GET'])
def get_iv_vs_volume():
    """IV vs Volume para scatter plot"""
    try:
        top_n = int(request.args.get('top_n', 20))
        
        print(f"📊 IV vs Volume: top {top_n}")
        
        # Buscar dados
        data = fetch_oplab_data()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados'
            }), 500
        
        # Processar
        df = process_data(data)
        if df is None:
            return jsonify({
                'success': False,
                'error': 'Erro ao processar dados'
            }), 500
        
        # Preparar dados do scatter
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
        
        return jsonify({
            'success': True,
            'total_acoes': len(scatter_data),
            'scatter_data': scatter_data,
            'descricao': 'IV vs Volume Financeiro',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro no IV vs Volume: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@rank_bp.route('/iv-percentil', methods=['GET'])
def get_iv_percentil():
    """Ranking por percentil de IV"""
    try:
        top_n = int(request.args.get('top_n', 20))
        
        print(f"📊 IV Percentil: top {top_n}")
        
        # Buscar dados
        data = fetch_oplab_data(rank_by='iv_6m_percentile')
        if not data:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados'
            }), 500
        
        # Processar
        df = process_data(data)
        if df is None:
            return jsonify({
                'success': False,
                'error': 'Erro ao processar dados'
            }), 500
        
        # Ranking
        ranking = []
        for idx, (_, row) in enumerate(df.head(top_n).iterrows(), 1):
            ranking.append({
                'posicao': idx,
                'symbol': row['symbol'],
                'name': row.get('name', ''),
                'iv_current': float(row.get('iv_current', 0)),
                'iv_6m_percentile': float(row.get('iv_6m_percentile', 0)),
                'close': float(row.get('close', 0)),
                'volume': int(row.get('volume', 0))
            })
        
        # Categorizar
        categorias = {'criticos': 0, 'altos': 0, 'medios': 0, 'baixos': 0}
        for item in ranking:
            percentil = item['iv_6m_percentile']
            if percentil > 80:
                categorias['criticos'] += 1
            elif percentil > 60:
                categorias['altos'] += 1
            elif percentil > 40:
                categorias['medios'] += 1
            else:
                categorias['baixos'] += 1
        
        return jsonify({
            'success': True,
            'total_acoes': len(ranking),
            'ranking': ranking,
            'resumo_categorias': categorias,
            'descricao': 'Ranking por Percentil IV 6M',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro no percentil: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@rank_bp.route('/iv-6m-comparison', methods=['GET'])
def get_iv_6m_comparison():
    """Comparação IV atual vs IV 6M máximo"""
    try:
        top_n = int(request.args.get('top_n', 20))
        
        print(f"📊 IV 6M Comparison: top {top_n}")
        
        # Buscar dados
        data = fetch_oplab_data()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados'
            }), 500
        
        # Processar
        df = process_data(data)
        if df is None:
            return jsonify({
                'success': False,
                'error': 'Erro ao processar dados'
            }), 500
        
        # Calcular ratio e filtrar
        comparison_data = []
        for _, row in df.head(top_n).iterrows():
            iv_atual = float(row.get('iv_current', 0))
            iv_6m_max = float(row.get('iv_6m_max', 1))
            ratio = (iv_atual / iv_6m_max) if iv_6m_max > 0 else 0
            
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
        
        # Estatísticas
        ratios = [item['ratio'] for item in comparison_data]
        stats = {
            'ratio_medio': sum(ratios) / len(ratios) if ratios else 0,
            'acoes_perto_maximo': len([r for r in ratios if r > 0.9]),
            'acoes_alto': len([r for r in ratios if 0.7 < r <= 0.9]),
            'acoes_baixo': len([r for r in ratios if r <= 0.5])
        }
        
        return jsonify({
            'success': True,
            'total_acoes': len(comparison_data),
            'comparison_data': comparison_data,
            'estatisticas': stats,
            'descricao': 'IV Atual vs IV 6M Máximo',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro na comparação 6M: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@rank_bp.route('/estatisticas', methods=['GET'])
def get_estatisticas():
    """Estatísticas gerais"""
    try:
        print("📊 Estatísticas gerais solicitadas")
        
        # Buscar dados
        data = fetch_oplab_data()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados'
            }), 500
        
        # Processar
        df = process_data(data)
        if df is None:
            return jsonify({
                'success': False,
                'error': 'Erro ao processar dados'
            }), 500
        
        # Estatísticas
        stats = {
            'iv_media': float(df['iv_current'].mean()),
            'iv_mediana': float(df['iv_current'].median()),
            'iv_max': float(df['iv_current'].max()),
            'iv_min': float(df['iv_current'].min()),
            'iv_std': float(df['iv_current'].std())
        }
        
        # Top 5 alta e baixa
        top_5_alta = []
        for _, row in df.head(5).iterrows():
            top_5_alta.append({
                'symbol': row['symbol'],
                'name': row.get('name', ''),
                'iv_current': float(row.get('iv_current', 0))
            })
        
        top_5_baixa = []
        for _, row in df.sort_values('iv_current').head(5).iterrows():
            top_5_baixa.append({
                'symbol': row['symbol'],
                'name': row.get('name', ''),
                'iv_current': float(row.get('iv_current', 0))
            })
        
        return jsonify({
            'success': True,
            'total_acoes_monitoradas': len(OPTIONS_STOCKS),
            'total_acoes_processadas': len(df),
            'estatisticas_iv': stats,
            'destaques': {
                'iv_alta': top_5_alta,
                'iv_baixa': top_5_baixa
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro nas estatísticas: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Error handlers
@rank_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint não encontrado',
        'timestamp': datetime.now().isoformat()
    }), 404

@rank_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Erro interno do servidor',
        'timestamp': datetime.now().isoformat()
    }), 500

# Função para retornar blueprint
def get_rank_blueprint():
    """Retorna blueprint para registrar no Flask"""
    return rank_bp