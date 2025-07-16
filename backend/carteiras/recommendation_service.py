# recommendation_service.py - SERVIÇOS DE RECOMENDAÇÕES - VERSÃO CORRIGIDA

from database import get_db_connection
from datetime import datetime
import jwt
import os

# ===== DADOS DAS EMPRESAS =====

COMPANY_INFO = {
    "VALE3": {
        "name": "Vale",
        "description": "Fundada em 1942, a Vale é uma das maiores mineradoras do mundo, com forte atuação em minério de ferro, níquel e logística.",
        "sector": "Mineração",
        "founded": 1942
    },
    "ITUB4": {
        "name": "Itaú Unibanco",
        "description": "Maior banco privado do Brasil, reconhecido por sua governança e eficiência operacional.",
        "sector": "Financeiro",
        "founded": 2008
    },
    "PETR4": {
        "name": "Petrobras",
        "description": "Maior empresa de energia do Brasil, líder em exploração em águas profundas.",
        "sector": "Energia",
        "founded": 1953
    },
    "BBDC4": {
        "name": "Bradesco",
        "description": "Um dos maiores bancos privados do Brasil, com ampla rede de agências.",
        "sector": "Financeiro", 
        "founded": 1943
    },
    "ABEV3": {
        "name": "Ambev",
        "description": "Uma das maiores cervejarias do mundo, domina o mercado brasileiro de bebidas.",
        "sector": "Bebidas",
        "founded": 1999
    },
    "WEGE3": {
        "name": "WEG",
        "description": "Líder brasileira em motores elétricos e automação industrial.",
        "sector": "Industrial",
        "founded": 1961
    },
    "MGLU3": {
        "name": "Magazine Luiza",
        "description": "Varejista brasileira pioneira em estratégia omnichannel e e-commerce.",
        "sector": "Varejo",
        "founded": 1957
    },
    # BDRs Americanas
    "AAPL34": {
        "name": "Apple Inc.",
        "description": "Líder mundial em tecnologia, conhecida por iPhone, Mac e serviços digitais.",
        "sector": "Tecnologia",
        "founded": 1976
    },
    "MSFT34": {
        "name": "Microsoft",
        "description": "Líder em software empresarial, computação em nuvem e produtividade.",
        "sector": "Tecnologia",
        "founded": 1975
    },
    "GOOGL34": {
        "name": "Alphabet (Google)",
        "description": "Domina buscas online, publicidade digital e computação em nuvem.",
        "sector": "Tecnologia",
        "founded": 2015
    },
    "AMZO34": {
        "name": "Amazon",
        "description": "Líder em e-commerce mundial e computação em nuvem (AWS).",
        "sector": "E-commerce",
        "founded": 1994
    },
    "TSLA34": {
        "name": "Tesla",
        "description": "Pioneira em veículos elétricos e armazenamento de energia.",
        "sector": "Automotivo",
        "founded": 2003
    },
    "NVDC34": {
        "name": "NVIDIA",
        "description": "Líder mundial em GPUs e computação acelerada, essencial para IA.",
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
    except Exception as e:
        print(f"Token verification error: {e}")
        return None

def get_company_info(ticker):
    """Buscar informações da empresa pelo ticker"""
    return COMPANY_INFO.get(ticker.upper(), {
        "name": ticker,
        "description": "Informações não disponíveis para este ativo.",
        "sector": "N/A",
        "founded": None
    })

# ===== SERVIÇOS DE RECOMENDAÇÕES =====

def get_admin_portfolio_recommendations_service(portfolio_name):
    """Buscar recomendações de uma carteira (Admin)"""
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
             recommendation_date, reason, price_target, current_price, 
             created_by, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true)
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
        
        # Construir query dinâmica
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
            WHERE portfolio_name = %s AND is_active = true
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
                AND recommendation_date >= %s AND is_active = true
            """, (portfolio, ticker, today))
            
            existing_rec = cursor.fetchone()
            
            if not existing_rec:
                # Inserir nova recomendação de VENDA
                cursor.execute("""
                    INSERT INTO portfolio_recommendations 
                    (portfolio_name, ticker, action_type, target_weight, 
                     recommendation_date, price_target, current_price, reason, created_by, is_active)
                    VALUES (%s, %s, 'SELL', 0, %s, %s, %s, %s, %s, true)
                """, (portfolio, ticker, today, target_price, current_price, reason, admin_user_id))
                
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
        print(f"Error generating rebalance: {e}")
        return {'success': False, 'error': str(e)}

def get_user_portfolios_service(user_id):
    """Buscar carteiras que o usuário tem acesso"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar se é admin
        cursor.execute("SELECT user_type FROM users WHERE id = %s", (user_id,))
        user_result = cursor.fetchone()
        
        if user_result and user_result[0] in ['admin', 'master']:
            # Admin tem acesso total
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
            # Usuário normal - apenas carteiras liberadas
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
        print(f"Error getting user portfolios: {e}")
        return {'success': False, 'error': str(e)}

def get_user_portfolio_recommendations_detailed_service(portfolio_name, user_id):
    """Buscar recomendações detalhadas de uma carteira para o usuário"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar se é admin
        cursor.execute("SELECT user_type FROM users WHERE id = %s", (user_id,))
        user_result = cursor.fetchone()
        is_admin = user_result and user_result[0] in ['admin', 'master']
        
        if not is_admin:
            # Verificar acesso para usuários normais
            cursor.execute("""
                SELECT id FROM user_portfolios 
                WHERE user_id = %s AND portfolio_name = %s AND is_active = true
            """, (user_id, portfolio_name))
            
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return {'success': False, 'error': 'Acesso negado a esta carteira'}
        
        # Buscar recomendações
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
        print(f"Error getting detailed recommendations: {e}")
        return {'success': False, 'error': str(e)}

def get_user_portfolio_assets_service(portfolio_name, user_id):
    """Buscar ativos de uma carteira para o usuário"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar se é admin
        cursor.execute("SELECT user_type FROM users WHERE id = %s", (user_id,))
        user_result = cursor.fetchone()
        is_admin = user_result and user_result[0] in ['admin', 'master']
        
        if not is_admin:
            # Verificar acesso para usuários normais
            cursor.execute("""
                SELECT id FROM user_portfolios 
                WHERE user_id = %s AND portfolio_name = %s AND is_active = true
            """, (user_id, portfolio_name))
            
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return {'success': False, 'error': 'Acesso negado a esta carteira'}
        
        # Buscar ativos
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
            weight = float(row[1]) if row[1] else 0
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
        print(f"Error getting user assets: {e}")
        return {'success': False, 'error': str(e)}

def get_admin_stats_service():
    """Buscar estatísticas do admin dashboard"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        # Total de usuários (excluindo admins)
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_type != 'admin'")
        total_users = cursor.fetchone()[0]
        
        # Usuários premium (plano > 3 = básico)
        cursor.execute("SELECT COUNT(*) FROM users WHERE plan_id < 3 AND user_type != 'admin'")
        premium_users = cursor.fetchone()[0]
        
        # Cupons ativos - usando OR para compatibilidade
        cursor.execute("SELECT COUNT(*) FROM coupons WHERE (is_active = true OR active = true)")
        active_coupons = cursor.fetchone()[0]
        
        # Total de recomendações ativas
        cursor.execute("SELECT COUNT(*) FROM portfolio_recommendations WHERE is_active = true")
        total_recommendations = cursor.fetchone()[0]
        
        # Receita mensal estimada
        monthly_revenue = premium_users * 75  # Estimativa
        
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