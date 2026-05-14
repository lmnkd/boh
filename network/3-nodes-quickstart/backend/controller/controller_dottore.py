from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError
from web3 import Web3
from eth_account.messages import encode_defunct

from blockchain.config import w3
from blockchain.contract import get_contract
from database.database import db, Doctor, User
from controller.controller_user import create_user


api = Blueprint("dottore_api", __name__)


# ----------------------------
# UTILS
# ----------------------------

def normalize_address(addr):
    if not addr:
        return None
    return Web3.to_checksum_address(addr)


def tx_params(from_address=None):
    params = {
        "from": normalize_address(from_address) if from_address else normalize_address(w3.eth.accounts[0]),
        "gas": 5_000_000,
    }
    if w3.eth.chain_id is not None:
        params["chainId"] = w3.eth.chain_id
    return params


# ----------------------------
# GET ALL DOCTORS
# ----------------------------

@api.route("/doctors", methods=["GET"])
def list_doctors():

    doctors = Doctor.query.all()

    result = []

    for d in doctors:
        result.append({
            "id": d.id,
            "nome": d.nome,
            "cognome": d.cognome,
            "email": d.user.email if d.user else None,
            "wallet_address": d.user.wallet_address if d.user else None,
            "role": d.user.role if d.user else None
        })

    return jsonify(result), 200


# ----------------------------
# GET DOCTOR BY ID
# ----------------------------

@api.route("/doctors/<int:doctor_id>", methods=["GET"])
def get_doctor(doctor_id):
    doctor = Doctor.query.get(doctor_id)

    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404

    return jsonify(
        model_to_dict(doctor, ["id", "wallet_address", "nome", "cognome"])
    )


# ----------------------------
# CREATE DOCTOR
# ----------------------------

@api.route("/register-doctor", methods=["POST"])
def register_doctor():

    print("===== START register_doctor =====", flush=True)

    try:

        # -------------------------
        # LETTURA JSON
        # -------------------------
        data = request.get_json()

        print("JSON ricevuto", flush=True)
        print(f"Dati ricevuti: {data}", flush=True)

        # -------------------------
        # 1. CREA USER
        # -------------------------

        user = create_user(
            email=data["email"],
            password=data["password"],
            role="DOCTOR"
        )
        
        print("Oggetto User creato", flush=True)

        print(f"User salvato con id {user.id} e wallet address {user.wallet_address}", flush=True)

        # -------------------------
        # 2. CREA DOCTOR
        # -------------------------
        doctor = Doctor(
            user_id=user.id,
            nome=data["nome"],
            cognome=data["cognome"],
        )

        db.session.add(doctor)
        db.session.commit()

        print(f"Doctor salvato con id {doctor.id} e wallet address {user.wallet_address}", flush=True)

        # =========================================================
        # 3. ASSEGNA RUOLO DOCTOR NEL CONTRATTO
        # =========================================================

        print("PRIMA TRY DOCTOR", flush=True)

        try:

            print("ENTRATO TRY DOCTOR", flush=True)

            contract = get_contract()

            print("Contract ottenuto", flush=True)

            normalized_address = normalize_address(
                user.wallet_address
            )

            print(
                f"Address normalizzato: {normalized_address}",
                flush=True
            )

            params = tx_params()

            print(f"TX PARAMS: {params}", flush=True)

            tx_hash = contract.functions.addDoctor(
                normalized_address
            ).transact(params)

            print(
                f"TX HASH DOCTOR: {tx_hash.hex()}",
                flush=True
            )

            receipt = w3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=60
            )

            print(
                f"TRANSACTION DOCTOR MINATA: {receipt}",
                flush=True
            )

        except Exception as e:

            print(
                f"ERRORE addDoctor: {str(e)}",
                flush=True
            )

        print("DOPO TRY DOCTOR", flush=True)

        # =========================================================
        # 4. ASSEGNA RUOLO VALIDATOR NEL CONTRATTO
        # =========================================================

        print("PRIMA TRY VALIDATOR", flush=True)

        try:

            print("ENTRATO TRY VALIDATOR", flush=True)

            contract = get_contract()

            normalized_address = normalize_address(
                user.wallet_address
            )

            tx_hash = contract.functions.addValidator(
                normalized_address
            ).transact(tx_params())

            print(
                f"TX HASH VALIDATOR: {tx_hash.hex()}",
                flush=True
            )

            receipt = w3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=60
            )

            print(
                f"TRANSACTION VALIDATOR MINATA: {receipt}",
                flush=True
            )

        except Exception as e:

            print(
                f"ERRORE addValidator: {str(e)}",
                flush=True
            )

        print("DOPO TRY VALIDATOR", flush=True)

        print("PRIMA TRY AUTHORITY", flush=True)

        try:

            print("ENTRATO TRY AUTHORITY", flush=True)

            contract = get_contract()

            normalized_address = normalize_address(
                user.wallet_address
            )

            tx_hash = contract.functions.addAuthority(
                normalized_address
            ).transact(tx_params())

            print(
                f"TX HASH AUTHORITY: {tx_hash.hex()}",
                flush=True
            )

            receipt = w3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=60
            )

            print(
                f"TRANSACTION AUTHORITY MINATA: {receipt}",
                flush=True
            )

        except Exception as e:

            print(
                f"ERRORE addAuthority: {str(e)}",
                flush=True
            )

        print("DOPO TRY AUTHORITY", flush=True)

        # =========================================================
        # RETURN
        # =========================================================

        print("ARRIVATO AL JSONIFY FINALE", flush=True)

        return jsonify({
            "message": "Doctor creato con successo",
            "doctor_id": doctor.id,
            "user_id": user.id
        }), 201

    except Exception as e:

        print(
            f"ERRORE GENERALE register_doctor: {str(e)}",
            flush=True
        )

        return jsonify({
            "error": str(e)
        }), 500