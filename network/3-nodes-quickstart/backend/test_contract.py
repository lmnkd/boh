#!/usr/bin/env python3
"""
Script per diagnosticare problemi di contratto e deployment
"""
import json
from pathlib import Path
from blockchain.config import w3, ACCOUNT, get_contract_address
from blockchain.contract import get_contract
from web3 import Web3

print("=" * 70)
print(" DIAGNOSTICA CONTRATTO E DEPLOYMENT")
print("=" * 70)

# 1. Verifica address.json
print("\n VERIFICA ADDRESS.JSON")
address_file = Path(__file__).resolve().parent / "blockchain" / "address.json"
print(f"   Percorso: {address_file}")

if address_file.exists():
    with open(address_file) as f:
        data = json.load(f)
        contract_address = data.get("address")
    print(f"   File trovato")
    print(f"    Indirizzo: {contract_address}")
    
    # Converti a checksum
    try:
        contract_address_checksum = Web3.to_checksum_address(contract_address)
        print(f"    Checksum: {contract_address_checksum}")
    except Exception as e:
        print(f"    Errore checksum: {e}")
        contract_address = None
else:
    print(f"    File NON trovato!")
    contract_address = None

# 2. Verifica se il contratto esiste sulla chain
print("\n VERIFICA CONTRATTO SULLA CHAIN")
if contract_address:
    try:
        code = w3.eth.get_code(contract_address)
        print(f"    Contratto trovato!")
        print(f"    Code size: {len(code)} bytes")
        
        if len(code) <= 2:  # '0x' = nessun codice
            print(f"    WARNING: Nessun bytecode all'indirizzo!")
            print(f"      L'indirizzo esiste ma non è un contratto!")
        else:
            print(f"    Bytecode presente")
    except Exception as e:
        print(f"   Errore verifica codice: {e}")
else:
    print(f"    Nessun indirizzo da verificare")

# 3. Verifica ABI
print("\n VERIFICA ABI")
abi_file = Path(__file__).resolve().parent / "blockchain" / "abi.json"
print(f"   Percorso: {abi_file}")

if abi_file.exists():
    with open(abi_file) as f:
        abi = json.load(f)
    print(f"   File trovato")
    print(f"   Funzioni ABI: {len([x for x in abi if x.get('type') == 'function'])}")
    print(f"   Eventi ABI: {len([x for x in abi if x.get('type') == 'event'])}")
    
    # Cerca submitVisit
    has_submit = any(x.get('name') == 'submitVisit' for x in abi if x.get('type') == 'function')
    has_confirm = any(x.get('name') == 'confirmVisit' for x in abi if x.get('type') == 'function')
    has_event = any(x.get('name') == 'VisitSubmitted' for x in abi if x.get('type') == 'event')
    
    print(f"   {'✅' if has_submit else '❌'} submitVisit: {has_submit}")
    print(f"   {'✅' if has_confirm else '❌'} confirmVisit: {has_confirm}")
    print(f"   {'✅' if has_event else '❌'} VisitSubmitted event: {has_event}")
else:
    print(f"   ❌ File NON trovato!")

# 4. Prova a caricare il contratto
print("\n VERIFICA CARICAMENTO CONTRATTO")
try:
    contract = get_contract()
    print(f"    Contratto caricato!")
    print(f"    Address: {contract.address}")
    
    # Prova a leggere una funzione
    try:
        visit_count = contract.functions.visitCount().call()
        print(f"    Funzione visitCount() callable: {visit_count}")
    except Exception as e:
        print(f"    Errore chiamata visitCount(): {e}")
    
except Exception as e:
    print(f"    Errore caricamento contratto: {e}")

# 5. Verifica account
print("\n VERIFICA ACCOUNT")
print(f"    Account: {ACCOUNT}")
try:
    account_checksum = Web3.to_checksum_address(ACCOUNT)
    balance = w3.eth.get_balance(account_checksum)
    balance_eth = w3.from_wei(balance, 'ether')
    print(f"   Saldo: {balance_eth} ETH")
    
    if balance == 0:
        print(f"    WARNING: Saldo è 0!")
except Exception as e:
    print(f"    Errore verifica account: {e}")

# 6. Verifica chain
print("\n VERIFICA CHAIN")
try:
    block_number = w3.eth.block_number
    chain_id = w3.eth.chain_id
    gas_price = w3.eth.gas_price
    
    print(f"    Block number: {block_number}")
    print(f"    Chain ID: {chain_id}")
    print(f"    Gas price: {w3.from_wei(gas_price, 'gwei')} Gwei")
except Exception as e:
    print(f"    Errore verifica chain: {e}")

print("\n" + "=" * 70)
print(" DIAGNOSTICA COMPLETATA")
print("=" * 70)
