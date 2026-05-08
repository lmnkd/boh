from eth_account import Account
import os

path = "qdata/dd1/keystore/key"

print("Esiste?", os.path.exists(path))

with open(path) as f:
    encrypted = f.read()

print("File letto.")

try:
    pk = Account.decrypt(encrypted, "")
    print("PRIVATE KEY:", pk.hex())

except Exception as e:
    print("Errore:", repr(e))

acct = Account.from_key(
    "e6181caaffff94a09d7e332fc8da9884d99902c7874eb74354bdcadf411929f1"
)

print(acct.address)