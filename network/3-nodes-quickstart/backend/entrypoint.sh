#!/bin/bash
set -e

export PYTHONUNBUFFERED=1

echo "Avviamento backend..."

# =========================
# ENV
# =========================
if [ -f "/home/app/.env" ]; then
    export $(cat /home/app/.env | xargs)
elif [ -f "/.env" ]; then
    export $(cat /.env | xargs)
fi

# =========================
# QUORUM CHECK
# =========================
echo "Aspettando che Quorum sia pronto..."

for i in {1..60}; do
    if python -c "
from blockchain.config import w3
exit(0 if w3.is_connected() else 1)
" 2>/dev/null; then
        echo " Quorum è pronto!"
        break
    fi

    echo "Tentativo $i/60..."
    sleep 2
done

# =========================
# POSTGRES CHECK
# =========================
echo " Aspettando PostgreSQL..."

for i in {1..60}; do
    if python -c "
import psycopg2
conn = psycopg2.connect(
    host='postgres',
    database='quorumdb',
    user='quorum',
    password='quorumpass'
)
conn.close()
" 2>/dev/null; then
        echo "PostgreSQL pronto!"
        break
    fi

    echo "Tentativo $i/60..."
    sleep 2
done

# =========================
# FORCE DEPLOY
# =========================
echo "Deploy contratto (FORZATO)..."

cd /home/app/blockchain

python -u deploy.py

echo " Deploy completato"

# =========================
# FLASK START
# =========================
echo " Avviando Flask..."

cd /home/app
python -u app.py