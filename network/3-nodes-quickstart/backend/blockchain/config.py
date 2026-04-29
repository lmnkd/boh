from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import os
import json
import time
from pathlib import Path
from typing import Optional

# =========================
# 📂 CONFIGURAZIONE E CARICAMENTO .env

def find_dotenv_path() -> Optional[Path]:
    current = Path(__file__).resolve()
    for parent in [current.parent] + list(current.parents):
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return None


def load_dotenv(dotenv_path: Optional[Path] = None, override: bool = False) -> None:
    if dotenv_path is None:
        dotenv_path = find_dotenv_path()
    if dotenv_path is None:
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if override or key not in os.environ:
            os.environ[key] = value


# Carica automaticamente .env dalla directory di progetto o da una directory superiore.
load_dotenv()

# =========================
# 🌐 CONNECTION BLOCKCHAIN
# =========================

WEB3_PROVIDER = os.getenv("WEB3_PROVIDER", "http://127.0.0.1:8545")

# Retry connection with exponential backoff
max_retries = 30
retry_delay = 2
w3 = None

for attempt in range(max_retries):
    try:
        w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER))
        # Aggiungi middleware PoA per Quorum/RAFT
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        if w3.is_connected():
            print(f"✅ Blockchain connessa: {WEB3_PROVIDER}")
            break
        else:
            print(f"⏳ Tentativo {attempt + 1}/{max_retries}: Connessione non riuscita. Riprovo tra {retry_delay}s...")
            time.sleep(retry_delay)
    except Exception as e:
        print(f"⏳ Tentativo {attempt + 1}/{max_retries}: Errore di connessione - {str(e)}. Riprovo tra {retry_delay}s...")
        time.sleep(retry_delay)

if w3 is None or not w3.is_connected():
    raise Exception(f"❌ Blockchain non connessa a {WEB3_PROVIDER} dopo {max_retries} tentativi")

print("✅ Blockchain connessa:", w3.is_connected())


# =========================
# 🔐 ACCOUNT BACKEND
# =========================

ACCOUNT = os.getenv("BLOCKCHAIN_ACCOUNT")

if not ACCOUNT:
    raise Exception("❌ BLOCKCHAIN_ACCOUNT non impostato nelle variabili d'ambiente")

PRIVATE_KEY = None  # Quorum RAFT non la richiede


# =========================
# 📜 CONTRACT ADDRESS (dinamico)
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADDRESS_FILE = os.path.join(BASE_DIR, "address.json")


def get_contract_address():
    if not os.path.exists(ADDRESS_FILE):
        return None

    try:
        with open(ADDRESS_FILE, "r") as f:
            data = json.load(f)
            return data.get("address")
    except Exception as e:
        print("⚠️ Errore lettura address.json:", e)
        return None


CONTRACT_ADDRESS = get_contract_address()


# =========================
# ⚠️ VALIDAZIONE ADDRESS
# =========================

if CONTRACT_ADDRESS:
    CONTRACT_ADDRESS = Web3.to_checksum_address(CONTRACT_ADDRESS)
    print("📜 Contract address:", CONTRACT_ADDRESS)
else:
    print("⚠️ Nessun contratto deployato ancora")