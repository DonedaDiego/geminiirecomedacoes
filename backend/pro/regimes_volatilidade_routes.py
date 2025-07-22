from flask import Blueprint, jsonify, request
from pro.regimes_volatilidade_service import RegimesVolatilidadeService

regimes_bp = Blueprint('regimes', __name__)
service = RegimesVolatilidadeService()

@regimes_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "regimes_volatilidade"})

@regimes_bp.route('/analyze/<symbol>', methods=['GET'])
def analyze_symbol(symbol):
    try:
        period = request.args.get('period', '6mo')
        result = service.analisar_acao(symbol, period)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@regimes_bp.route('/screener', methods=['GET'])
def screener():
    symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
    results = []
    
    for symbol in symbols:
        try:
            analysis = service.analisar_acao(symbol, '3mo')
            if analysis['success'] and analysis['trading_signal']['confidence'] >= 60:
                results.append({
                    "ticker": symbol,
                    "signal": analysis['trading_signal']['signal'],
                    "strategy": analysis['trading_signal']['strategy'],
                    "confidence": analysis['trading_signal']['confidence'],
                    "regime": analysis['metrics']['regime']['name'],
                    "current_price": analysis['current_price']
                })
        except:
            continue
    
    return jsonify({
        "success": True,
        "total_found": len(results),
        "screener_results": results
    })