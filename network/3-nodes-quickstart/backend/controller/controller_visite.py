from datetime import datetime

from flask import Blueprint, jsonify, request, render_template
from web3 import Web3
from database.database import db, User, Patient, Doctor, Admin, Visit, Record, Probability
from blockchain.config import ACCOUNT, w3
from blockchain.contract import get_contract

api = Blueprint("visite_api", __name__)


def visit_to_dict(visit):
    return {
        "id": visit.id,
        "blockchain_id": visit.blockchain_id,
        "patient_id": visit.patient_id,
        "patient_wallet": visit.patient.user.wallet_address if visit.patient and visit.patient.user else None,
        "doctor_id": visit.doctor_id,
        "doctor_wallet": visit.doctor.user.wallet_address if visit.doctor and visit.doctor.user else None,
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


# -----------------------------
# GET /visits
# -----------------------------
@api.route("/visits", methods=["GET"])
def list_visits():
    visits = Visit.query.all()
    return render_template("visite.html", visits=visits)


# -----------------------------
# DELETE /visits/<id>
# -----------------------------
@api.route("/visits/delete/<int:visit_id>", methods=["GET"])
def delete_visit(visit_id):
    visit = Visit.query.get(visit_id)
    if not visit:
        return jsonify({"error": "Visit not found"}), 404
    db.session.delete(visit)
    db.session.commit()
    return jsonify({"status": "SUCCESS", "message": "Visit deleted successfully"})


# -----------------------------
# GET /visits/<id>
# -----------------------------
@api.route("/visits/<int:visit_id>", methods=["GET"])
def get_visit(visit_id):
    visit = Visit.query.get(visit_id)
    if not visit:
        return jsonify({"error": "Visit not found"}), 404
    return jsonify(visit_to_dict(visit))


# -----------------------------
# POST /visits
# -----------------------------
@api.route("/visits", methods=["POST"])
def submit_visit():
    data = request.get_json() or {}

    p_max = data.get("pressione_max")
    p_min = data.get("pressione_min")
    battiti = data.get("battiti")
    note = data.get("note", "")

    try:
        p_max, p_min, battiti = int(p_max), int(p_min), int(battiti)
        if p_max <= p_min:
            return jsonify({"error": "La pressione massima deve essere superiore alla minima"}), 400
        if not (40 <= p_max <= 250) or not (30 <= battiti <= 220):
            return jsonify({"error": "Parametri vitali fuori range fisiologico"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "I parametri medici devono essere numeri validi"}), 400

    patient_id = data.get("patient_id")
    doctor_id = data.get("doctor_id")

    if not patient_id or not doctor_id:
        return jsonify({"error": "patient_id e doctor_id obbligatori"}), 400

    patient = Patient.query.get(patient_id)
    doctor = Doctor.query.get(doctor_id)

    if not patient or not doctor:
        return jsonify({"error": "Patient o Doctor non trovato"}), 404

    patient_address = normalize_address(patient.user.wallet_address)

    now = datetime.utcnow().isoformat()
    data_content = f"{patient_id}-{doctor_id}-{p_max}-{p_min}-{battiti}-{now}"
    final_data_hash = Web3.keccak(text=data_content)
    patient_hash = Web3.keccak(text=str(patient_id))

    contract = get_contract()

    try:
        tx_hash = contract.functions.submitVisit(
            patient_address,
            patient_hash,
            final_data_hash,
        ).transact(tx_params())

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        print(f"📋 Receipt status: {receipt.get('status')}, gasUsed: {receipt.get('gasUsed')}")
        print(f"📋 Logs nella receipt: {len(receipt.get('logs', []))}")

        try:
            events = contract.events.VisitSubmitted().process_receipt(receipt)
        except Exception as e:
            print(f"⚠️ Errore processamento evento: {str(e)}")
            events = []

        if not events:
            print("⚠️ Evento non trovato, uso visitCount...")
            blockchain_id = contract.functions.visitCount().call()
            print(f"📋 visitCount dal contratto: {blockchain_id}")
        else:
            blockchain_id = events[0].args.visitId
            print(f"✅ Evento trovato! visitId: {blockchain_id}")

    except Exception as exc:
        print(f"❌ Errore submitVisit: {str(exc)}")
        return jsonify({"error": str(exc)}), 500

    visit = Visit(
        blockchain_id=blockchain_id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        pressione_max=p_max,
        pressione_min=p_min,
        battiti=battiti,
        note=note,
        patient_hash=patient_hash.hex(),
        data_hash=final_data_hash.hex(),
        confirmed=False,
        blockchain_tx=tx_hash.hex(),
    )

    db.session.add(visit)
    db.session.commit()

    return jsonify({
        "status": "SUCCESS",
        "visit": visit_to_dict(visit)
    }), 201


# -----------------------------
# POST /visits/<id>/confirm
# -----------------------------
@api.route("/visits/<int:visit_id>/confirm", methods=["POST"])
def confirm_visit(visit_id):

    visit = Visit.query.get(visit_id)
    if not visit:
        return jsonify({"error": "Visit non trovato"}), 404

    patient = Patient.query.get(visit.patient_id)
    if not patient:
        return jsonify({"error": "Paziente non trovato"}), 404

    user = User.query.get(patient.user_id)

    print("=== DEBUG USER ===", flush=True)
    print("wallet:", user.wallet_address, flush=True)
    print("has_private_key:", bool(user.private_key), flush=True)

    if not user or not user.private_key:
        return jsonify({"error": "Wallet paziente non trovato"}), 404

    try:
        contract = get_contract()

        nonce = w3.eth.get_transaction_count(user.wallet_address)
        print("=== DEBUG NONCE ===", nonce, flush=True)

        tx = contract.functions.confirmVisit(
            visit.blockchain_id
        ).build_transaction({
            "from": user.wallet_address,
            "nonce": nonce,
            "gas": 200000,
            "gasPrice": 0
        })

        print("=== DEBUG TX ===", tx, flush=True)

        signed = w3.eth.account.sign_transaction(tx, user.private_key)
        print("=== DEBUG SIGNED TX ===", flush=True)
        print("raw tx size:", len(signed.raw_transaction), flush=True)

        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print("=== TX SENT ===", tx_hash.hex(), flush=True)

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        print("=== RECEIPT ===", flush=True)
        print("status:", receipt.status, flush=True)
        print("blockNumber:", receipt.blockNumber, flush=True)
        print("gasUsed:", receipt.gasUsed, flush=True)
        print("txHash:", receipt.transactionHash.hex(), flush=True)

        if receipt.status == 1:
            print("✅ TRANSAZIONE SUCCESSO", flush=True)
        else:
            print("❌ TRANSAZIONE FALLITA (REVERT)", flush=True)

    except Exception as exc:
        print("❌ EXCEPTION:", str(exc), flush=True)
        return jsonify({"error": str(exc), "step": "transaction_failed"}), 500

    visit_data = get_contract().functions.getVisit(visit.blockchain_id).call()
    print("VISIT ONCHAIN:", visit_data)

    visit.confirmed = visit_data[4]
    visit.blockchain_tx = tx_hash.hex()
    db.session.commit()

    return jsonify({
        "status": "SUCCESS",
        "tx_hash": tx_hash.hex(),
        "receipt": {
            "status": receipt.status,
            "blockNumber": receipt.blockNumber,
            "gasUsed": receipt.gasUsed
        }
    })