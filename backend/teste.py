# atsmom antigo 


# <!DOCTYPE html>
# <html lang="pt-BR">
# <head>
#   <meta charset="UTF-8">
#   <meta name="viewport" content="width=device-width, initial-scale=1.0">
#   <title>ATSMOM - Geminii Tech</title>
#   <script src="https://cdn.tailwindcss.com"></script>
#   <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
#   <script>
#     tailwind.config = {
#       theme: {
#         extend: {
#           colors: {
#             dark: '#000000',
#             light: '#ffffff',
#             subtle: 'rgba(255,255,255,0.1)',
#             geminii: '#ba39af'
#           },
#           fontFamily: {
#             sans: ['Inter', 'sans-serif']
#           }
#         }
#       }
#     }
#   </script>
#   <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
#   <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
#   <style>
#     body { 
#       font-family: 'Inter', sans-serif; 
#       background: linear-gradient(135deg, #0c0c0c 0%, #1a1a1a 100%);
#       min-height: 100vh;
#     }
    
#     .beta-card {
#       background: rgba(255, 255, 255, 0.08);
#       backdrop-filter: blur(20px);
#       border: 1px solid rgba(255, 255, 255, 0.2);
#       border-radius: 16px;
#       transition: all 0.3s ease;
#     }
    
#     .beta-card:hover {
#       transform: translateY(-2px);
#       box-shadow: 0 20px 40px rgba(186, 57, 175, 0.15);
#       border-color: rgba(186, 57, 175, 0.3);
#     }
    
#     .loading {
#       opacity: 0.6;
#       pointer-events: none;
#     }
    
#     .spinner {
#       border: 2px solid rgba(255, 255, 255, 0.1);
#       border-radius: 50%;
#       border-top: 2px solid #ba39af;
#       width: 20px;
#       height: 20px;
#       animation: spin 1s linear infinite;
#       display: inline-block;
#     }
    
#     @keyframes spin {
#       0% { transform: rotate(0deg); }
#       100% { transform: rotate(360deg); }
#     }
    
#     .signal-card {
#       background: rgba(255, 255, 255, 0.05);
#       border: 1px solid rgba(255, 255, 255, 0.1);
#       border-radius: 12px;
#       padding: 16px;
#       transition: all 0.3s ease;
#     }
    
#     .signal-card:hover {
#       background: rgba(255, 255, 255, 0.08);
#       border-color: rgba(186, 57, 175, 0.3);
#     }
    
#     .signal-compra { border-left: 4px solid #10b981; }
#     .signal-venda { border-left: 4px solid #ef4444; }
#     .signal-neutro { border-left: 4px solid #6b7280; }

#     /* Estilos escuros para select */
#     .dark-select {
#       background-color: rgba(30, 30, 30, 0.9);
#       border: 1px solid rgba(255, 255, 255, 0.2);
#       color: white;
#       backdrop-filter: blur(10px);
#     }

#     .dark-select option {
#       background-color: #1a1a1a;
#       color: white;
#       padding: 8px;
#     }

#     .dark-select:focus {
#       outline: none;
#       border-color: #ba39af;
#       box-shadow: 0 0 0 2px rgba(186, 57, 175, 0.2);
#     }

#     /* Tabs */
#     .tab-button {
#       padding: 12px 24px;
#       border-radius: 8px;
#       border: 1px solid rgba(255, 255, 255, 0.1);
#       background: rgba(255, 255, 255, 0.05);
#       color: #94a3b8;
#       cursor: pointer;
#       transition: all 0.3s ease;
#       font-weight: 500;
#     }

#     .tab-button.active {
#       background: linear-gradient(135deg, #ba39af, #8b5cf6);
#       color: white;
#       border-color: rgba(186, 57, 175, 0.3);
#     }

#     .tab-button:not(.active):hover {
#       background: rgba(255, 255, 255, 0.08);
#       color: #e2e8f0;
#       border-color: rgba(255, 255, 255, 0.2);
#     }

#     .tab-content {
#       display: none;
#     }

#     .tab-content.active {
#       display: block;
#       animation: fadeIn 0.3s ease-in-out;
#     }

#     @keyframes fadeIn {
#       from { opacity: 0; transform: translateY(10px); }
#       to { opacity: 1; transform: translateY(0); }
#     }

#     /* Plotly Container */
#     .plotly-container {
#       background: rgba(255, 255, 255, 0.02);
#       border-radius: 12px;
#       padding: 20px;
#       min-height: 600px;
#     }
#   </style>
# </head>
# <body class="text-white">
  
#   <!-- Navbar -->
#   <nav class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50 bg-opacity-5 border-opacity-10 bg-white border-white border rounded-full px-4 py-3 shadow-xl backdrop-blur-md">
#     <div class="flex items-center justify-between">
#       <div class="flex items-center">
#         <img src="/assets/logo.png" alt="Geminii Logo" class="w-6 h-6 cursor-pointer" onclick="window.location.href='/dashboard'">
#       </div>
#       <div class="hidden md:flex items-center space-x-6 text-xs text-gray-300 ml-8">
#         <a href="/dashboard" class="hover:text-white transition-colors">Dashboard</a>
#         <span class="text-white font-medium">ATSMOM</span>
#         <a href="/beta-regression" class="hover:text-white transition-colors">Beta Regression</a>
#         <a href="/swing-trade-machine-learning" class="hover:text-white transition-colors">ML Trading</a>
#       </div>
#       <div class="flex items-center space-x-3 ml-8">
#         <div id="apiStatus" class="w-8 h-8 bg-green-500 bg-opacity-10 border border-green-500 border-opacity-30 rounded-full flex items-center justify-center relative">
#           <i class="fas fa-chart-line text-green-500 text-xs"></i>
#           <div class="absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
#         </div>
#       </div>
#     </div>
#   </nav>

#   <!-- Content -->
#   <div class="pt-32 pb-16">
#     <div class="max-w-7xl mx-auto px-6">
      
