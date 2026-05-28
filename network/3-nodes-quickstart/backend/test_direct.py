#!/usr/bin/env python3
"""Test direct contract call"""
from blockchain.config import w3, ACCOUNT
from blockchain.contract import get_contract
from web3 import Web3

print("=" * 60)
print(" TEST DIRETTO DEL CONTRATTO")
print("=" * 60)

try:
    contract = get_contract()
    print(f"\n Contratto caricato: {contract.address}")
    
    # Prova a leggere visitCount
    print(f"\n Tentativo 1: Leggi visitCount()")
    try:
        visit_count = contract.functions.visitCount().call()
        print(f"    visitCount = {visit_count}")
    except Exception as e:
        print(f"    Errore: {e}")
    
    # Prova a leggere un visit
    print(f"\n Tentativo 2: Leggi recordCount()")
    try:
        record_count = contract.functions.recordCount().call()
        print(f"    recordCount = {record_count}")
    except Exception as e:
        print(f"    Errore: {e}")
    
    # Prova a leggere il owner (DEFAULT_ADMIN_ROLE)
    print(f"\n Tentativo 3: Verifica ruoli")
    try:
        default_admin = contract.functions.DEFAULT_ADMIN_ROLE().call()
        print(f"    DEFAULT_ADMIN_ROLE = {default_admin.hex()}")
    except Exception as e:
        print(f"    Errore: {e}")
    
    # Prova una transazione di test: addDoctor
    print(f"\n Tentativo 4: Transazione di test - addDoctor")
    try:
        test_addr = Web3.to_checksum_address("0x1111111111111111111111111111111111111111")
        account_checksum = Web3.to_checksum_address(ACCOUNT)
        
        tx_hash = contract.functions.addDoctor(test_addr).transact({
            "from": account_checksum,
            "gas": 5_000_000,
            "chainId": 10
        })
        print(f"    Tx inviata: {tx_hash.hex()}")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        print(f"    Tx confermata nel blocco {receipt.blockNumber}")
        print(f"    Gas usato: {receipt.gasUsed}")
        
        if receipt.status == 0:
            print(f"    Transazione fallita (status=0)")
        else:
            print(f"    Transazione riuscita (status=1)")
    except Exception as e:
        print(f"    Errore: {e}")
    
except Exception as e:
    print(f" Errore: {e}")

print("\n" + "=" * 60)
