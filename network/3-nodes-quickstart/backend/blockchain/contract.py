import json
from blockchain.config import w3, get_contract_address

with open("blockchain/abi.json") as f:
    abi = json.load(f)


def get_contract():
    address = get_contract_address()

    if not address:
        raise Exception("❌ Contratto non ancora deployato")

    return w3.eth.contract(
        address=address,
        abi=abi
    )