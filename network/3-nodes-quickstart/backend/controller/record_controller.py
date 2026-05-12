from controller.controller import record_to_dict, normalize_address, bytes32_from_value, tx_params
from flask import Blueprint, request, jsonify
from database.database import db, Record, Visit
from blockchain.contract import get_contract
from blockchain.config import ACCOUNT, w3
from controller.blockchain_service import propose_record, vote_record
from web3 import Web3

api = Blueprint("record_api", __name__)

def check_authority_role(contract, account):
    try:
        role = Web3.keccak(text="AUTHORITY_ROLE")
        address = Web3.to_checksum_address(account)

        has_role = contract.functions.hasRole(role, address).call()

        print("=== ROLE DEBUG ===")
        print("ACCOUNT:", address)
        print("AUTHORITY_ROLE:", role.hex())
        print("HAS ROLE:", has_role)

        return has_role

    except Exception as e:
        print("❌ ROLE CHECK ERROR:", e)
        return None


def legacy_tx_params(from_address=None):
    """Parametri transazione legacy per Quorum/Besu (no EIP-1559, no eth_feeHistory)."""
    addr = normalize_address(from_address or ACCOUNT)
    return {
        "from": addr,
        "nonce": w3.eth.get_transaction_count(addr),
        "chainId": w3.eth.chain_id,
        "gas": 5_000_000,
        "gasPrice": w3.to_wei(0, "gwei"),
        "value": 0,
        "type": "0x0",
    }


@api.route("/records", methods=["GET"])
def list_records():
    status = request.args.get("status")
    query = Record.query
    if status:
        query = query.filter_by(status=status)
    records = query.all()
    return jsonify([record_to_dict(r) for r in records])


@api.route("/records/<int:record_id>", methods=["GET"])
def get_record(record_id):
    record = Record.query.get(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(record_to_dict(record))


def ensure_record_for_visit(visit, authority_address=None):
    existing_record = Record.query.filter_by(visit_id=visit.id).first()
    if existing_record:
        return existing_record

    try:
        tx_hash = get_contract().functions.proposeRecord(
            visit.blockchain_id,
            bytes32_from_value(visit.data_hash),
        ).transact(tx_params(authority_address))
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        events = get_contract().events.RecordProposed().process_receipt(receipt)
        if not events:
            raise ValueError("Evento RecordProposed non trovato")
        blockchain_id = events[0].args.recordId
    except Exception as exc:
        raise

    authority_wallet = normalize_address(authority_address) if authority_address else normalize_address(ACCOUNT)
    record = Record(
        blockchain_id=blockchain_id,
        visit_id=visit.id,
        authority_wallet=authority_wallet,
        data_hash=visit.data_hash,
        status="PENDING",
        approve_votes=0,
        reject_votes=0,
        blockchain_tx=tx_hash.hex(),
    )

    db.session.add(record)
    db.session.commit()
    return record


@api.route("/records/<int:record_id>/vote", methods=["POST"])
def vote(record_id):
    data = request.get_json() or {}
    approve = data.get("approve")
    from_address = data.get("from_address")

    record = Record.query.get(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    try:
        contract = get_contract()
        tx_data = contract.functions.vote(
            record.blockchain_id,
            approve
        ).build_transaction(legacy_tx_params())

        return jsonify({
            "status": "READY_FOR_TX",
            "tx_data": {
                "to":       tx_data["to"],
                "from":     tx_data["from"],
                "data":     tx_data["data"],
                "value":    tx_data["value"],
                "gas":      tx_data["gas"],
                "gasPrice": tx_data["gasPrice"],
                "chainId":  tx_data["chainId"],
                "type":     tx_data["type"],
            },
            "record_id": record_id,
            "approve": approve,
            "from_address": from_address
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/records/<int:record_id>/confirm_vote", methods=["POST"])
def confirm_vote(record_id):
    data = request.get_json() or {}
    tx_hash = data.get("tx_hash")
    approve = data.get("approve")
    from_address = data.get("from_address")

    if not tx_hash:
        return jsonify({"error": "tx_hash required"}), 400

    record = Record.query.get(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if approve:
            record.approve_votes += 1
        else:
            record.reject_votes += 1

        contract = get_contract()
        record_info = contract.functions.records(record.blockchain_id).call()

        if record_info[3]:  # approved
            record.status = "APPROVED"
        elif record.reject_votes > 0:
            record.status = "REJECTED"

        db.session.commit()

        return jsonify({
            "status": "SUCCESS",
            "record_status": record.status
        }), 200

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"error": str(e)}), 500


@api.route("/visit/<int:visit_id>/propose_record", methods=["POST"])
def propose_record_for_visit(visit_id):

    visit = Visit.query.get(visit_id)

    if not visit:
        return jsonify({"error": "Visit non trovato"}), 404

    if not visit.confirmed:
        return jsonify({"error": "Visit non confermato"}), 400

    try:
        contract = get_contract()

        # 🔥 IMPORTANTISSIMO: RIUSA HASH SALVATO, NON RICALCOLARE
        data_hash = Web3.to_bytes(hexstr=visit.data_hash)

        print("=== DEBUG PROPOSE RECORD ===")
        print("ACCOUNT:", ACCOUNT)
        print("visit.blockchain_id:", visit.blockchain_id)
        print("visit.data_hash (DB):", visit.data_hash)
        print("data_hash (bytes):", data_hash.hex())

        tx_hash = contract.functions.proposeRecord(
            visit.blockchain_id,
            data_hash
        ).transact({
            "from": normalize_address(ACCOUNT),
            "gas": 5_000_000,
            "gasPrice": w3.to_wei(0, "gwei"),
            "type": "0x0"
        })

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        print("TX STATUS:", receipt.status)

        if receipt.status == 0:
            return jsonify({
                "error": "Transazione fallita on-chain (REVERT)",
                "debug": {
                    "visit_id": visit_id,
                    "blockchain_id": visit.blockchain_id,
                    "account": ACCOUNT
                }
            }), 400

        # 🔥 CREA RECORD SOLO SE OK
        record = Record(
            blockchain_id=contract.functions.recordCount().call(),
            visit_id=visit.id,
            authority_wallet=ACCOUNT,
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
            "blockNumber": receipt.blockNumber
        })

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"error": str(e)}), 500
    
@api.route("/fund_address", methods=["POST"])
def fund_address():
    data = request.get_json() or {}
    address = data.get("address")

    if not address:
        return jsonify({"error": "address required"}), 400

    try:
        tx_hash = w3.eth.send_transaction({
            "to": address,
            "from": ACCOUNT,
            "value": w3.to_wei(1, "ether"),
            "gas": 21000,
            "gasPrice": w3.to_wei(0, "gwei"),
        })

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        return jsonify({
            "status": "FUNDED",
            "tx_hash": tx_hash.hex(),
            "amount": "1 ETH"
        })

    except Exception as e:
        print("❌ FUND ERROR:", e)
        return jsonify({"error": str(e)}), 500