#       <!-- Header -->
#       <div class="text-center mb-12">
#         <h1 class="text-4xl md:text-5xl font-bold mb-4">
#           <span style="color: #ba39af; font-weight: 900;">ATSMOM</span>
#           <span class="text-white font-light">Analytics</span>
#         </h1>
#         <p class="text-neutral-300 text-lg max-w-2xl mx-auto">
#           Adaptive Time Series Momentum - Análise Avançada de Sinais de Trading
#         </p>
#       </div>

#       <!-- Tabs -->
#       <div class="beta-card p-6 mb-8">
#         <div class="flex flex-wrap gap-2 mb-6 justify-center">
#           <button class="tab-button active" data-tab="individual">
#             <i class="fas fa-chart-line mr-2"></i>Análise Individual
#           </button>
#           <button class="tab-button" data-tab="bulk">
#             <i class="fas fa-list mr-2"></i>Análise em Lote
#           </button>
#           <button class="tab-button" data-tab="compare">
#             <i class="fas fa-balance-scale mr-2"></i>Comparar Ativos
#           </button>
#           <button class="tab-button" data-tab="overview">
#             <i class="fas fa-globe mr-2"></i>Visão Geral
#           </button>
#         </div>

#         <!-- Tab Content: Individual -->
#         <div id="individual-content" class="tab-content active">
#           <div class="flex flex-col md:flex-row gap-4 items-center justify-center">
#             <div class="flex gap-3 flex-wrap items-center">
#               <input 
#                 id="individual-symbol" 
#                 type="text" 
#                 placeholder="Digite o código da ação (ex: PETR4)" 
#                 class="px-4 py-2 bg-white bg-opacity-10 border border-white border-opacity-20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-geminii backdrop-blur-sm"
#               >
#               <select id="individual-period" class="dark-select px-4 py-2 rounded-lg">
#                 <option value="1y">1 Ano</option>
#                 <option value="2y" selected>2 Anos</option>
#                 <option value="5y">5 Anos</option>
#                 <option value="max">Máximo</option>
#               </select>
#               <input 
#                 id="individual-strike" 
#                 type="number" 
#                 placeholder="Strike (opcional)" 
#                 step="0.01"
#                 class="px-4 py-2 bg-white bg-opacity-10 border border-white border-opacity-20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-geminii backdrop-blur-sm"
#               >
#               <button id="analyzeIndividualBtn" class="px-6 py-2 bg-gradient-to-r from-pink-500 to-purple-600 hover:shadow-lg rounded-lg transition-all font-medium">
#                 <i class="fas fa-rocket mr-2"></i>Analisar ATSMOM
#               </button>
#             </div>
#           </div>
#         </div>

#         <!-- Tab Content: Bulk -->
#         <div id="bulk-content" class="tab-content">
#           <div class="flex flex-col md:flex-row gap-4 items-center justify-center">
#             <div class="flex gap-3 flex-wrap items-center">
#               <select id="bulk-period" class="dark-select px-4 py-2 rounded-lg">
#                 <option value="1y">1 Ano</option>
#                 <option value="2y" selected>2 Anos</option>
#                 <option value="5y">5 Anos</option>
#                 <option value="max">Máximo</option>
#               </select>
#               <input 
#                 id="bulk-symbols" 
#                 type="text" 
#                 placeholder="Símbolos separados por vírgula (opcional)" 
#                 class="px-4 py-2 bg-white bg-opacity-10 border border-white border-opacity-20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-geminii backdrop-blur-sm w-80"
#               >
#               <button id="analyzeBulkBtn" class="px-6 py-2 bg-gradient-to-r from-orange-500 to-red-600 hover:shadow-lg rounded-lg transition-all font-medium">
#                 <i class="fas fa-list mr-2"></i>Analisar Carteira
#               </button>
#             </div>
#           </div>
#         </div>

#         <!-- Tab Content: Compare -->
#         <div id="compare-content" class="tab-content">
#           <div class="flex flex-col md:flex-row gap-4 items-center justify-center">
#             <div class="flex gap-3 flex-wrap items-center">
#               <input 
#                 id="compare-symbol1" 
#                 type="text" 
#                 placeholder="Primeiro ativo (ex: PETR4)" 
#                 class="px-4 py-2 bg-white bg-opacity-10 border border-white border-opacity-20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-geminii backdrop-blur-sm"
#               >
#               <input 
#                 id="compare-symbol2" 
#                 type="text" 
#                 placeholder="Segundo ativo (ex: VALE3)" 
#                 class="px-4 py-2 bg-white bg-opacity-10 border border-white border-opacity-20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-geminii backdrop-blur-sm"
#               >
#               <select id="compare-period" class="dark-select px-4 py-2 rounded-lg">
#                 <option value="1y">1 Ano</option>
#                 <option value="2y" selected>2 Anos</option>
#                 <option value="5y">5 Anos</option>
#                 <option value="max">Máximo</option>
#               </select>
#               <button id="compareBtn" class="px-6 py-2 bg-gradient-to-r from-purple-500 to-blue-600 hover:shadow-lg rounded-lg transition-all font-medium">
#                 <i class="fas fa-balance-scale mr-2"></i>Comparar
#               </button>
#             </div>
#           </div>
#         </div>

#         <!-- Tab Content: Overview -->
#         <div id="overview-content" class="tab-content">
#           <div class="flex flex-col md:flex-row gap-4 items-center justify-center">
#             <div class="flex gap-3 flex-wrap items-center">
#               <select id="overview-period" class="dark-select px-4 py-2 rounded-lg">
#                 <option value="1y">1 Ano</option>
#                 <option value="2y" selected>2 Anos</option>
#                 <option value="5y">5 Anos</option>
#                 <option value="max">Máximo</option>
#               </select>
#               <button id="overviewBtn" class="px-6 py-2 bg-gradient-to-r from-green-500 to-teal-600 hover:shadow-lg rounded-lg transition-all font-medium">
#                 <i class="fas fa-globe mr-2"></i>Visão Geral
#               </button>
#             </div>
#           </div>
#         </div>
#       </div>

#       <!-- Status -->
#       <div id="statusMsg" class="mb-6 p-4 rounded-lg hidden backdrop-blur-sm"></div>

