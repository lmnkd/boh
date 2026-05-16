import hashlib
from datetime import datetime
from flask import Blueprint, jsonify, request
from eth_account import Account
from database.database import db, User, Patient

api = Blueprint("user_api", __name__)

def create_user(email, password, role):
    """
    Funzione helper condivisa. Genera automaticamente il wallet 
    e prepara l'istanza User compilando l'ID senza chiudere la transazione.
    """
    wallet = Account.create()

    user = User(
        email=email,
        role=role,
        wallet_address=wallet.address,
        private_key=wallet.key.hex()
    )
    user.set_password(password)
    
    db.session.add(user)
    db.session.flush()  # Genera l'ID utente per le tabelle collegate (Patient/Doctor)
    return user

@api.route("/register-patient", methods=["POST"])
def register_patient():
    data = request.get_json() or {}
    
    nome = data.get("nome")
    cognome = data.get("cognome")
    data_nascita_str = data.get("data_nascita")
    email = data.get("email")
    password = data.get("password")
    role = "PATIENT"

    if not nome or not cognome or not data_nascita_str or not email or not password:
        return jsonify({"error": "Tutti i campi sono obbligatori"}), 400

    try:
        data_nascita = datetime.strptime(data_nascita_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Formato data di nascita non valido"}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "Un utente con questa email è già registrato"}), 400

    try:
        # Usa l'helper condiviso appena ripristinato
        user = create_user(email, password, role)

        # Generazione del patient_hash unico a 66 caratteri
        seed_string = f"{email}-{datetime.utcnow().timestamp()}"
        sha256_hash = hashlib.sha256(seed_string.encode()).hexdigest()
        patient_hash = "0x" + sha256_hash

        patient = Patient(
            user_id=user.id,
            nome=nome,
            cognome=cognome,
            data_nascita=data_nascita,
            patient_hash=patient_hash
        )
        
        db.session.add(patient)
        db.session.commit()  # Salva definitivamente sia l'User che il Patient

        return jsonify({
            "status": "SUCCESS",
            "wallet_address": user.wallet_address
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Errore durante la registrazione del paziente: {str(e)}"}), 500