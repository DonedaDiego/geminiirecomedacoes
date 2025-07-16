# recommendation_opcoes_service.py - SERVIÇOS DE RECOMENDAÇÕES DE OPÇÕES

from database import get_db_connection
from datetime import datetime
import jwt
import os

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

# ===== SERVIÇOS DE RECOMENDAÇÕES DE OPÇÕES =====

def create_opcoes_recommendation_service(data, admin_id):
    """Criar nova recomendação de opção"""
    try:
        # Validar dados obrigatórios
        required_fields = ['ativo_spot', 'ticker_opcao', 'strike', 'valor_entrada', 'vencimento', 'data_recomendacao', 'stop', 'gain']
        for field in required_fields:
            if field not in data or data[field] is None:
                return {'success': False, 'error': f'Campo {field} é obrigatório'}
        
        # Validações específicas
        if data['valor_entrada'] <= 0:
            return {'success': False, 'error': 'Valor de entrada deve ser maior que zero'}
        
        if data['strike'] <= 0:
            return {'success': False, 'error': 'Strike deve ser maior que zero'}
        
        if data['stop'] < 0:
            return {'success': False, 'error': 'Stop não pode ser negativo'}
        
        if data['gain'] <= 0:
            return {'success': False, 'error': 'Gain deve ser maior que zero'}
        
        # Validar data de vencimento (deve ser futura)
        try:
            vencimento_date = datetime.strptime(data['vencimento'], '%Y-%m-%d').date()
            if vencimento_date <= datetime.now().date():
                return {'success': False, 'error': 'Data de vencimento deve ser futura'}
        except ValueError:
            return {'success': False, 'error': 'Formato de data de vencimento inválido'}
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        # Inserir recomendação de opção
        cursor.execute('''
            INSERT INTO opcoes_recommendations 
            (ativo_spot, ticker_opcao, strike, valor_entrada, vencimento, 
             data_recomendacao, stop, gain, gain_parcial, status, created_by, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            data['ativo_spot'].upper(),
            data['ticker_opcao'].upper(), 
            data['strike'],
            data['valor_entrada'],
            data['vencimento'],
            data['data_recomendacao'],
            data['stop'],
            data['gain'],
            data.get('gain_parcial'),  # Campo opcional
            'ATIVA',  # Status inicial
            admin_id,
            True
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': f'Recomendação de opção {data["ticker_opcao"]} criada com sucesso!'
        }
        
    except Exception as e:
        print(f"Error creating opcoes recommendation: {e}")
        return {'success': False, 'error': str(e)}

def get_all_opcoes_recommendations_service():
    """Buscar todas as recomendações de opções"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                id, ativo_spot, ticker_opcao, strike, valor_entrada, 
                vencimento, data_recomendacao, stop, gain, gain_parcial,
                status, created_at, updated_at, is_active
            FROM opcoes_recommendations 
            WHERE is_active = true
            ORDER BY created_at DESC
        ''')
        
                
        rows = cursor.fetchall()
                
        recommendations = []
        for i, row in enumerate(rows):
            print(f"📋 Row {i}: {row}")  # ✅ LOG CADA LINHA
            
            recommendations.append({
                'id': row[0],
                'ativo_spot': row[1],
                'ticker_opcao': row[2],
                'strike': float(row[3]) if row[3] else 0,
                'valor_entrada': float(row[4]) if row[4] else 0,
                'vencimento': row[5].isoformat() if row[5] else None,
                'data_recomendacao': row[6].isoformat() if row[6] else None,
                'stop': float(row[7]) if row[7] else 0,
                'gain': float(row[8]) if row[8] else 0,
                'gain_parcial': float(row[9]) if row[9] else None,
                'status': row[10],  
                'created_at': row[11].isoformat() if row[11] else None,
                'updated_at': row[12].isoformat() if row[12] else None,
                'is_active': row[13]
            })
        
                
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'recommendations': recommendations
        }
        
    except Exception as e:
        print(f"Error getting opcoes recommendations: {e}")
        return {'success': False, 'error': str(e)}