#       <!-- Análise Individual - Resultados -->
#       <div id="individual-results" class="mb-8 hidden">
#         <div class="beta-card p-6">
#           <div class="flex justify-between items-center mb-6">
#             <h3 id="individual-title" class="text-2xl font-bold"></h3>
#             <div id="individual-timestamp" class="text-sm text-gray-400"></div>
#           </div>
          
#           <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
#             <div class="bg-white bg-opacity-5 p-4 rounded-lg">
#               <div class="text-sm text-gray-400">Sinal Atual</div>
#               <div id="individual-signal" class="text-xl font-bold"></div>
#             </div>
            
#             <div class="bg-white bg-opacity-5 p-4 rounded-lg">
#               <div class="text-sm text-gray-400">Preço Atual</div>
#               <div id="individual-price" class="text-xl font-bold"></div>
#             </div>
            
#             <div class="bg-white bg-opacity-5 p-4 rounded-lg">
#               <div class="text-sm text-gray-400">Força do Sinal</div>
#               <div id="individual-strength" class="text-xl font-bold"></div>
#             </div>
            
#             <div class="bg-white bg-opacity-5 p-4 rounded-lg">
#               <div class="text-sm text-gray-400">Volatilidade</div>
#               <div id="individual-volatility" class="text-xl font-bold"></div>
#             </div>
#           </div>
          
#           <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
#             <div>
#               <h4 class="text-lg font-semibold mb-4">Métricas ATSMOM</h4>
#               <div class="space-y-3">
#                 <div class="bg-white bg-opacity-5 p-3 rounded-lg flex justify-between">
#                   <span class="text-gray-400">Tendência:</span>
#                   <span id="individual-trend" class="font-semibold">0</span>
#                 </div>
#                 <div class="bg-white bg-opacity-5 p-3 rounded-lg flex justify-between">
#                   <span class="text-gray-400">Beta:</span>
#                   <span id="individual-beta" class="font-semibold">0</span>
#                 </div>
#                 <div class="bg-white bg-opacity-5 p-3 rounded-lg flex justify-between">
#                   <span class="text-gray-400">Última Atualização:</span>
#                   <span id="individual-update" class="font-semibold text-xs">--</span>
#                 </div>
#               </div>
#             </div>
            
#             <div id="individual-strike-analysis" class="hidden">
#               <h4 class="text-lg font-semibold mb-4">Análise de Strike</h4>
#               <div class="space-y-3">
#                 <div class="bg-white bg-opacity-5 p-3 rounded-lg flex justify-between">
#                   <span class="text-gray-400">Strike:</span>
#                   <span id="strike-price" class="font-semibold">R$ 0,00</span>
#                 </div>
#                 <div class="bg-white bg-opacity-5 p-3 rounded-lg flex justify-between">
#                   <span class="text-gray-400">Distância:</span>
#                   <span id="strike-distance" class="font-semibold">0%</span>
#                 </div>
#                 <div class="bg-white bg-opacity-5 p-3 rounded">
#                   <div class="text-gray-400 text-sm mb-2">Análise:</div>
#                   <div id="strike-analysis-text" class="text-xs leading-relaxed">--</div>
#                 </div>
#               </div>
#             </div>
#           </div>
#         </div>
#       </div>

#       <!-- Gráfico ATSMOM Principal -->
#       <div id="plotly-chart-container" class="mb-8 hidden">
#         <div class="beta-card p-6">
#           <h3 class="text-xl font-bold mb-4">
#             <i class="fas fa-chart-area text-purple-400 mr-2"></i>
#             Análise ATSMOM Completa
#           </h3>
#           <div class="plotly-container">
#             <div id="plotly-chart" style="width: 100%; height: 600px;"></div>
#           </div>
#         </div>
#       </div>

#       <!-- Análise em Lote - Resultados -->
#       <div id="bulk-results" class="mb-8 hidden">
#         <div class="beta-card p-6">
#           <h3 class="text-xl font-bold mb-6">Resumo da Carteira ATSMOM</h3>
          
#           <!-- Resumo Cards -->
#           <div id="bulk-summary" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6"></div>
          
#           <!-- Tabela -->
#           <div class="overflow-x-auto">
#             <table class="w-full">
#               <thead>
#                 <tr class="border-b border-white border-opacity-10">
#                   <th class="text-left py-3 px-4">Ativo</th>
#                   <th class="text-left py-3 px-4">Preço</th>
#                   <th class="text-left py-3 px-4">Sinal</th>
#                   <th class="text-left py-3 px-4">Força</th>
#                   <th class="text-left py-3 px-4">Tendência</th>
#                   <th class="text-left py-3 px-4">Volatilidade</th>
#                   <th class="text-left py-3 px-4">Beta</th>
#                 </tr>
#               </thead>
#               <tbody id="bulk-table-body">
#                 <!-- Resultados serão inseridos aqui -->
#               </tbody>
#             </table>
#           </div>
#         </div>
#       </div>

#       <!-- Comparação - Resultados -->
#       <div id="compare-results" class="mb-8 hidden">
#         <div class="beta-card p-6 mb-6">
#           <h3 class="text-xl font-bold mb-4">Resumo da Comparação</h3>
#           <div id="comparison-summary" class="grid grid-cols-1 md:grid-cols-3 gap-4"></div>
#         </div>
        
#         <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
#           <div id="compare-asset1" class="beta-card p-6">
#             <!-- Primeiro ativo -->
#           </div>
#           <div id="compare-asset2" class="beta-card p-6">
#             <!-- Segundo ativo -->
#           </div>
#         </div>
#       </div>

#       <!-- Visão Geral - Resultados -->
#       <div id="overview-results" class="mb-8 hidden">
#         <div class="beta-card p-6">
#           <h3 class="text-xl font-bold mb-6">Visão Geral do Mercado</h3>
          
#           <!-- Stats Cards -->
#           <div id="overview-stats" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4 mb-6"></div>
          
