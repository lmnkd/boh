#!/usr/bin/env python3
"""
Script per testare se l'account BLOCKCHAIN_ACCOUNT può fare transazioni
"""
from blockchain.config import w3, ACCOUNT
from web3 import Web3

print("=" * 60)
print(" TEST ACCOUNT E BLOCKCHAIN")
print("=" * 60)

# 1. Verifica connessione
print(f"\nConnessione blockchain: {w3.is_connected()}")
print(f"   Provider: {w3.provider}")

# 2. Verifica account
print(f"\nAccount configurato: {ACCOUNT}")
account_checksum = Web3.to_checksum_address(ACCOUNT)
print(f"   Checksum: {account_checksum}")

# 3. Verifica saldo
try:
    balance = w3.eth.get_balance(account_checksum)
    balance_eth = w3.from_wei(balance, 'ether')
    print(f"\n Saldo: {balance_eth} ETH ({balance} Wei)")
    if balance == 0:
        print("   WARNING: Saldo è 0! Nessuna transazione possibile!")
    else:
        print("    OK: L'account ha fondi")
except Exception as e:
    print(f"    Errore lettura saldo: {e}")

# 4. Verifica nonce
try:
    nonce = w3.eth.get_transaction_count(account_checksum)
    print(f"\n Nonce: {nonce}")
    print(f"    OK: Account può inviare transazioni")
except Exception as e:
    print(f"    Errore lettura nonce: {e}")

# 5. Verifica gas price
try:
    gas_price = w3.eth.gas_price
    gas_price_gwei = w3.from_wei(gas_price, 'gwei')
    print(f"\n Gas price: {gas_price_gwei} Gwei ({gas_price} Wei)")
except Exception as e:
    print(f"    Errore lettura gas price: {e}")

# 6. Verifica chain ID
try:
    chain_id = w3.eth.chain_id
    print(f"\n Chain ID: {chain_id}")
except Exception as e:
    print(f"    Errore lettura chain ID: {e}")

# 7. Lista account disponibili nel nodo
try:
    accounts = w3.eth.accounts
    print(f"\n Account disponibili nel nodo: {len(accounts)}")
    for i, acc in enumerate(accounts[:5]):  # Mostra i primi 5
        print(f"   [{i}] {acc}")
    if len(accounts) > 5:
        print(f"   ... e altri {len(accounts) - 5}")
    
    if account_checksum in accounts:
        print(f"\n L'account {ACCOUNT} È DISPONIBILE nel nodo")
    else:
        print(f"\n L'account {ACCOUNT} NON È DISPONIBILE nel nodo!")
        print(f"   Questo potrebbe causare errori nelle transazioni!")
except Exception as e:
    print(f"    Errore lettura account: {e}")

print("\n" + "=" * 60)
print(" TEST COMPLETATO")
print("=" * 60)

print("Accounts:", w3.eth.accounts)
