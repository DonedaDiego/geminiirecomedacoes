# recommendation_service.py - SERVIÇOS DE RECOMENDAÇÕES

from database import get_db_connection
from datetime import datetime
import jwt
import os

# ===== DADOS DAS EMPRESAS =====

COMPANY_INFO = {
    "VALE3": {
        "name": "Vale",
        "description": "Fundada em 1942, a Vale é uma das maiores mineradoras do mundo, com forte atuação em minério de ferro, níquel e logística. Sua presença global e importância para a balança comercial brasileira a tornam estratégica, embora esteja sujeita à volatilidade das commodities e a riscos ambientais.",
        "sector": "Mineração",
        "founded": 1942
    },
    "ITUB4": {
        "name": "Itaú Unibanco",
        "description": "Resultado da fusão entre Itaú e Unibanco em 2008, tornou-se o maior banco privado do Brasil. É reconhecido por sua sólida governança, foco em eficiência operacional e forte atuação em varejo bancário, crédito e gestão de ativos.",
        "sector": "Financeiro",
        "founded": 2008
    },
    "PETR4": {
        "name": "Petrobras",
        "description": "Criada em 1953, a Petrobras é a maior empresa de energia do Brasil. Atua nos segmentos de exploração, produção, refino e distribuição de petróleo e gás. Apesar do histórico de interferência política, é referência mundial em exploração em águas profundas.",
        "sector": "Energia",
        "founded": 1953
    },
    "BBDC4": {
        "name": "Bradesco",
        "description": "Fundado em 1943, o Bradesco é um dos maiores bancos privados do Brasil. Reconhecido por sua ampla rede de agências e forte presença no varejo, oferece serviços bancários completos e tem estratégia focada em transformação digital.",
        "sector": "Financeiro", 
        "founded": 1943
    },
    "ABEV3": {
        "name": "Ambev",
        "description": "A Ambev é uma das maiores cervejarias do mundo, controlada pela Anheuser-Busch InBev. No Brasil, domina o mercado de bebidas com marcas como Skol, Brahma e Antarctica, além de atuar em refrigerantes e água.",
        "sector": "Bebidas",
        "founded": 1999
    },
    "WEGE3": {
        "name": "WEG",
        "description": "Fundada em 1961, a WEG é líder brasileira em motores elétricos e automação industrial. Reconhecida pela qualidade e inovação, exporta para mais de 135 países e é referência em eficiência energética.",
        "sector": "Industrial",
        "founded": 1961
    },
    "MGLU3": {
        "name": "Magazine Luiza",
        "description": "Varejista brasileira fundada em 1957, revolucionou o setor com sua estratégia omnichannel. Conhecida pela inovação em e-commerce e marketplace, é uma das principais empresas de varejo do país.",
        "sector": "Varejo",
        "founded": 1957
    },
    # BDRs Americanas
    "AAPL34": {
        "name": "Apple Inc.",
        "description": "Fundada em 1976, a Apple é uma das maiores empresas de tecnologia do mundo. Líder em smartphones (iPhone), computadores (Mac) e serviços digitais, é reconhecida pela inovação e design premium.",
        "sector": "Tecnologia",
        "founded": 1976
    },
    "MSFT34": {
        "name": "Microsoft",
        "description": "Criada em 1975, a Microsoft é líder em software empresarial, computação em nuvem (Azure) e produtividade. Domina o mercado de sistemas operacionais e tem forte crescimento em cloud computing.",
        "sector": "Tecnologia",
        "founded": 1975
    },
    "GOOGL34": {
        "name": "Alphabet (Google)",
        "description": "A Alphabet, holding do Google fundada em 2015, domina o mercado de buscas online e publicidade digital. Também atua em computação em nuvem, inteligência artificial e veículos autônomos.",
        "sector": "Tecnologia",
        "founded": 2015
    },
    "AMZO34": {
        "name": "Amazon",
        "description": "Fundada em 1994, a Amazon revolucionou o e-commerce e é líder em computação em nuvem (AWS). Atua também em logística, streaming de vídeo e inteligência artificial.",
        "sector": "E-commerce",
        "founded": 1994
    },
    "TSLA34": {
        "name": "Tesla",
        "description": "Fundada em 2003, a Tesla é pioneira em veículos elétricos e armazenamento de energia. Liderada por Elon Musk, é referência em inovação automotiva e sustentabilidade.",
        "sector": "Automotivo",
        "founded": 2003
    },
    "NVDC34": {
        "name": "NVIDIA",
        "description": "Fundada em 1993, a NVIDIA é líder mundial em processadores gráficos (GPUs) e computação acelerada. Tornou-se essencial para inteligência artificial, games e data centers.",
        "sector": "Semicondutores",
        "founded": 1993
    }
}

