# test_coupons_app.py - APP PARA TESTAR CUPONS
# ===============================================

from flask import Flask, render_template_string
from flask_cors import CORS
import os

# Importar o serviço de cupons
from coupons_service import get_coupons_blueprint, init_coupons_service

# ===== CONFIGURAÇÃO DA APP =====
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'test-secret-key-12345')

# CORS para permitir requisições do frontend
CORS(app, origins=['*'])

# ===== REGISTRAR BLUEPRINT =====
app.register_blueprint(get_coupons_blueprint())

# ===== PÁGINA DE TESTE =====
@app.route('/')
def test_page():
    """Página para testar a API de cupons"""
    return render_template_string("""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Teste API Cupons</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white min-h-screen p-8">
    <div class="max-w-4xl mx-auto">
        <h1 class="text-3xl font-bold mb-8 text-center">🎫 Teste API de Cupons</h1>
        
        <!-- Status de Conexão -->
        <div class="bg-gray-800 rounded-lg p-6 mb-8">
            <h2 class="text-xl font-bold mb-4">Status da Conexão</h2>
            <button onclick="testConnection()" class="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded mr-4">
                Testar Conexão
            </button>
            <div id="connectionStatus" class="mt-4 p-3 rounded hidden"></div>
        </div>
        
        <!-- Listar Cupons -->
        <div class="bg-gray-800 rounded-lg p-6 mb-8">
            <h2 class="text-xl font-bold mb-4">Cupons Existentes</h2>
            <button onclick="loadCoupons()" class="bg-green-600 hover:bg-green-700 px-4 py-2 rounded mr-4">
                Carregar Cupons
            </button>
            <button onclick="getStats()" class="bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded">
                Ver Estatísticas
            </button>
            <div id="couponsResult" class="mt-4"></div>
        </div>
        
        <!-- Criar Cupom -->
        <div class="bg-gray-800 rounded-lg p-6 mb-8">
            <h2 class="text-xl font-bold mb-4">Criar Novo Cupom</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-sm mb-1">Código do Cupom</label>
                    <input type="text" id="couponCode" placeholder="TESTE50" 
                           class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white">
                </div>
                <div>
                    <label class="block text-sm mb-1">Desconto (%)</label>
                    <input type="number" id="couponDiscount" placeholder="50" min="1" max="100"
                           class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white">
                </div>
                <div>
                    <label class="block text-sm mb-1">Planos (segure Ctrl para múltiplos)</label>
                    <select id="couponPlans" multiple class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white">
                        <option value="pro">Pro</option>
                        <option value="premium">Premium</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm mb-1">Limite de Uso</label>
                    <input type="number" id="couponMaxUses" placeholder="100"
                           class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white">
                </div>
            </div>
            <button onclick="createCoupon()" class="mt-4 bg-green-600 hover:bg-green-700 px-6 py-2 rounded">
                Criar Cupom
            </button>
            <div id="createResult" class="mt-4"></div>
        </div>
        
        <!-- Validar Cupom -->
        <div class="bg-gray-800 rounded-lg p-6 mb-8">
            <h2 class="text-xl font-bold mb-4">Validar Cupom</h2>
            <div class="flex gap-4">
                <input type="text" id="validateCode" placeholder="Código do cupom" 
                       class="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white">
                <select id="validatePlan" class="px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white">
                    <option value="pro">Pro</option>
                    <option value="premium">Premium</option>
                </select>
                <button onclick="validateCoupon()" class="bg-yellow-600 hover:bg-yellow-700 px-6 py-2 rounded">
                    Validar
                </button>
            </div>
            <div id="validateResult" class="mt-4"></div>
        </div>
    </div>
    
    <script>
        const API_BASE = '';
        
        // Função para fazer requisições
        async function apiRequest(url, options = {}) {
            try {
                const response = await fetch(API_BASE + url, {
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer admin-test-token',
                        ...options.headers
                    },
                    ...options
                });
                
                const data = await response.json();
                return { success: response.ok, data, status: response.status };
            } catch (error) {
                return { success: false, error: error.message };
            }
        }
        
        // Testar conexão
        async function testConnection() {
            const result = await apiRequest('/api/coupons/test');
            const statusDiv = document.getElementById('connectionStatus');
            statusDiv.classList.remove('hidden');
            
            if (result.success) {
                statusDiv.className = 'mt-4 p-3 rounded bg-green-600 text-white';
                statusDiv.innerHTML = `✅ ${result.data.message}<br><small>${result.data.db_version}</small>`;
            } else {
                statusDiv.className = 'mt-4 p-3 rounded bg-red-600 text-white';
                statusDiv.innerHTML = `❌ Erro: ${result.error || result.data?.error}`;
            }
        }
        
        // Carregar cupons
        async function loadCoupons() {
            const result = await apiRequest('/api/coupons/admin/list');
            const resultDiv = document.getElementById('couponsResult');
            
            if (result.success) {
                const coupons = result.data.coupons;
                if (coupons.length === 0) {
                    resultDiv.innerHTML = '<p class="text-gray-400">Nenhum cupom encontrado</p>';
                } else {
                    resultDiv.innerHTML = `
                        <h3 class="font-bold mb-2">Total: ${coupons.length} cupons</h3>
                        <div class="space-y-2">
                            ${coupons.map(coupon => `
                                <div class="bg-gray-700 p-3 rounded flex justify-between items-center">
                                    <div>
                                        <strong>${coupon.code}</strong> - ${coupon.discount_percent}% 
                                        <span class="text-sm text-gray-400">(${coupon.applicable_plans.join(', ')})</span>
                                        <span class="ml-2 px-2 py-1 rounded text-xs ${coupon.is_active ? 'bg-green-600' : 'bg-red-600'}">
                                            ${coupon.is_active ? 'Desativar' : 'Ativar'}
                                        </button>
                                        <button onclick="deleteCoupon('${coupon.code}')" 
                                                class="px-3 py-1 rounded text-xs bg-red-600 hover:bg-red-700">
                                            Deletar
                                        </button>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `;
                }
            } else {
                resultDiv.innerHTML = `<p class="text-red-400">❌ Erro: ${result.error || result.data?.error}</p>`;
            }
        }
        
        // Criar cupom
        async function createCoupon() {
            const code = document.getElementById('couponCode').value.trim();
            const discount = document.getElementById('couponDiscount').value;
            const plansSelect = document.getElementById('couponPlans');
            const plans = Array.from(plansSelect.selectedOptions).map(opt => opt.value);
            const maxUses = document.getElementById('couponMaxUses').value;
            
            if (!code || !discount || plans.length === 0) {
                document.getElementById('createResult').innerHTML = 
                    '<p class="text-red-400">❌ Preencha código, desconto e selecione pelo menos um plano</p>';
                return;
            }
            
            const result = await apiRequest('/api/coupons/admin/create', {
                method: 'POST',
                body: JSON.stringify({
                    code: code,
                    discount_percent: parseFloat(discount),
                    applicable_plans: plans,
                    max_uses: maxUses ? parseInt(maxUses) : null
                })
            });
            
            const resultDiv = document.getElementById('createResult');
            
            if (result.success) {
                resultDiv.innerHTML = `<p class="text-green-400">✅ ${result.data.message}</p>`;
                
                // Limpar formulário
                document.getElementById('couponCode').value = '';
                document.getElementById('couponDiscount').value = '';
                document.getElementById('couponPlans').selectedIndex = -1;
                document.getElementById('couponMaxUses').value = '';
                
                // Recarregar lista
                setTimeout(loadCoupons, 1000);
            } else {
                resultDiv.innerHTML = `<p class="text-red-400">❌ Erro: ${result.error || result.data?.error}</p>`;
            }
        }
        
        // Ativar/Desativar cupom
        async function toggleCoupon(code, newStatus) {
            const result = await apiRequest(`/api/coupons/admin/toggle/${code}`, {
                method: 'PATCH',
                body: JSON.stringify({ is_active: newStatus })
            });
            
            if (result.success) {
                alert(`✅ ${result.data.message}`);
                loadCoupons();
            } else {
                alert(`❌ Erro: ${result.error || result.data?.error}`);
            }
        }
        
        // Deletar cupom
        async function deleteCoupon(code) {
            if (!confirm(`Tem certeza que deseja deletar o cupom ${code}?`)) return;
            
            const result = await apiRequest(`/api/coupons/admin/delete/${code}`, {
                method: 'DELETE'
            });
            
            if (result.success) {
                alert(`✅ ${result.data.message}`);
                loadCoupons();
            } else {
                alert(`❌ Erro: ${result.error || result.data?.error}`);
            }
        }
        
        // Validar cupom
        async function validateCoupon() {
            const code = document.getElementById('validateCode').value.trim();
            const plan = document.getElementById('validatePlan').value;
            
            if (!code) {
                document.getElementById('validateResult').innerHTML = 
                    '<p class="text-red-400">❌ Digite um código de cupom</p>';
                return;
            }
            
            const result = await apiRequest(`/api/coupons/validate/${code}`, {
                method: 'POST',
                body: JSON.stringify({
                    plan_name: plan,
                    user_id: 1
                })
            });
            
            const resultDiv = document.getElementById('validateResult');
            
            if (result.success) {
                const coupon = result.data.coupon;
                resultDiv.innerHTML = `
                    <div class="p-3 rounded bg-green-600">
                        <p class="font-bold">✅ ${result.data.message}</p>
                        <p>Código: ${coupon.code}</p>
                        <p>Desconto: ${coupon.discount_percent}%</p>
                        <p>Planos: ${coupon.applicable_plans.join(', ')}</p>
                    </div>
                `;
            } else {
                resultDiv.innerHTML = `
                    <div class="p-3 rounded bg-red-600">
                        <p>❌ ${result.error || result.data?.error}</p>
                    </div>
                `;
            }
        }
        
        // Obter estatísticas
        async function getStats() {
            const result = await apiRequest('/api/coupons/admin/stats');
            const resultDiv = document.getElementById('couponsResult');
            
            if (result.success) {
                const stats = result.data.stats;
                resultDiv.innerHTML = `
                    <div class="bg-gray-700 p-4 rounded">
                        <h3 class="font-bold mb-3">📊 Estatísticas</h3>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                            <div>
                                <div class="text-2xl font-bold text-blue-400">${stats.total_coupons}</div>
                                <div class="text-sm text-gray-400">Total</div>
                            </div>
                            <div>
                                <div class="text-2xl font-bold text-green-400">${stats.active_coupons}</div>
                                <div class="text-sm text-gray-400">Ativos</div>
                            </div>
                            <div>
                                <div class="text-2xl font-bold text-red-400">${stats.inactive_coupons}</div>
                                <div class="text-sm text-gray-400">Inativos</div>
                            </div>
                            <div>
                                <div class="text-2xl font-bold text-purple-400">${stats.total_uses}</div>
                                <div class="text-sm text-gray-400">Usos</div>
                            </div>
                        </div>
                        ${stats.top_coupons.length > 0 ? `
                            <div class="mt-4">
                                <h4 class="font-bold mb-2">Cupons Mais Usados:</h4>
                                ${stats.top_coupons.map(coupon => 
                                    `<div class="flex justify-between py-1">
                                        <span>${coupon.code}</span>
                                        <span>${coupon.uses} usos</span>
                                    </div>`
                                ).join('')}
                            </div>
                        ` : ''}
                    </div>
                `;
            } else {
                resultDiv.innerHTML = `<p class="text-red-400">❌ Erro: ${result.error || result.data?.error}</p>`;
            }
        }
        
        // Carregar cupons automaticamente ao carregar a página
        window.addEventListener('load', function() {
            testConnection();
            setTimeout(loadCoupons, 1000);
        });
    </script>
</body>
</html>
    """)

@app.route('/health')
def health_check():
    """Health check para Railway"""
    return {'status': 'ok', 'service': 'coupons-test'}

# ===== INICIALIZAÇÃO =====
if __name__ == '__main__':
    print("🚀 Iniciando app de teste de cupons...")
    
    # Inicializar serviço de cupons
    init_coupons_service()
    
    # Configurações para desenvolvimento e produção
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"🌐 Servidor rodando em: http://localhost:{port}")
    print("📋 Endpoints disponíveis:")
    print("   GET  /                           - Página de teste")
    print("   GET  /api/coupons/test           - Testar conexão")
    print("   GET  /api/coupons/admin/list     - Listar cupons")
    print("   POST /api/coupons/admin/create   - Criar cupom")
    print("   PATCH /api/coupons/admin/toggle/<code> - Ativar/desativar")
    print("   DELETE /api/coupons/admin/delete/<code> - Deletar cupom")
    print("   POST /api/coupons/validate/<code> - Validar cupom")
    print("   GET  /api/coupons/admin/stats    - Estatísticas")
    
