# railway_sync_routes.py - Blueprint para sincronização Railway

from flask import Blueprint, jsonify
from pro.railway_sync_service import RailwaySyncService

railway_bp = Blueprint('railway', __name__, url_prefix='/railway')

# Inicializar serviço
sync_service = RailwaySyncService()

@railway_bp.route('/health', methods=['GET'])
def health_check():
    """Health check do serviço"""
    return jsonify({
        "status": "ok",
        "service": "railway_sync"
    })

@railway_bp.route('/status', methods=['GET'])
def get_status():
    """Retorna status atual do banco Railway"""
    try:
        status = sync_service.obter_status()
        return jsonify({
            "success": True,
            "data": status
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@railway_bp.route('/sync', methods=['POST'])
def sincronizar():
    """Sincroniza todas as datas disponíveis"""
    try:
        datas = sync_service.obter_datas_disponiveis()
        
        resultado = sync_service.sincronizar_datas(datas)
        
        return jsonify({
            "success": True,
            "data": resultado
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@railway_bp.route('/datas-disponiveis', methods=['GET'])
def listar_datas():
    """Lista datas disponíveis para sincronização"""
    try:
        datas = sync_service.obter_datas_disponiveis()
        
        # Formatar datas
        datas_formatadas = []
        for data_str in datas:
            from datetime import datetime
            data_obj = datetime.strptime(data_str, '%Y%m%d')
            
            # Verificar se existe
            existe = sync_service.verificar_data_existe(data_obj)
            
            datas_formatadas.append({
                "data_raw": data_str,
                "data_formatada": data_obj.strftime('%d/%m/%Y'),
                "existe_no_banco": existe,
                "status": "✅ Sincronizado" if existe else "⏳ Pendente"
            })
        
        return jsonify({
            "success": True,
            "total": len(datas_formatadas),
            "datas": datas_formatadas
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@railway_bp.route('/resumo', methods=['GET'])
def obter_resumo():
    """Resumo executivo da sincronização"""
    try:
        status = sync_service.obter_status()
        datas = sync_service.obter_datas_disponiveis()
        
        # Contar quantas já existem
        from datetime import datetime
        datas_sincronizadas = 0
        datas_pendentes = 0
        
        for data_str in datas:
            data_obj = datetime.strptime(data_str, '%Y%m%d')
            if sync_service.verificar_data_existe(data_obj):
                datas_sincronizadas += 1
            else:
                datas_pendentes += 1
        
        return jsonify({
            "success": True,
            "resumo": {
                "total_registros": status.get('total_registros', 0),
                "datas_no_banco": status.get('datas_disponiveis', 0),
                "ultima_atualizacao": status.get('ultima_atualizacao'),
                "datas_configuradas": len(datas),
                "datas_sincronizadas": datas_sincronizadas,
                "datas_pendentes": datas_pendentes,
                "percentual_completo": round((datas_sincronizadas / len(datas) * 100), 2) if datas else 0
            },
            "top_tickers": status.get('top_tickers', [])
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500