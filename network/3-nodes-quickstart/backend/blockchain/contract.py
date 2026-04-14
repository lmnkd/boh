import json
from blockchain.config import w3

CONTRACT_ADDRESS = "INSERISCI_ADDRESS_DEPLOY"

with open("blockchain/abi.json") as f:
    abi = json.load(f)

contract = w3.eth.contract(
    address=CONTRACT_ADDRESS,
    abi=abi
)