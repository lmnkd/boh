import json
import sys
from pathlib import Path

# Aggiungi la directory padre al path per permettere l'import da qualsiasi directory
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from blockchain.config import w3, get_contract_address

with open(Path(__file__).resolve().parent / "abi.json") as f:
    abi = json.load(f)


def get_contract():
    address = get_contract_address()
    

    if not address:
        raise Exception("❌ Contratto non ancora deployato")

    return w3.eth.contract(
        address=address,
        abi=abi
    )