from flask import Blueprint, render_template, request, jsonify
from gratis.copom_service import get_dados_completos, REUNIOES_COPOM

copom_bp = Blueprint('copom', __name__)


@copom_bp.route('/copom')
def copom():
    """Página principal do módulo COPOM."""
    ref_date = request.args.get('ref_date')
    meeting_date = request.args.get('meeting_date')

    dados = get_dados_completos(ref_date=ref_date, meeting_date=meeting_date)
    return render_template('copom.html', dados=dados)


@copom_bp.route('/api/copom/dados')
def api_copom_dados():
    """API JSON para o frontend atualizar os dados via AJAX."""
    ref_date = request.args.get('ref_date')
    meeting_date = request.args.get('meeting_date')
    days = int(request.args.get('days', 60))

    dados = get_dados_completos(ref_date=ref_date, meeting_date=meeting_date, days=days)
    return jsonify(dados)


@copom_bp.route('/api/copom/reunioes')
def api_reunioes():
    """Retorna lista de reuniões COPOM disponíveis."""
    return jsonify(REUNIOES_COPOM)