#           <!-- Tabela -->
#           <div class="overflow-x-auto">
#             <table class="w-full">
#               <thead>
#                 <tr class="border-b border-white border-opacity-10">
#                   <th class="text-left py-3 px-4">Ativo</th>
#                   <th class="text-left py-3 px-4">Preço</th>
#                   <th class="text-left py-3 px-4">Sinal</th>
#                   <th class="text-left py-3 px-4">Força</th>
#                   <th class="text-left py-3 px-4">Volatilidade</th>
#                   <th class="text-left py-3 px-4">Beta</th>
#                 </tr>
#               </thead>
#               <tbody id="overview-table-body">
#                 <!-- Resultados serão inseridos aqui -->
#               </tbody>
#             </table>
#           </div>
#         </div>
#       </div>

#     </div>
#   </div>

#   <script>
#     // Configurações
#     const API_BASE = window.location.origin + '/atsmom';
    
#     // Elements
#     const statusMsg = document.getElementById('statusMsg');
    
#     // Funções utilitárias
#     function showStatus(message, type = 'info') {
#       const bgClass = type === 'success' ? 'bg-green-600 bg-opacity-20 border-green-500 border-opacity-30' : 
#                      type === 'error' ? 'bg-red-600 bg-opacity-20 border-red-500 border-opacity-30' : 
#                      'bg-blue-600 bg-opacity-20 border-blue-500 border-opacity-30';
      
#       statusMsg.className = `mb-6 p-4 rounded-lg border backdrop-blur-sm ${bgClass}`;
#       statusMsg.textContent = message;
#       statusMsg.classList.remove('hidden');
#       setTimeout(() => statusMsg.classList.add('hidden'), 5000);
#     }
    
#     function formatCurrency(value) {
#       return new Intl.NumberFormat('pt-BR', {
#         style: 'currency',
#         currency: 'BRL'
#       }).format(value);
#     }
    
#     function setLoading(element, loading) {
#       if (loading) {
#         element.classList.add('loading');
#         const icon = element.querySelector('i');
#         if (icon) icon.className = 'fas fa-spinner fa-spin mr-2';
#       } else {
#         element.classList.remove('loading');
#         const icon = element.querySelector('i');
#         if (icon && element.id === 'analyzeIndividualBtn') icon.className = 'fas fa-rocket mr-2';
#         if (icon && element.id === 'analyzeBulkBtn') icon.className = 'fas fa-list mr-2';
#         if (icon && element.id === 'compareBtn') icon.className = 'fas fa-balance-scale mr-2';
#         if (icon && element.id === 'overviewBtn') icon.className = 'fas fa-globe mr-2';
#       }
#     }
    
#     function getStatusColor(status) {
#       switch(status) {
#         case 'COMPRA': return 'text-green-400';
#         case 'VENDA': return 'text-red-400';
#         default: return 'text-gray-400';
#       }
#     }
    
#     function hideAllResults() {
#       document.getElementById('individual-results').classList.add('hidden');
#       document.getElementById('plotly-chart-container').classList.add('hidden');
#       document.getElementById('bulk-results').classList.add('hidden');
#       document.getElementById('compare-results').classList.add('hidden');
#       document.getElementById('overview-results').classList.add('hidden');
#     }

#     // Tab Navigation
#     document.querySelectorAll('.tab-button').forEach(button => {
#       button.addEventListener('click', () => {
#         // Remove active from all tabs
#         document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
#         document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        
#         // Add active to clicked tab
#         button.classList.add('active');
#         const tabId = button.getAttribute('data-tab');
#         document.getElementById(`${tabId}-content`).classList.add('active');
        
#         // Hide results
#         hideAllResults();
#       });
#     });

#     // Análise Individual
#     async function analyzeIndividual() {
#       const symbol = document.getElementById('individual-symbol').value.trim().toUpperCase();
#       const period = document.getElementById('individual-period').value;
#       const strike = document.getElementById('individual-strike').value;
#       const btn = document.getElementById('analyzeIndividualBtn');

#       if (!symbol) {
#         showStatus('Digite o código de uma ação', 'error');
#         return;
#       }

#       setLoading(btn, true);
#       hideAllResults();
#       showStatus('Executando análise ATSMOM... Isso pode levar alguns segundos', 'info');

#       try {
#         const payload = {
#           symbol: symbol,
#           period: period
#         };

#         if (strike && strike.trim() !== '') {
#           payload.strike = parseFloat(strike);
#         }

#         const response = await fetch(`${API_BASE}/analyze`, {
#           method: 'POST',
#           headers: {
#             'Content-Type': 'application/json',
#           },
#           body: JSON.stringify(payload)
#         });

#         const data = await response.json();
#         console.log('=== DADOS RECEBIDOS DO BACKEND ===');
#         console.log('Success:', data.success);
#         console.log('Dados completos:', data);

#         if (data.success) {
#           displayIndividualResults(data);
#           showStatus(`Análise ATSMOM de ${symbol} concluída com sucesso!`, 'success');
#         } else {
#           showStatus(data.error || 'Erro na análise', 'error');
#         }
#       } catch (error) {
#         showStatus('Erro ao executar análise', 'error');
#         console.error(error);
#       }

#       setLoading(btn, false);
#     }

#     // Display Individual Results - CORRIGIDO IGUAL AO BETA REGRESSION
#     function displayIndividualResults(data) {
#       console.log('=== DISPLAY INDIVIDUAL RESULTS ===');
#       console.log('Data recebida:', data);
      
#       const analysis = data.analysis_data;
      
#       // Header
#       document.getElementById('individual-title').textContent = `${analysis.symbol} - ATSMOM`;
#       document.getElementById('individual-timestamp').textContent = analysis.last_update;
      
#       // Main metrics
#       document.getElementById('individual-signal').textContent = analysis.signal_status;
#       document.getElementById('individual-signal').className = `text-xl font-bold ${getStatusColor(analysis.signal_status)}`;
      
#       document.getElementById('individual-price').textContent = formatCurrency(analysis.current_price);
#       document.getElementById('individual-strength').textContent = analysis.current_signal.toFixed(4);
#       document.getElementById('individual-volatility').textContent = `${analysis.current_volatility.toFixed(1)}%`;
      
#       // Additional metrics
#       document.getElementById('individual-trend').textContent = analysis.current_trend.toFixed(4);
#       document.getElementById('individual-beta').textContent = analysis.beta;
#       document.getElementById('individual-update').textContent = analysis.last_update;
      
