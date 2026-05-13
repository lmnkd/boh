from datetime import date, datetime

from flask import Blueprint, jsonify, request, render_template
from sqlalchemy.exc import IntegrityError
from web3 import Web3

from blockchain.config import ACCOUNT, w3
from blockchain.contract import get_contract
from database.database import db, Patient, Doctor, Admin, Visit, Record, Probability

api = Blueprint("api", __name__)


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


def normalize_address(address):
    if not address:
        raise ValueError("Missing address")
    return Web3.to_checksum_address(address)


def tx_params(from_address=None):
    params = {
        "from": normalize_address(from_address) if from_address else normalize_address(ACCOUNT),
        "gas": 5_000_000,
    }
    if w3.eth.chain_id is not None:
        params["chainId"] = w3.eth.chain_id
    return params


def model_to_dict(model, fields):
    output = {}
    for field in fields:
        value = getattr(model, field)
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        output[field] = value
    return output


def record_to_dict(record):
    return {
        "id": record.id,
        "blockchain_id": record.blockchain_id,
        "visit_id": record.visit_id,
        "authority_wallet": record.authority_wallet,
        "data_hash": record.data_hash,
        "status": record.status,
        "approve_votes": record.approve_votes,
        "reject_votes": record.reject_votes,
        "blockchain_tx": record.blockchain_tx,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def probability_to_dict(prob):
    return {
        "id": prob.id,
        "blockchain_id": prob.blockchain_id,
        "record_id": prob.record_id,
        "prior": prob.prior,
        "posterior": prob.posterior,
        "blockchain_tx": prob.blockchain_tx,
        "created_at": prob.created_at.isoformat() if prob.created_at else None,
    }


@api.route("/patients", methods=["GET"])
def list_patients():
    patients = Patient.query.all()
    return jsonify([model_to_dict(p, ["id", "nome", "cognome", "data_nascita", "patient_hash", "created_at"]) for p in patients])


@api.route("/patients/<int:patient_id>", methods=["GET"])
def get_patient(patient_id):
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found"}), 404
    return jsonify(model_to_dict(patient, ["id", "nome", "cognome", "data_nascita", "patient_hash", "created_at"]))


@api.route("/patients", methods=["POST"])
def create_patient():
    data = request.get_json() or {}
    nome = data.get("nome")
    cognome = data.get("cognome")
    data_nascita = data.get("data_nascita")
    patient_hash = data.get("patient_hash")

    if not nome or not cognome or not patient_hash:
        return jsonify({"error": "nome, cognome e patient_hash sono obbligatori"}), 400

    patient = Patient(
        nome=nome,
        cognome=cognome,
        data_nascita=data_nascita,
        patient_hash=patient_hash,
    )

    try:
        db.session.add(patient)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Patient già esistente"}), 409

    return jsonify(model_to_dict(patient, ["id", "nome", "cognome", "data_nascita", "patient_hash", "created_at"])), 201


@api.route("/admins", methods=["GET"])
def list_admins():
    admins = Admin.query.all()
    return jsonify([model_to_dict(a, ["id", "nome", "indirizzo"]) for a in admins])


@api.route("/admins/<int:admin_id>", methods=["GET"])
def get_admin(admin_id):
    admin = Admin.query.get(admin_id)
    if not admin:
        return jsonify({"error": "Admin not found"}), 404
    return jsonify(model_to_dict(admin, ["id", "nome", "indirizzo"]))


@api.route("/admins", methods=["POST"])
def create_admin():
    data = request.get_json() or {}
    nome = data.get("nome")
    indirizzo = data.get("indirizzo")

    if not nome:
        return jsonify({"error": "nome è obbligatorio"}), 400

    admin = Admin(nome=nome, indirizzo=indirizzo)

    try:
        db.session.add(admin)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Admin già esistente"}), 409

    return jsonify(model_to_dict(admin, ["id", "nome", "indirizzo"])), 201


@api.route("/contract/register", methods=["POST"])
def register_contract_role():
    data = request.get_json() or {}
    role = data.get("role")
    address = normalize_address(data.get("address"))
    from_address = data.get("from_address")

    if role not in {"doctor", "authority", "oracle", "patient"}:
        return jsonify({"error": "role deve essere doctor, authority, oracle o patient"}), 400

    contract = get_contract()
    function_name = f"add{role.capitalize()}"
    contract_function = getattr(contract.functions, function_name, None)
    if not contract_function:
        return jsonify({"error": f"Funzione {function_name} non trovata"}), 500

    try:
        tx_hash = contract_function(address).transact(tx_params(from_address))
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({
        "status": "SUCCESS",
        "role": role,
        "address": address,
        "tx_hash": tx_hash.hex(),
        "receipt": {
            "blockNumber": receipt.blockNumber,
            "transactionHash": receipt.transactionHash.hex(),
        },
    }), 201


@api.route("/probabilities", methods=["GET"])
def list_probabilities():
    probabilities = Probability.query.all()
    return jsonify([probability_to_dict(p) for p in probabilities])


@api.route("/probabilities/<int:probability_id>", methods=["GET"])
def get_probability(probability_id):
    probability = Probability.query.get(probability_id)
    if not probability:
        return jsonify({"error": "Probability not found"}), 404
    return jsonify(probability_to_dict(probability))


@api.route("/probabilities", methods=["POST"])
def create_probability():
    data = request.get_json() or {}
    record_id = data.get("record_id")
    prior = data.get("prior")
    posterior = data.get("posterior")
    from_address = data.get("from_address")

    if not record_id or prior is None or posterior is None:
        return jsonify({"error": "record_id, prior e posterior sono obbligatori"}), 400

    record = Record.query.get(record_id)
    if not record:
        return jsonify({"error": "Record non trovato"}), 404

    try:
        tx_hash = get_contract().functions.updateProbability(
            record.blockchain_id, int(prior), int(posterior)
        ).transact(tx_params(from_address))
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        events = get_contract().events.ProbabilityUpdated().process_receipt(receipt)
        if not events:
            raise ValueError("Evento ProbabilityUpdated non trovato")
        blockchain_id = events[0].args.probId
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    probability = Probability(
        blockchain_id=blockchain_id,
        record_id=record.id,
        prior=int(prior),
        posterior=int(posterior),
        blockchain_tx=tx_hash.hex(),
    )

    db.session.add(probability)
    db.session.commit()

    return jsonify({"status": "SUCCESS", "probability": probability_to_dict(probability)}), 201