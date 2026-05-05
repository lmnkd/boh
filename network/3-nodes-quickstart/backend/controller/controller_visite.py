from datetime import date, datetime

from flask import Blueprint, jsonify, request, render_template
from sqlalchemy.exc import IntegrityError
from web3 import Web3

from blockchain.config import ACCOUNT, w3
from blockchain.contract import get_contract
from database.database import db, Patient, Doctor, Admin, Visit, Record, Probability

api = Blueprint("visite_api", __name__)

def visit_to_dict(visit):
    return {
        "id": visit.id,
        "blockchain_id": visit.blockchain_id,
        "patient_id": visit.patient_id,
        "patient_wallet": visit.patient.wallet_address if visit.patient else None,
        "doctor_id": visit.doctor_id,
        "doctor_wallet": visit.doctor.wallet_address if visit.doctor else None,
        "data_hash": visit.data_hash,
        "patient_hash": visit.patient_hash,
        "confirmed": visit.confirmed,
        "blockchain_tx": visit.blockchain_tx,
        "created_at": visit.created_at.isoformat() if visit.created_at else None,
    }


def normalize_address(address):
    if not address:
        raise ValueError("Missing address")
    return Web3.to_checksum_address(address)

def bytes32_from_value(value):
    if value is None:
        raise ValueError("Missing bytes32 value")

    if isinstance(value, bytes):
        if len(value) != 32:
            raise ValueError("bytes32 value must be exactly 32 bytes")
        return value

    if isinstance(value, str):
        if value.startswith("0x"):
            raw = Web3.to_bytes(hexstr=value)
            if len(raw) != 32:
                raise ValueError("Hex string must encode exactly 32 bytes")
            return raw

        encoded = value.encode("utf-8")
        if len(encoded) > 32:
            raise ValueError("String value must fit within 32 bytes")
        return encoded.ljust(32, b"\0")

    raise ValueError("Unsupported bytes32 value type")


def tx_params(from_address=None):
    params = {
        "from": normalize_address(from_address) if from_address else normalize_address(ACCOUNT),
        "gas": 5_000_000,
    }
    if w3.eth.chain_id is not None:
        params["chainId"] = w3.eth.chain_id
    return params

@api.route("/visits", methods=["GET"])
def list_visits():
    visits = Visit.query.all()
    return render_template("visite.html", visits=visits)

@api.route("/visits/delete/<int:visit_id>", methods=["GET"])
def delete_visit(visit_id):
    visit = Visit.query.get(visit_id)
    if not visit:
        return jsonify({"error": "Visit not found"}), 404
    db.session.delete(visit)
    db.session.commit()
    return jsonify({"status": "SUCCESS", "message": "Visit deleted successfully"})


@api.route("/visits/<int:visit_id>", methods=["GET"])
def get_visit(visit_id):
    visit = Visit.query.get(visit_id)
    if not visit:
        return jsonify({"error": "Visit not found"}), 404
    return jsonify(visit_to_dict(visit))


@api.route("/visits", methods=["POST"])
def submit_visit():
    data = request.get_json() or {}

    patient_id = data.get("patient_id")
    doctor_id = data.get("doctor_id")

    if not patient_id or not doctor_id:
        return jsonify({"error": "patient_id e doctor_id obbligatori"}), 400

    patient = Patient.query.get(patient_id)
    doctor = Doctor.query.get(doctor_id)

    if not patient or not doctor:
        return jsonify({"error": "Patient o Doctor non trovato"}), 404

    # 🔐 NON mettiamo dati personali on-chain
    patient_address = patient.wallet_address
    doctor_address = doctor.wallet_address

    # 🔐 generazione hash (esempio semplice)
    patient_hash = Web3.keccak(text=str(patient_id))
    data_hash = Web3.keccak(text=f"{patient_id}-{doctor_id}-{datetime.utcnow()}")

    contract = get_contract()

    try:
        tx_hash = contract.functions.submitVisit(
            patient_address,
            patient_hash,
            data_hash,
        ).transact(tx_params(doctor_address))

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        events = contract.events.VisitSubmitted().processReceipt(receipt)
        if not events:
            raise ValueError("Evento VisitSubmitted non trovato")

        blockchain_id = events[0].args.visitId

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    visit = Visit(
        blockchain_id=blockchain_id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        patient_hash=patient_hash.hex(),
        data_hash=data_hash.hex(),
        confirmed=False,
        blockchain_tx=tx_hash.hex(),
    )

    db.session.add(visit)
    db.session.commit()

    return jsonify({
        "status": "SUCCESS",
        "visit": visit_to_dict(visit)
    }), 201


@api.route("/visits/<int:visit_id>/confirm", methods=["POST"])
def confirm_visit(visit_id):
    data = request.get_json() or {}
    from_address = data.get("from_address")
    visit = Visit.query.get(visit_id)

    if not visit:
        return jsonify({"error": "Visit non trovato"}), 404

    try:
        tx_hash = get_contract().functions.confirmVisit(visit.blockchain_id).transact(tx_params(from_address))
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    visit.confirmed = True
    visit.blockchain_tx = tx_hash.hex()
    db.session.commit()

    return jsonify({"status": "SUCCESS", "visit": visit_to_dict(visit), "receipt": {"blockNumber": receipt.blockNumber}})