#       // Strike analysis if available
#       if (analysis.strike !== undefined) {
#         document.getElementById('strike-price').textContent = formatCurrency(analysis.strike);
#         document.getElementById('strike-distance').textContent = `${analysis.distance_to_strike}%`;
#         document.getElementById('strike-analysis-text').textContent = analysis.strike_analysis || 'Análise não disponível';
#         document.getElementById('individual-strike-analysis').classList.remove('hidden');
#       } else {
#         document.getElementById('individual-strike-analysis').classList.add('hidden');
#       }
      
#       // Show results
#       document.getElementById('individual-results').classList.remove('hidden');
      
#       // NOVO: Criar gráfico com Chart.js baseado nos dados do ATSMOM
#       createATSMOMChart(data);
#       document.getElementById('plotly-chart-container').classList.remove('hidden');
#     }

#     // NOVA FUNÇÃO: Criar gráfico ATSMOM com Chart.js (igual ao Beta Regression)
#     function createATSMOMChart(data) {
#       try {
#         console.log('Criando gráfico ATSMOM com Chart.js');
        
#         const analysis = data.analysis_data;
        
#         // Preparar dados para Chart.js
#         let chartData;
        
#         if (data.raw_data && data.raw_data.dates && data.raw_data.prices) {
#           // Usar dados reais
#           chartData = {
#             labels: data.raw_data.dates,
#             prices: data.raw_data.prices,
#             signals: data.raw_data.signals || [],
#             trends: data.raw_data.trends || []
#           };
#         } else {
#           // Gerar dados de exemplo
#           const numPoints = 60;
#           const dates = [];
#           const prices = [];
#           const signals = [];
#           const trends = [];
          
#           const today = new Date();
#           let basePrice = analysis.current_price || 50;
          
#           for (let i = numPoints; i >= 0; i--) {
#             const date = new Date(today);
#             date.setDate(date.getDate() - i);
#             dates.push(date.toLocaleDateString('pt-BR'));
            
#             // Preço com movimento realista
#             const movement = Math.sin(i * 0.02) * 2 + (Math.random() - 0.5) * 1;
#             basePrice += movement * 0.3;
#             prices.push(Math.max(basePrice * 0.8, basePrice));
            
#             // Sinal ATSMOM (-3 a +3)
#             const signal = Math.sin(i * 0.03) * 2.5 + (Math.random() - 0.5) * 1;
#             signals.push(Math.max(-3, Math.min(3, signal)));
            
#             // Tendência
#             const trend = Math.sin(i * 0.025) * 1.8 + (Math.random() - 0.5) * 0.4;
#             trends.push(trend);
#           }
          
#           // Definir valores atuais
#           prices[prices.length - 1] = analysis.current_price;
#           signals[signals.length - 1] = analysis.current_signal;
#           trends[trends.length - 1] = analysis.current_trend;
          
#           chartData = { labels: dates, prices, signals, trends };
#         }
        
#         // Simular IBOV normalizado
#         const ibovPrices = chartData.prices.map((p, i) => p * (0.95 + Math.sin(i * 0.02) * 0.05));
#         const ibovSignals = chartData.signals.map(s => s * 0.8);
#         const ibovTrends = chartData.trends.map(t => t * 0.7);
        
#         // Limpar container e criar HTML igual ao Beta Regression
#         const chartContainer = document.getElementById('plotly-chart');
#         chartContainer.innerHTML = `
#           <!-- Gráfico Principal - Preços vs IBOV -->
#           <div class="mb-8">
#             <div class="beta-card p-6">
#               <h3 class="text-xl font-bold mb-4" style="color: #00FFAA;">
#                 <i class="fas fa-chart-line mr-2"></i>
#                 ${analysis.symbol} vs IBOV - Preços Normalizados
#               </h3>
#               <div class="mb-4 flex flex-wrap gap-4 text-sm">
#                 <div class="flex items-center gap-2">
#                   <div class="w-3 h-3 rounded-full" style="background-color: #00FFAA;"></div>
#                   <span>${analysis.symbol}</span>
#                 </div>
#                 <div class="flex items-center gap-2">
#                   <div class="w-3 h-3 rounded-full" style="background-color: #ffffff;"></div>
#                   <span>IBOV (normalizado)</span>
#                 </div>
#               </div>
#               <div style="position: relative; height: 300px; width: 100%;">
#                 <canvas id="atsmomPriceChart"></canvas>
#               </div>
#             </div>
#           </div>

#           <!-- Gráficos de Sinais -->
#           <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
#             <div class="beta-card p-6">
#               <h3 class="text-xl font-bold mb-4" style="color: #00BFFF;">
#                 <i class="fas fa-wave-square mr-2"></i>
#                 Força da Tendência (ATSMOM)
#               </h3>
#               <div class="mb-4 flex flex-wrap gap-4 text-sm">
#                 <div class="flex items-center gap-2">
#                   <div class="w-3 h-3 rounded-full" style="background-color: #00FFAA;"></div>
#                   <span>Tendência ${analysis.symbol}</span>
#                 </div>
#                 <div class="flex items-center gap-2">
#                   <div class="w-3 h-3 rounded-full" style="background-color: #ffffff;"></div>
#                   <span>Tendência IBOV</span>
#                 </div>
#               </div>
#               <div style="position: relative; height: 250px; width: 100%;">
#                 <canvas id="atsmomTrendChart"></canvas>
#               </div>
#             </div>
            
#             <div class="beta-card p-6">
#               <h3 class="text-xl font-bold mb-4" style="color: #9400D3;">
#                 <i class="fas fa-chart-area mr-2"></i>
#                 Sinal Ajustado pela Volatilidade
#               </h3>
#               <div class="mb-4 flex flex-wrap gap-4 text-sm">
#                 <div class="flex items-center gap-2">
#                   <div class="w-3 h-3 rounded-full" style="background-color: #00FFAA;"></div>
#                   <span>Sinal ${analysis.symbol}</span>
#                 </div>
#                 <div class="flex items-center gap-2">
#                   <div class="w-3 h-3 rounded-full" style="background-color: #ffffff;"></div>
#                   <span>Sinal IBOV</span>
#                 </div>
#               </div>
#               <div style="position: relative; height: 250px; width: 100%;">
#                 <canvas id="atsmomSignalChart"></canvas>
#               </div>
#             </div>
#           </div>
#         `;
        
