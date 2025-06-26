# rollback.py - RESTAURAR ESTADO ANTERIOR
import shutil
import os
import glob

def rollback():
    print("🔄 EXECUTANDO ROLLBACK")
    
    # Encontrar backup mais recente
    backups = glob.glob("backup_*")
    if not backups:
        print("❌ Nenhum backup encontrado")
        return False
    
    latest_backup = max(backups)
    print(f"📁 Usando backup: {latest_backup}")
    
    files = ["main.py", "mercadopago_routes.py", "checkout_mercadopago.py"]
    
    for file in files:
        backup_file = f"{latest_backup}/{file}"
        if os.path.exists(backup_file):
            shutil.copy2(backup_file, file)
            print(f"✅ Restaurado: {file}")
    
    print("🎉 Rollback concluído!")

if __name__ == "__main__":
    rollback()
