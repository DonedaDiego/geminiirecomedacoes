import os

def listar_pastas(caminho='.', nivel=0, max_nivel=2):
    if nivel > max_nivel:
        return
    for item in os.listdir(caminho):
        if item in ['venv', '__pycache__', 'node_modules']:
            continue
        caminho_item = os.path.join(caminho, item)
        print('│   ' * nivel + '├── ' + item)
        if os.path.isdir(caminho_item):
            listar_pastas(caminho_item, nivel + 1, max_nivel)

listar_pastas('.', 0, 2)