#         // Configuração base para Chart.js (cyberpunk style)
#         const baseChartConfig = {
#           responsive: true,
#           maintainAspectRatio: false,
#           plugins: {
#             legend: {
#               labels: {
#                 color: '#ffffff',
#                 font: { size: 12 },
#                 usePointStyle: true
#               }
#             },
#             tooltip: {
#               backgroundColor: 'rgba(17, 17, 58, 0.9)',
#               titleColor: '#00FFAA',
#               bodyColor: '#ffffff',
#               borderColor: '#00FFAA',
#               borderWidth: 1
#             }
#           },
#           scales: {
#             x: {
#               ticks: { 
#                 color: '#ffffff',
#                 maxTicksLimit: 8
#               },
#               grid: { color: 'rgba(255, 255, 255, 0.1)' }
#             },
#             y: {
#               ticks: { color: '#ffffff' },
#               grid: { color: 'rgba(255, 255, 255, 0.1)' }
#             }
#           },
#           elements: {
#             point: { radius: 0 }
#           }
#         };
        
#         // 1. Gráfico de Preços
#         const priceCtx = document.getElementById('atsmomPriceChart').getContext('2d');
#         new Chart(priceCtx, {
#           type: 'line',
#           data: {
#             labels: chartData.labels,
#             datasets: [
#               {
#                 label: analysis.symbol,
#                 data: chartData.prices,
#                 borderColor: '#00FFAA',
#                 backgroundColor: 'rgba(0, 255, 170, 0.1)',
#                 borderWidth: 3,
#                 fill: false,
#                 tension: 0.1
#               },
#               {
#                 label: 'IBOV (normalizado)',
#                 data: ibovPrices,
#                 borderColor: '#ffffff',
#                 backgroundColor: 'rgba(255, 255, 255, 0.1)',
#                 borderWidth: 2,
#                 fill: false,
#                 tension: 0.1,
#                 borderDash: [5, 5]
#               }
#             ]
#           },
#           options: {
#             ...baseChartConfig,
#             scales: {
#               ...baseChartConfig.scales,
#               y: {
#                 ...baseChartConfig.scales.y,
#                 ticks: {
#                   color: '#ffffff',
#                   callback: function(value) {
#                     return 'R$ ' + value.toFixed(2);
#                   }
#                 }
#               }
#             }
#           }
#         });
        
#         // 2. Gráfico de Tendência
#         const trendCtx = document.getElementById('atsmomTrendChart').getContext('2d');
#         new Chart(trendCtx, {
#           type: 'line',
#           data: {
#             labels: chartData.labels,
#             datasets: [
#               {
#                 label: `Tendência ${analysis.symbol}`,
#                 data: chartData.trends,
#                 borderColor: '#00FFAA',
#                 backgroundColor: 'rgba(0, 255, 170, 0.1)',
#                 borderWidth: 2,
#                 fill: true,
#                 tension: 0.1
#               },
#               {
#                 label: 'Tendência IBOV',
#                 data: ibovTrends,
#                 borderColor: '#ffffff',
#                 backgroundColor: 'rgba(255, 255, 255, 0.05)',
#                 borderWidth: 2,
#                 fill: false,
#                 tension: 0.1,
#                 borderDash: [3, 3]
#               }
#             ]
#           },
#           options: baseChartConfig
#         });
        
#         // 3. Gráfico de Sinais
#         const signalCtx = document.getElementById('atsmomSignalChart').getContext('2d');
#         new Chart(signalCtx, {
#           type: 'line',
#           data: {
#             labels: chartData.labels,
#             datasets: [
#               {
#                 label: `Sinal ${analysis.symbol}`,
#                 data: chartData.signals,
#                 borderColor: '#00FFAA',
#                 backgroundColor: 'rgba(0, 255, 170, 0.1)',
#                 borderWidth: 2,
#                 fill: true,
#                 tension: 0.1
#               },
#               {
#                 label: 'Sinal IBOV',
#                 data: ibovSignals,
#                 borderColor: '#ffffff',
#                 backgroundColor: 'rgba(255, 255, 255, 0.05)',
#                 borderWidth: 1,
#                 fill: false,
#                 tension: 0.1,
#                 borderDash: [2, 2]
#               }
#             ]
#           },
#           options: {
#             ...baseChartConfig,
#             scales: {
#               ...baseChartConfig.scales,
#               y: {
#                 ...baseChartConfig.scales.y,
#                 min: -3,
#                 max: 3,
#                 ticks: {
#                   color: '#ffffff',
#                   stepSize: 0.5
#                 }
#               }
#             }
#           }
#         });
        
#         console.log('✅ Gráficos ATSMOM criados com sucesso usando Chart.js');
        
#       } catch (error) {
#         console.error('❌ Erro ao criar gráficos ATSMOM:', error);
#         document.getElementById('plotly-chart').innerHTML = `
#           <div style="color: white; text-align: center; padding: 50px;">
#             <i class="fas fa-exclamation-triangle" style="font-size: 48px; color: #ef4444; margin-bottom: 20px;"></i>
#             <h3>Erro ao carregar gráficos</h3>
#             <p>${error.message}</p>
#           </div>
#         `;
#       }
#     }

#     // Análise em Lote
#     async function analyzeBulk() {
#       const period = document.getElementById('bulk-period').value;
#       const symbolsInput = document.getElementById('bulk-symbols').value.trim();
#       const btn = document.getElementById('analyzeBulkBtn');

#       setLoading(btn, true);
#       hideAllResults();
#       showStatus('Executando análise em lote... Isso pode levar alguns minutos', 'info');

#       try {
#         const payload = { period: period };
#         if (symbolsInput) {
#           payload.symbols = symbolsInput.split(',').map(s => s.trim().toUpperCase());
#         }

#         const response = await fetch(`${API_BASE}/bulk_analyze`, {
#           method: 'POST',
#           headers: {
#             'Content-Type': 'application/json',
#           },
#           body: JSON.stringify(payload)
#         });