# ===== FUNÇÕES AUXILIARES =====

def verify_token(token):
    """Função auxiliar para verificar token"""
    try:
        secret_key = os.environ.get('SECRET_KEY', 'geminii-secret-2024')
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload
    except:
        return None

def get_company_info(ticker):
    """Buscar informações da empresa pelo ticker"""
    return COMPANY_INFO.get(ticker, {
        "name": ticker,
        "description": "Informações não disponíveis para este ativo.",
        "sector": "N/A",
        "founded": None
    })

# ===== SERVIÇOS DE RECOMENDAÇÕES =====

def get_admin_portfolio_recommendations_service(portfolio_name):
    """Buscar recomendações de uma carteira (Admin) - COM INFO DAS EMPRESAS"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                id, ticker, action_type, target_weight, 
                recommendation_date, reason, price_target, 
                current_price, is_active
            FROM portfolio_recommendations 
            WHERE portfolio_name = %s AND is_active = true
            ORDER BY recommendation_date DESC
        ''', (portfolio_name,))
        
        recommendations = []
        for row in cursor.fetchall():
            ticker = row[1]
            company_info = get_company_info(ticker)
            
            recommendations.append({
                'id': row[0],
                'ticker': ticker,
                'action_type': row[2],
                'target_weight': float(row[3]) if row[3] else None,
                'recommendation_date': row[4].isoformat() if row[4] else None,
                'reason': row[5],
                'price_target': float(row[6]) if row[6] else None,
                'current_price': float(row[7]) if row[7] else None,
                'is_active': row[8],
                # ✅ NOVAS INFORMAÇÕES DA EMPRESA
                'company_name': company_info['name'],
                'company_description': company_info['description'],
                'company_sector': company_info['sector'],
                'company_founded': company_info['founded']
            })
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'recommendations': recommendations,
            'portfolio': portfolio_name
        }
        
    except Exception as e:
        print(f"Error getting recommendations: {e}")
        return {'success': False, 'error': str(e)}

def add_portfolio_recommendation_service(data, admin_id):
    """Adicionar nova recomendação"""
    try:
        # Validar dados obrigatórios
        required_fields = ['portfolio', 'ticker', 'action_type', 'recommendation_date']
        for field in required_fields:
            if field not in data:
                return {'success': False, 'error': f'Campo {field} é obrigatório'}
        
        # Validar action_type
        if data['action_type'] not in ['BUY', 'SELL', 'HOLD']:
            return {'success': False, 'error': 'Ação deve ser BUY, SELL ou HOLD'}
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        # Inserir recomendação
        cursor.execute('''
            INSERT INTO portfolio_recommendations 
            (portfolio_name, ticker, action_type, target_weight, 
             recommendation_date, reason, price_target, current_price, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            data['portfolio'],
            data['ticker'].upper(),
            data['action_type'],
            data.get('target_weight'),
            data['recommendation_date'],
            data.get('reason', ''),
            data.get('price_target'),
            data.get('current_price'),
            admin_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': f'Recomendação para {data["ticker"]} adicionada com sucesso!'
        }
        
    except Exception as e:
        print(f"Error adding recommendation: {e}")
        return {'success': False, 'error': str(e)}

def update_portfolio_recommendation_service(data):
    """Atualizar recomendação existente"""
    try:
        if 'id' not in data:
            return {'success': False, 'error': 'ID da recomendação é obrigatório'}
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        # Construir query dinâmica baseada nos campos fornecidos
        update_fields = []
        update_values = []
        
        updatable_fields = ['action_type', 'target_weight', 'reason', 'price_target', 'current_price', 'is_active']
        for field in updatable_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                update_values.append(data[field])
        
        if not update_fields:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Nenhum campo para atualizar'}
        
        # Adicionar timestamp de atualização
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        update_values.append(data['id'])
        
        query = f'''
            UPDATE portfolio_recommendations 
            SET {', '.join(update_fields)}
            WHERE id = %s
        '''
        
        cursor.execute(query, update_values)
        conn.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Recomendação não encontrada'}
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': 'Recomendação atualizada com sucesso!'
        }
        
    except Exception as e:
        print(f"Error updating recommendation: {e}")
        return {'success': False, 'error': str(e)}

def delete_portfolio_recommendation_service(recommendation_id):
    """Deletar recomendação"""
    try:
        if not recommendation_id:
            return {'success': False, 'error': 'ID da recomendação é obrigatório'}
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE portfolio_recommendations 
            SET is_active = false, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (recommendation_id,))
        
        conn.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Recomendação não encontrada'}
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': 'Recomendação removida com sucesso!'
        }
        
    except Exception as e:
        print(f"Error deleting recommendation: {e}")
        return {'success': False, 'error': str(e)}

def get_user_portfolio_recommendations_service(portfolio_name):
    """Endpoint público para usuários verem recomendações"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                ticker, action_type, target_weight, 
                recommendation_date, reason, price_target
            FROM portfolio_recommendations 
            WHERE portfolio_name = %s AND is_active = true
            ORDER BY recommendation_date DESC
            LIMIT 10
        ''', (portfolio_name,))
        
        recommendations = []
        for row in cursor.fetchall():
            recommendations.append({
                'ticker': row[0],
                'action_type': row[1],
                'target_weight': float(row[2]) if row[2] else None,
                'recommendation_date': row[3].isoformat() if row[3] else None,
                'reason': row[4],
                'price_target': float(row[5]) if row[5] else None
            })
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'recommendations': recommendations,
            'portfolio': portfolio_name
        }
        
    except Exception as e:
        print(f"Error getting user recommendations: {e}")
        return {'success': False, 'error': str(e)}

def generate_rebalance_recommendations_service(portfolio, reason, admin_user_id):
    """Gerar recomendações de VENDA automáticas para rebalanceamento"""
    try:
        if not portfolio:
            return {'success': False, 'error': 'Nome da carteira é obrigatório'}
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Buscar todos os ativos atuais da carteira
        cursor.execute("""
            SELECT ticker, current_price, target_price, weight
            FROM portfolio_assets 
            WHERE portfolio_name = %s
        """, (portfolio,))
        
        assets = cursor.fetchall()
        
        if not assets:
            cursor.close()
            conn.close()
            return {'success': False, 'error': f'Nenhum ativo encontrado na carteira {portfolio}'}
        
        recommendations_created = 0
        today = datetime.now().date()
        
        # Criar recomendação de VENDA para cada ativo existente
        for asset in assets:
            ticker, current_price, target_price, weight = asset
            
            # Usar preço atual como preço de entrada/mercado
            entry_price = current_price if current_price and current_price > 0 else target_price
            market_price = current_price if current_price and current_price > 0 else target_price
            
            # Verificar se já existe recomendação de SELL recente para este ticker
            cursor.execute("""
                SELECT id FROM portfolio_recommendations 
                WHERE portfolio_name = %s AND ticker = %s AND action_type = 'SELL'
                AND recommendation_date >= %s
            """, (portfolio, ticker, today))
            
            existing_rec = cursor.fetchone()
            
            if not existing_rec:
                # Inserir nova recomendação de VENDA
                cursor.execute("""
                    INSERT INTO portfolio_recommendations 
                    (portfolio_name, ticker, action_type, target_weight, 
                     recommendation_date, price_target, reason, created_by)
                    VALUES (%s, %s, 'SELL', 0, %s, %s, %s, %s)
                """, (portfolio, ticker, today, target_price, reason, admin_user_id))
                
                recommendations_created += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': f'Rebalanceamento criado com sucesso!',
            'recommendations_created': recommendations_created,
            'portfolio': portfolio
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_portfolios_service(user_id):
    """Buscar carteiras que o usuário tem acesso (ADMIN TEM ACESSO TOTAL)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ✅ VERIFICAR SE É ADMIN PRIMEIRO
        cursor.execute("SELECT user_type FROM users WHERE id = %s", (user_id,))
        user_result = cursor.fetchone()
        
        if user_result and user_result[0] in ['admin', 'master']:
            # 🔥 ADMIN TEM ACESSO TOTAL - TODAS AS CARTEIRAS
            cursor.execute("""
                SELECT name, display_name, description, created_at
                FROM portfolios 
                WHERE is_active = true
                ORDER BY display_name
            """)
            
            portfolios = []
            for row in cursor.fetchall():
                portfolios.append({
                    'name': row[0],
                    'display_name': row[1],
                    'description': row[2],
                    'granted_at': row[3].isoformat() if row[3] else None
                })
                
        else:
            # 👤 USUÁRIO NORMAL - APENAS CARTEIRAS LIBERADAS
            cursor.execute("""
                SELECT up.portfolio_name, p.display_name, p.description, up.granted_at
                FROM user_portfolios up
                JOIN portfolios p ON up.portfolio_name = p.name
                WHERE up.user_id = %s AND up.is_active = true
                ORDER BY p.display_name
            """, (user_id,))
            
            portfolios = []
            for row in cursor.fetchall():
                portfolios.append({
                    'name': row[0],
                    'display_name': row[1],
                    'description': row[2],
                    'granted_at': row[3].isoformat() if row[3] else None
                })
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'portfolios': portfolios
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_portfolio_recommendations_detailed_service(portfolio_name, user_id):
    """Buscar recomendações detalhadas de uma carteira para o usuário"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ✅ VERIFICAR SE É ADMIN
        cursor.execute("SELECT user_type FROM users WHERE id = %s", (user_id,))
        user_result = cursor.fetchone()
        is_admin = user_result and user_result[0] in ['admin', 'master']
        
        if not is_admin:
            # VERIFICAR ACESSO PARA USUÁRIOS NORMAIS
            cursor.execute("""
                SELECT id FROM user_portfolios 
                WHERE user_id = %s AND portfolio_name = %s AND is_active = true
            """, (user_id, portfolio_name))
            
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return {'success': False, 'error': 'Acesso negado a esta carteira'}
        
        # ADMIN OU USUÁRIO COM ACESSO - BUSCAR RECOMENDAÇÕES
        cursor.execute("""
            SELECT 
                ticker, action_type, target_weight, 
                recommendation_date, reason, price_target, current_price
            FROM portfolio_recommendations 
            WHERE portfolio_name = %s AND is_active = true
            ORDER BY recommendation_date DESC
            LIMIT 20
        """, (portfolio_name,))
        
        recommendations = []
        for row in cursor.fetchall():
            ticker = row[0]
            company_info = get_company_info(ticker)
            
            recommendations.append({
                'ticker': ticker,
                'action_type': row[1],
                'target_weight': float(row[2]) if row[2] else None,
                'recommendation_date': row[3].isoformat() if row[3] else None,
                'reason': row[4],
                'price_target': float(row[5]) if row[5] else None,
                'current_price': float(row[6]) if row[6] else None,
                'company_name': company_info['name'],
                'company_description': company_info['description'],
                'company_sector': company_info['sector']
            })
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'portfolio_name': portfolio_name,
            'recommendations': recommendations
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_portfolio_assets_service(portfolio_name, user_id):
    """Buscar ativos de uma carteira para o usuário"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ✅ VERIFICAR SE É ADMIN
        cursor.execute("SELECT user_type FROM users WHERE id = %s", (user_id,))
        user_result = cursor.fetchone()
        is_admin = user_result and user_result[0] in ['admin', 'master']
        
        if not is_admin:
            # VERIFICAR ACESSO PARA USUÁRIOS NORMAIS
            cursor.execute("""
                SELECT id FROM user_portfolios 
                WHERE user_id = %s AND portfolio_name = %s AND is_active = true
            """, (user_id, portfolio_name))
            
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return {'success': False, 'error': 'Acesso negado a esta carteira'}
        
        # ADMIN OU USUÁRIO COM ACESSO - BUSCAR ATIVOS
        cursor.execute("""
            SELECT ticker, weight, sector, entry_price, current_price, target_price, entry_date
            FROM portfolio_assets 
            WHERE portfolio_name = %s AND is_active = true
            ORDER BY weight DESC
        """, (portfolio_name,))
        
        assets = []
        total_weight = 0
        
        for row in cursor.fetchall():
            ticker = row[0]
            weight = float(row[1])
            company_info = get_company_info(ticker)
            
            assets.append({
                'ticker': ticker,
                'weight': weight,
                'sector': row[2],
                'entry_price': float(row[3]) if row[3] else 0,
                'current_price': float(row[4]) if row[4] else 0,
                'target_price': float(row[5]) if row[5] else 0,
                'entry_date': row[6].isoformat() if row[6] else None,
                'company_name': company_info['name'],
                'company_description': company_info['description']
            })
            
            total_weight += weight
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'portfolio_name': portfolio_name,
            'assets': assets,
            'total_weight': total_weight
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_admin_stats_service():
    """Buscar estatísticas do admin dashboard"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        # Total de usuários
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_type != 'admin'")
        total_users = cursor.fetchone()[0]
        
        # Usuários premium (não básico)
        cursor.execute("SELECT COUNT(*) FROM users WHERE plan_id > 1 AND user_type != 'admin'")
        premium_users = cursor.fetchone()[0]
        
        # Cupons ativos
        cursor.execute("SELECT COUNT(*) FROM coupons WHERE is_active = true")
        active_coupons = cursor.fetchone()[0]
        
        # Total de recomendações ativas
        cursor.execute("SELECT COUNT(*) FROM portfolio_recommendations WHERE is_active = true")
        total_recommendations = cursor.fetchone()[0]
        
        # Receita mensal estimada (simulada)
        monthly_revenue = premium_users * 50  # Estimativa básica
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'data': {
                'total_users': total_users,
                'premium_users': premium_users,
                'active_coupons': active_coupons,
                'total_recommendations': total_recommendations,
                'monthly_revenue': monthly_revenue
            }
        }
        
    except Exception as e:
        print(f"Error getting admin stats: {e}")
        return {'success': False, 'error': str(e)}