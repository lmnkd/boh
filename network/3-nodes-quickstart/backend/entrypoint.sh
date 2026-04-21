#!/bin/bash
set -e

# Carica le variabili d'ambiente da .env (se esiste nel parent)
if [ -f "/home/app/.env" ]; then
    export $(cat /home/app/.env | xargs)
elif [ -f "/.env" ]; then
    export $(cat /.env | xargs)
fi

echo "🚀 Avviamento backend..."

# Aspetta che i nodi Quorum siano pronti
echo "⏳ Aspettando che Quorum sia pronto..."
for i in {1..60}; do
    if python -c "
import sys
sys.path.insert(0, '/home/app')
from blockchain.config import w3
print('✅ Quorum pronto' if w3.is_connected() else '❌ Non connesso')
" 2>/dev/null; then
        echo "✅ Quorum è pronto!"
        break
    fi
    echo "Tentativo $i/60..."
    sleep 2
done

# Aspetta che PostgreSQL sia pronto
echo "⏳ Aspettando che PostgreSQL sia pronto..."
for i in {1..60}; do
    if python -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='postgres',
        database='quorumdb',
        user='quorum',
        password='quorumpass'
    )
    conn.close()
    print('✅ PostgreSQL pronto')
except:
    print('❌ PostgreSQL non pronto')
" 2>/dev/null | grep -q "pronto"; then
        echo "✅ PostgreSQL è pronto!"
        break
    fi
    echo "Tentativo $i/60..."
    sleep 2
done

# Deploy del contratto se non esiste
echo "📜 Verificando se il contratto è deployato..."
if python -c "
import sys, json
from pathlib import Path
sys.path.insert(0, '/home/app')
address_file = Path('/home/app/blockchain/address.json')
if address_file.exists():
    with open(address_file) as f:
        data = json.load(f)
        if data.get('address'):
            print(f'✅ Contratto già deployato: {data[\"address\"]}')
            sys.exit(0)
print('❌ Non deployato')
sys.exit(1)
" 2>/dev/null; then
    echo "Contratto già presente, procedendo..."
else
    echo "📝 Deployando il contratto..."
    cd /home/app/blockchain
    python deploy.py || echo "⚠️ Deploy fallito, continuando comunque..."
fi

# Avvia Flask
echo "🎯 Avviando Flask..."
cd /home/app
python app.py