#         const data = await response.json();

#         if (data.success) {
#           displayBulkResults(data);
#           showStatus(`Análise em lote concluída! ${data.total_analyzed} ativos processados.`, 'success');
#         } else {
#           showStatus(data.error || 'Erro na análise em lote', 'error');
#         }
#       } catch (error) {
#         showStatus('Erro ao executar análise em lote', 'error');
#         console.error(error);
#       }

#       setLoading(btn, false);
#     }

#     // Display Bulk Results
#     function displayBulkResults(data) {
#       const compras = data.results.filter(r => r.signal_status === 'COMPRA').length;
#       const vendas = data.results.filter(r => r.signal_status === 'VENDA').length;
#       const neutros = data.results.filter(r => r.signal_status === 'NEUTRO').length;
      
#       const summaryHtml = `
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-2xl font-bold">${data.total_analyzed}</div>
#           <div class="text-sm text-gray-400">Total Analisado</div>
#         </div>
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-2xl font-bold text-green-400">${compras}</div>
#           <div class="text-sm text-gray-400">Sinais de Compra</div>
#         </div>
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-2xl font-bold text-red-400">${vendas}</div>
#           <div class="text-sm text-gray-400">Sinais de Venda</div>
#         </div>
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-2xl font-bold text-gray-400">${neutros}</div>
#           <div class="text-sm text-gray-400">Sinais Neutros</div>
#         </div>
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-2xl font-bold text-red-400">${data.total_errors}</div>
#           <div class="text-sm text-gray-400">Erros</div>
#         </div>
#       `;
      
#       document.getElementById('bulk-summary').innerHTML = summaryHtml;
      
#       const tbody = document.getElementById('bulk-table-body');
#       tbody.innerHTML = data.results.map(result => `
#         <tr class="border-b border-white border-opacity-10 hover:bg-white hover:bg-opacity-5 cursor-pointer" onclick="analyzeFromTable('${result.symbol}')">
#           <td class="py-3 px-4 font-bold">${result.symbol}</td>
#           <td class="py-3 px-4">${formatCurrency(result.current_price)}</td>
#           <td class="py-3 px-4">
#             <span class="px-2 py-1 rounded-full text-xs ${getStatusBadgeClass(result.signal_status)}">
#               ${result.signal_status}
#             </span>
#           </td>
#           <td class="py-3 px-4">${result.current_signal.toFixed(4)}</td>
#           <td class="py-3 px-4">${result.current_trend.toFixed(4)}</td>
#           <td class="py-3 px-4">${result.current_volatility.toFixed(1)}%</td>
#           <td class="py-3 px-4">${result.beta}</td>
#         </tr>
#       `).join('');
      
#       document.getElementById('bulk-results').classList.remove('hidden');
#     }

#     // Comparar Ativos
#     async function compareAssets() {
#       const symbol1 = document.getElementById('compare-symbol1').value.trim().toUpperCase();
#       const symbol2 = document.getElementById('compare-symbol2').value.trim().toUpperCase();
#       const period = document.getElementById('compare-period').value;
#       const btn = document.getElementById('compareBtn');

#       if (!symbol1 || !symbol2) {
#         showStatus('Digite ambos os códigos das ações', 'error');
#         return;
#       }

#       if (symbol1 === symbol2) {
#         showStatus('Os ativos devem ser diferentes', 'error');
#         return;
#       }

#       setLoading(btn, true);
#       hideAllResults();
#       showStatus('Comparando ativos... Isso pode levar alguns segundos', 'info');

#       try {
#         const response = await fetch(`${API_BASE}/compare`, {
#           method: 'POST',
#           headers: {
#             'Content-Type': 'application/json',
#           },
#           body: JSON.stringify({
#             symbol1: symbol1,
#             symbol2: symbol2,
#             period: period
#           })
#         });

#         const data = await response.json();

#         if (data.success) {
#           displayComparisonResults(data);
#           showStatus('Comparação concluída com sucesso!', 'success');
#         } else {
#           showStatus(data.error || 'Erro na comparação', 'error');
#         }
#       } catch (error) {
#         showStatus('Erro ao executar comparação', 'error');
#         console.error(error);
#       }

#       setLoading(btn, false);
#     }

#     // Display Comparison Results
#     function displayComparisonResults(data) {
#       const comparison = data.comparison;
#       const summary = comparison.comparison_summary;
      
#       const summaryHtml = `
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-lg font-bold text-purple-400">${summary.stronger_signal}</div>
#           <div class="text-sm text-gray-400">Sinal Mais Forte</div>
#         </div>
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-lg font-bold text-orange-400">${summary.higher_volatility}</div>
#           <div class="text-sm text-gray-400">Maior Volatilidade</div>
#         </div>
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-lg font-bold text-blue-400">${summary.higher_beta}</div>
#           <div class="text-sm text-gray-400">Maior Beta</div>
#         </div>
#       `;
      
#       document.getElementById('comparison-summary').innerHTML = summaryHtml;
#       document.getElementById('compare-asset1').innerHTML = createAssetCard(comparison.symbol1);
#       document.getElementById('compare-asset2').innerHTML = createAssetCard(comparison.symbol2);
#       document.getElementById('compare-results').classList.remove('hidden');
#     }

