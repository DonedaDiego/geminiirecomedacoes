from flask import Blueprint, request, jsonify
from newsletter_service import newsletter_service

newsletter_bp = Blueprint('newsletter', __name__, url_prefix='/api')

@newsletter_bp.route('/newsletter', methods=['POST'])
def subscribe_newsletter():
    try:
        print("🎯 Newsletter route chamada!")
        
        data = request.get_json()
        print(f"📥 Dados recebidos: {data}")
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados necessários'}), 400
        
        email = data.get('email', '').strip().lower()
        name = data.get('name', '').strip()
        source = data.get('source', '').strip()
        
        print(f"📋 Processando: email={email}, name={name}, source={source}")
        
        if not email or '@' not in email:
            return jsonify({'success': False, 'error': 'Email inválido'}), 400
        
        result = newsletter_service.subscribe_email(email, name, source)
        print(f"📤 Resultado do service: {result}")
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
    except Exception as e:
        print(f"❌ Erro na rota newsletter: {e}")
        return jsonify({'success': False, 'error': 'Erro interno'}), 500

def get_newsletter_blueprint():
    return newsletter_bp