from eth_account import Account
from database import db, User


def create_user(email, password, role):
    # Genera wallet Ethereum automaticamente
    wallet = Account.create()

    user = User(
        email=email,
        role=role,
        wallet_address=wallet.address,
        private_key=wallet.key.hex()  # salva la chiave privata
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user