#     function createAssetCard(assetData) {
#       const data = assetData.data;
#       return `
#         <h3 class="text-xl font-bold mb-4 text-center">${assetData.symbol}</h3>
#         <div class="space-y-3">
#           <div class="bg-white bg-opacity-5 p-3 rounded-lg flex justify-between">
#             <span class="text-gray-400">Preço:</span>
#             <span class="font-semibold">${formatCurrency(data.current_price)}</span>
#           </div>
#           <div class="bg-white bg-opacity-5 p-3 rounded-lg flex justify-between">
#             <span class="text-gray-400">Sinal:</span>
#             <span class="font-semibold ${getStatusColor(data.signal_status)}">${data.signal_status}</span>
#           </div>
#           <div class="bg-white bg-opacity-5 p-3 rounded-lg flex justify-between">
#             <span class="text-gray-400">Força:</span>
#             <span class="font-semibold">${data.current_signal.toFixed(4)}</span>
#           </div>
#           <div class="bg-white bg-opacity-5 p-3 rounded-lg flex justify-between">
#             <span class="text-gray-400">Tendência:</span>
#             <span class="font-semibold">${data.current_trend.toFixed(4)}</span>
#           </div>
#           <div class="bg-white bg-opacity-5 p-3 rounded-lg flex justify-between">
#             <span class="text-gray-400">Volatilidade:</span>
#             <span class="font-semibold">${data.current_volatility.toFixed(1)}%</span>
#           </div>
#           <div class="bg-white bg-opacity-5 p-3 rounded-lg flex justify-between">
#             <span class="text-gray-400">Beta:</span>
#             <span class="font-semibold">${data.beta}</span>
#           </div>
#         </div>
#       `;
#     }

#     // Visão Geral do Mercado
#     async function getMarketOverview() {
#       const period = document.getElementById('overview-period').value;
#       const btn = document.getElementById('overviewBtn');

#       setLoading(btn, true);
#       hideAllResults();
#       showStatus('Carregando visão geral do mercado...', 'info');

#       try {
#         const response = await fetch(`${API_BASE}/market_overview?period=${period}`);
#         const data = await response.json();

#         if (data.success) {
#           displayOverviewResults(data);
#           showStatus('Visão geral carregada com sucesso!', 'success');
#         } else {
#           showStatus(data.error || 'Erro ao carregar visão geral', 'error');
#         }
#       } catch (error) {
#         showStatus('Erro ao carregar visão geral', 'error');
#         console.error(error);
#       }

#       setLoading(btn, false);
#     }

#     function displayOverviewResults(data) {
#       const overview = data.overview;
      
#       const statsHtml = `
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-xl font-bold">${overview.total_assets}</div>
#           <div class="text-xs text-gray-400">Total</div>
#         </div>
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-xl font-bold text-green-400">${overview.buy_signals}</div>
#           <div class="text-xs text-gray-400">Compra</div>
#         </div>
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-xl font-bold text-red-400">${overview.sell_signals}</div>
#           <div class="text-xs text-gray-400">Venda</div>
#         </div>
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-xl font-bold text-gray-400">${overview.neutral_signals}</div>
#           <div class="text-xs text-gray-400">Neutro</div>
#         </div>
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-xl font-bold">${overview.average_volatility}%</div>
#           <div class="text-xs text-gray-400">Vol. Média</div>
#         </div>
#         <div class="bg-white bg-opacity-5 p-4 rounded-lg text-center">
#           <div class="text-xl font-bold ${getStatusColor(overview.market_sentiment)}">${overview.market_sentiment}</div>
#           <div class="text-xs text-gray-400">Sentimento</div>
#         </div>
#       `;
      
#       document.getElementById('overview-stats').innerHTML = statsHtml;
      
#       const tbody = document.getElementById('overview-table-body');
#       tbody.innerHTML = data.assets.map(asset => `
#         <tr class="border-b border-white border-opacity-10 hover:bg-white hover:bg-opacity-5 cursor-pointer" onclick="analyzeFromTable('${asset.symbol}')">
#           <td class="py-3 px-4 font-bold">${asset.symbol}</td>
#           <td class="py-3 px-4">${formatCurrency(asset.price)}</td>
#           <td class="py-3 px-4">
#             <span class="px-2 py-1 rounded-full text-xs ${getStatusBadgeClass(asset.signal)}">
#               ${asset.signal}
#             </span>
#           </td>
#           <td class="py-3 px-4">${asset.signal_strength.toFixed(4)}</td>
#           <td class="py-3 px-4">${asset.volatility.toFixed(1)}%</td>
#           <td class="py-3 px-4">${asset.beta}</td>
#         </tr>
#       `).join('');
      
#       document.getElementById('overview-results').classList.remove('hidden');
#     }

#     function getStatusBadgeClass(status) {
#       switch(status) {
#         case 'COMPRA': return 'bg-green-600 bg-opacity-20 text-green-400 border border-green-500 border-opacity-30';
#         case 'VENDA': return 'bg-red-600 bg-opacity-20 text-red-400 border border-red-500 border-opacity-30';
#         default: return 'bg-gray-600 bg-opacity-20 text-gray-400 border border-gray-500 border-opacity-30';
#       }
#     }

#     function analyzeFromTable(symbol) {
#       document.querySelector('[data-tab="individual"]').click();
#       document.getElementById('individual-symbol').value = symbol;
#       analyzeIndividual();
#     }

#     // Event Listeners
#     document.getElementById('analyzeIndividualBtn').addEventListener('click', analyzeIndividual);
#     document.getElementById('analyzeBulkBtn').addEventListener('click', analyzeBulk);
#     document.getElementById('compareBtn').addEventListener('click', compareAssets);
#     document.getElementById('overviewBtn').addEventListener('click', getMarketOverview);

#     document.getElementById('individual-symbol').addEventListener('keypress', (e) => {
#       if (e.key === 'Enter') analyzeIndividual();
#     });

#     document.getElementById('compare-symbol1').addEventListener('keypress', (e) => {
#       if (e.key === 'Enter') compareAssets();
#     });

#     document.getElementById('compare-symbol2').addEventListener('keypress', (e) => {
#       if (e.key === 'Enter') compareAssets();
#     });

#     // Health Check
#     async function checkHealth() {
#       try {
#         const response = await fetch(`${API_BASE}/health`);
#         const data = await response.json();
        
#         if (data.status === 'OK') {
#           console.log('✅ Serviço ATSMOM funcionando:', data.message);
#         } else {
#           console.warn('⚠️ Serviço com problemas:', data.message);
#         }
#       } catch (error) {
#         console.error('❌ Erro ao verificar saúde do serviço:', error);
#       }
#     }

#     // Initialize
#     document.addEventListener('DOMContentLoaded', function() {
#       checkHealth();
#       showStatus('ATSMOM Analytics carregado! Selecione uma opção de análise para começar.', 'info');
#     });
#   </script>
# </body>
# </html>