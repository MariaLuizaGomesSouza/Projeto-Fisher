import os
import datetime

def realizar_backup():
    data = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = f"banco/backups/fisher_backup_{data}.sql"
    
    if not os.path.exists('banco/backups'):
        os.makedirs('banco/backups')
        
    cmd = (
        f'& "C:\\Program Files\\MySQL\\MySQL Server 8.0\\bin\\mysqldump.exe" '
        f'-u fisher_admin -pSenhaAdminSegura123! --no-tablespaces '
        f'--routines --triggers fisher > {destino}'
    )
    
    os.system(f'powershell -Command "{cmd}"')
    print(f"Backup realizado em: {destino}")

if __name__ == '__main__':
    realizar_backup()