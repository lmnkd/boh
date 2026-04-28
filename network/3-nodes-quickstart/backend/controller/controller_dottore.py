from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from web3 import Web3
from eth_account.messages import encode_defunct

from blockchain.config import w3
from database.database import db, Doctor, User

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

    data = request.get_json()

    # -------------------------
    # 1. CREA USER
    # -------------------------
    user = User(
        email=data["email"],
        wallet_address=data["wallet_address"],
        role="DOCTOR"
    )
    user.set_password(data["password"])

    db.session.add(user)
    db.session.commit()  # serve per ottenere user.id

    # -------------------------
    # 2. CREA DOCTOR
    # -------------------------
    doctor = Doctor(
        user_id=user.id,
        nome=data["nome"],
        cognome=data["cognome"]
    )

    db.session.add(doctor)
    db.session.commit()

    return jsonify({
        "message": "Doctor creato con successo",
        "doctor_id": doctor.id,
        "user_id": user.id
    }), 201