def update_opcoes_recommendation_service(data):
    """Atualizar recomendação de opção existente"""
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
        
        updatable_fields = [
            'ativo_spot', 'ticker_opcao', 'strike', 'valor_entrada', 
            'vencimento', 'data_recomendacao', 'stop', 'gain', 
            'gain_parcial', 'status'
        ]
        
        for field in updatable_fields:
            if field in data:
                if field in ['ativo_spot', 'ticker_opcao']:
                    update_fields.append(f"{field} = %s")
                    update_values.append(data[field].upper())
                else:
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
            UPDATE opcoes_recommendations 
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
            'message': 'Recomendação de opção atualizada com sucesso!'
        }
        
    except Exception as e:
        print(f"Error updating opcoes recommendation: {e}")
        return {'success': False, 'error': str(e)}

def delete_opcoes_recommendation_service(recommendation_id):
    """Deletar recomendação de opção (soft delete)"""
    try:
        if not recommendation_id:
            return {'success': False, 'error': 'ID da recomendação é obrigatório'}
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE opcoes_recommendations 
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
            'message': 'Recomendação de opção removida com sucesso!'
        }
        
    except Exception as e:
        print(f"Error deleting opcoes recommendation: {e}")
        return {'success': False, 'error': str(e)}

def close_opcoes_recommendation_service(recommendation_id, status, resultado_final=None):
    """Fechar recomendação de opção com resultado"""
    try:
        if not recommendation_id:
            return {'success': False, 'error': 'ID da recomendação é obrigatório'}
        
        if status not in ['FINALIZADA_GANHO', 'FINALIZADA_STOP', 'FINALIZADA_VENCIMENTO', 'FINALIZADA_MANUAL']:
            return {'success': False, 'error': 'Status inválido'}
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        # Buscar dados da recomendação
        cursor.execute('''
            SELECT ativo_spot, ticker_opcao, valor_entrada, stop, gain
            FROM opcoes_recommendations 
            WHERE id = %s AND is_active = true
        ''', (recommendation_id,))
        
        recommendation = cursor.fetchone()
        if not recommendation:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Recomendação não encontrada'}
        
        ativo_spot, ticker_opcao, valor_entrada, stop, gain = recommendation
        
        # Calcular performance se resultado_final foi fornecido
        performance = None
        if resultado_final:
            performance = ((resultado_final - valor_entrada) / valor_entrada) * 100
        
        # Atualizar status da recomendação
        cursor.execute('''
            UPDATE opcoes_recommendations 
            SET status = %s, resultado_final = %s, performance = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (status, resultado_final, performance, recommendation_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': f'Recomendação {ticker_opcao} finalizada com sucesso!',
            'performance': performance
        }
        
    except Exception as e:
        print(f"Error closing opcoes recommendation: {e}")
        return {'success': False, 'error': str(e)}

def get_opcoes_stats_service():
    """Buscar estatísticas das recomendações de opções"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        # Total de recomendações
        cursor.execute("SELECT COUNT(*) FROM opcoes_recommendations WHERE is_active = true")
        total_recommendations = cursor.fetchone()[0]
        
        # Recomendações ativas
        cursor.execute("SELECT COUNT(*) FROM opcoes_recommendations WHERE status = 'ATIVA' AND is_active = true")
        active_recommendations = cursor.fetchone()[0]
        
        # Recomendações finalizadas com ganho
        cursor.execute("SELECT COUNT(*) FROM opcoes_recommendations WHERE status = 'FINALIZADA_GANHO' AND is_active = true")
        win_recommendations = cursor.fetchone()[0]
        
        # Recomendações finalizadas com perda
        cursor.execute("SELECT COUNT(*) FROM opcoes_recommendations WHERE status IN ('FINALIZADA_STOP', 'FINALIZADA_VENCIMENTO') AND is_active = true")
        loss_recommendations = cursor.fetchone()[0]
        
        # Performance média
        cursor.execute("""
            SELECT AVG(performance) 
            FROM opcoes_recommendations 
            WHERE performance IS NOT NULL AND is_active = true
        """)
        avg_performance = cursor.fetchone()[0] or 0
        
        cursor.close()
        conn.close()
        
        # Calcular taxa de acerto
        total_closed = win_recommendations + loss_recommendations
        win_rate = (win_recommendations / total_closed * 100) if total_closed > 0 else 0
        
        return {
            'success': True,
            'stats': {
                'total_recommendations': total_recommendations,
                'active_recommendations': active_recommendations,
                'win_recommendations': win_recommendations,
                'loss_recommendations': loss_recommendations,
                'win_rate': round(win_rate, 2),
                'avg_performance': round(float(avg_performance), 2)
            }
        }
        
    except Exception as e:
        print(f"Error getting opcoes stats: {e}")
        return {'success': False, 'error': str(e)}