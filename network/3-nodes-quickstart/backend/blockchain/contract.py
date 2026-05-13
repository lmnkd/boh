import json
import sys
from pathlib import Path

from blockchain.config import w3, get_contract_address

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# ✅ FIX: estrai SOLO ABI
abi_path = Path(__file__).resolve().parent / "abi.json"

with open(abi_path) as f:
    full_json = json.load(f)
    abi = full_json["abi"] if "abi" in full_json else full_json


def get_contract():
    address = get_contract_address()
    print("ABI LOADED:", len(abi))
    print("EVENTS IN ABI:", [item.get("name") for item in abi if item.get("type") == "event"])

    if not address:
        raise Exception("❌ Contratto non ancora deployato")

    return w3.eth.contract(
        address=address,
        abi=abi
    )