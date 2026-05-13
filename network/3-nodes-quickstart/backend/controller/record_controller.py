from controller.controller import record_to_dict, normalize_address, bytes32_from_value, tx_params
from flask import Blueprint, request, jsonify
from database.database import db, Record, Visit, Doctor, User
from blockchain.contract import get_contract
from blockchain.config import ACCOUNT, w3
from web3 import Web3

api = Blueprint("record_api", __name__)


# -----------------------------
# HELPER: firma e invia tx con private key
# -----------------------------
def sign_and_send(tx_data, private_key):
    """Firma una transazione con la private key e la invia sulla chain."""
    signed = w3.eth.account.sign_transaction(tx_data, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    return tx_hash, receipt


# -----------------------------
# HELPER: parametri tx legacy (Quorum/Besu)
# -----------------------------
def legacy_tx_params(from_address):
    addr = normalize_address(from_address)
    return {
        "from": addr,
        "nonce": w3.eth.get_transaction_count(addr),
        "chainId": w3.eth.chain_id,
        "gas": 5_000_000,
        "gasPrice": w3.to_wei(0, "gwei"),
        "value": 0,
    }


# -----------------------------
# HELPER: recupera private key del dottore dalla visita
# -----------------------------
def get_doctor_private_key(visit):
    """Risale da Visit → Doctor → User → private_key."""
    doctor = Doctor.query.get(visit.doctor_id)
    if not doctor:
        raise ValueError(f"Doctor non trovato per visit {visit.id}")

    user = User.query.get(doctor.user_id)
    if not user or not user.private_key:
        raise ValueError(f"Private key non trovata per doctor {doctor.id}")

    return user.wallet_address, user.private_key


# -----------------------------
# GET /records
# -----------------------------
@api.route("/records", methods=["GET"])
def list_records():
    status = request.args.get("status")
    query = Record.query
    if status:
        query = query.filter_by(status=status)
    records = query.all()
    return jsonify([record_to_dict(r) for r in records])


# -----------------------------
# GET /records/<id>
# -----------------------------
@api.route("/records/<int:record_id>", methods=["GET"])
def get_record(record_id):
    record = Record.query.get(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(record_to_dict(record))


# -----------------------------
# POST /visit/<id>/propose_record
# -----------------------------
@api.route("/visit/<int:visit_id>/propose_record", methods=["POST"])
def propose_record_for_visit(visit_id):

    visit = Visit.query.get(visit_id)
    if not visit:
        return jsonify({"error": "Visit non trovata"}), 404

    if not visit.confirmed:
        return jsonify({"error": "Visit non confermata dal paziente"}), 400

    # Controlla se esiste già un record per questa visita
    existing = Record.query.filter_by(visit_id=visit.id).first()
    if existing:
        return jsonify({
            "error": "Record già esistente per questa visita",
            "record_id": existing.id
        }), 409

    try:
        wallet_address, private_key = get_doctor_private_key(visit)

        contract = get_contract()
        data_hash = Web3.to_bytes(hexstr=visit.data_hash)

        print("=== DEBUG PROPOSE RECORD ===")
        print("DOCTOR WALLET:", wallet_address)
        print("visit.blockchain_id:", visit.blockchain_id)
        print("data_hash:", data_hash.hex())

        # Costruisce la transazione
        tx_data = contract.functions.proposeRecord(
            visit.blockchain_id,
            data_hash
        ).build_transaction(legacy_tx_params(wallet_address))

        # Firma e invia con la private key del dottore
        tx_hash, receipt = sign_and_send(tx_data, private_key)

        print("TX STATUS:", receipt.status)

        if receipt.status == 0:
            return jsonify({
                "error": "Transazione fallita on-chain (REVERT)",
                "debug": {
                    "visit_id": visit_id,
                    "blockchain_id": visit.blockchain_id,
                    "doctor_wallet": wallet_address
                }
            }), 400

        # Legge l'evento per ottenere il blockchain_id del record
        events = contract.events.RecordProposed().process_receipt(receipt)
        if not events:
            return jsonify({"error": "Evento RecordProposed non trovato"}), 500

        blockchain_record_id = events[0].args.recordId

        record = Record(
            blockchain_id=blockchain_record_id,
            visit_id=visit.id,
            authority_wallet=wallet_address,
            data_hash=visit.data_hash,
            status="PENDING",
            approve_votes=0,
            reject_votes=0,
            blockchain_tx=tx_hash.hex(),
        )

        db.session.add(record)
        db.session.commit()

        return jsonify({
            "status": "SUCCESS",
            "tx_hash": tx_hash.hex(),
            "record_id": record.id,
            "blockchain_record_id": blockchain_record_id,
            "blockNumber": receipt.blockNumber
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print("❌ ERROR propose_record:", e)
        return jsonify({"error": str(e)}), 500


# -----------------------------
# POST /records/<id>/vote
# — firma direttamente lato server con la private key del dottore
# -----------------------------
@api.route("/records/<int:record_id>/vote", methods=["POST"])
def vote(record_id):
    data = request.get_json() or {}
    approve = data.get("approve")
    doctor_id = data.get("doctor_id")

    if approve is None:
        return jsonify({"error": "Campo 'approve' obbligatorio"}), 400

    if not doctor_id:
        return jsonify({"error": "Campo 'doctor_id' obbligatorio"}), 400

    record = Record.query.get(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    if record.status != "PENDING":
        return jsonify({"error": f"Record non votabile, stato: {record.status}"}), 400

    try:
        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            return jsonify({"error": "Doctor non trovato"}), 404

        user = User.query.get(doctor.user_id)
        if not user or not user.private_key:
            return jsonify({"error": "Private key non trovata"}), 400

        wallet_address = user.wallet_address
        private_key = user.private_key

        contract = get_contract()

        print("\n===== VOTE DEBUG START =====")
        print("Record DB id:", record.id)
        print("Blockchain record id:", record.blockchain_id)
        print("Voter:", wallet_address)
        print("Approve:", approve)

        already_voted = contract.functions.hasVoted(
            record.blockchain_id,
            Web3.to_checksum_address(wallet_address)
        ).call()

        print("Already voted:", already_voted)

        if already_voted:
            return jsonify({"error": "Hai già votato questo record"}), 409

        tx_data = contract.functions.vote(
            record.blockchain_id,
            approve
        ).build_transaction(legacy_tx_params(wallet_address))

        tx_hash, receipt = sign_and_send(tx_data, private_key)

        print("TX HASH:", tx_hash.hex())
        print("TX STATUS:", receipt.status)
        print("BLOCK NUMBER:", receipt.blockNumber)

        # 🔥 STEP 1: stato immediato on-chain
        state1 = contract.functions.getRecord(record.blockchain_id).call()
        print("\nSTATE IMMEDIATO ON-CHAIN:")
        print(state1)

        import time
        time.sleep(2)

        # 🔥 STEP 2: stato dopo sync
        state2 = contract.functions.getRecord(record.blockchain_id).call()
        print("\nSTATE DOPO 2s:")
        print(state2)

        print("===== VOTE DEBUG END =====\n")

        # 🔥 SYNC COMPLETO DA BLOCKCHAIN (NON DB LOCAL COUNTER)
        record.approve_votes = int(state2[5])
        record.reject_votes = int(state2[6])

        status = int(state2[4])

        if status == 1:
            record.status = "APPROVED"
        elif status == 2:
            record.status = "REJECTED"

        db.session.commit()

        return jsonify({
            "status": "SUCCESS",
            "tx_hash": tx_hash.hex(),
            "record_status": record.status,
            "approve_votes": record.approve_votes,
            "reject_votes": record.reject_votes,
        }), 200

    except Exception as e:
        print("❌ VOTE ERROR:", e)
        return jsonify({"error": str(e)}), 500