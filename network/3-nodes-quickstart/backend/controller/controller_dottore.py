from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from web3 import Web3
from eth_account.messages import encode_defunct

from blockchain.config import w3
from database.database import db, Doctor

api = Blueprint("dottore_api", __name__)


# ----------------------------
# UTILS
# ----------------------------

def normalize_address(addr):
    if not addr:
        return None
    return Web3.to_checksum_address(addr)


def model_to_dict(obj, fields):
    return {field: getattr(obj, field) for field in fields}


# ----------------------------
# GET ALL DOCTORS
# ----------------------------

@api.route("/doctors", methods=["GET"])
def list_doctors():
    doctors = Doctor.query.all()

    return jsonify([
        model_to_dict(d, ["id", "wallet_address", "nome", "cognome"])
        for d in doctors
    ])


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
# CREATE / LOGIN DOCTOR (META MASK)
# ----------------------------

@api.route("/doctors", methods=["POST"])
def create_doctor():
    data = request.get_json() or {}

    wallet_address = normalize_address(data.get("wallet_address"))
    nome = data.get("nome")
    cognome = data.get("cognome")
    signature = data.get("signature")
    message = data.get("message")

    # ----------------------------
    # VALIDATION INPUT
    # ----------------------------
    if not wallet_address or not nome or not cognome or not signature or not message:
        return jsonify({
            "error": "wallet_address, nome, cognome, signature e message sono obbligatori"
        }), 400

    # ----------------------------
    # CHECK IF DOCTOR EXISTS (LOGIN MODE)
    # ----------------------------
    existing = Doctor.query.filter_by(wallet_address=wallet_address).first()

    if existing:
        return jsonify({
            "message": "Doctor già registrato",
            "doctor": model_to_dict(existing, ["id", "wallet_address", "nome", "cognome"])
        }), 200

    # ----------------------------
    # VERIFY META MASK SIGNATURE
    # ----------------------------
    try:
        encoded_message = encode_defunct(text=message)

        recovered = w3.eth.account.recover_message(
            encoded_message,
            signature=signature
        )

        if recovered.lower() != wallet_address.lower():
            return jsonify({"error": "Firma non valida"}), 401

    except Exception:
        return jsonify({"error": "Errore verifica firma"}), 400

    # ----------------------------
    # CREATE DOCTOR
    # ----------------------------
    doctor = Doctor(
        wallet_address=wallet_address,
        nome=nome,
        cognome=cognome,
    )

    try:
        db.session.add(doctor)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Doctor già esistente"}), 409

    return jsonify(
        model_to_dict(doctor, ["id", "wallet_address", "nome", "cognome"])
    ), 201