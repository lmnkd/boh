from controller.controller import record_to_dict, normalize_address, bytes32_from_value, tx_params
from flask import Blueprint, request, jsonify
from database.database import db, Record, Visit, Doctor, User, Probability, Vote
from blockchain.contract import get_contract
from blockchain.config import ACCOUNT, w3
from web3 import Web3

api = Blueprint("record_api", __name__)

# -----------------------------
# COSTANTI BAYESIANE
# -----------------------------
APPROVAL_THRESHOLD  = 0.90
REJECTION_THRESHOLD = 0.10
REPUTATION_REWARD   = 0.02
REPUTATION_PENALTY  = 0.03
MIN_VOTES           = 1


# -----------------------------
# HELPER: firma e invia tx
# -----------------------------
def sign_and_send(tx_data, private_key):
    signed = w3.eth.account.sign_transaction(tx_data, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    return tx_hash, receipt


# -----------------------------
# HELPER: parametri tx legacy
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
# HELPER: recupera credenziali dottore
# -----------------------------
def get_doctor_credentials(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        raise ValueError(f"Doctor {doctor_id} non trovato")
    user = User.query.get(doctor.user_id)
    if not user or not user.private_key:
        raise ValueError(f"Private key non trovata per doctor {doctor_id}")
    return doctor, user.wallet_address, user.private_key


# -----------------------------
# MOTORE BAYESIANO
# -----------------------------
def bayesian_update(prior, reputation, approve):
    """
    Aggiorna la probabilità posteriore con il teorema di Bayes.
    prior      = probabilità corrente che il record sia corretto [0,1]
    reputation = affidabilità del validatore [0,1]
    approve    = True se approva, False se rifiuta
    """
    likelihood = reputation if approve else (1 - reputation)
    denominator = (likelihood * prior) + ((1 - likelihood) * (1 - prior))
    if denominator == 0:
        return prior
    posterior = (likelihood * prior) / denominator
    return round(posterior, 6)


def update_reputation(doctor, approved_final, voted_approve):
    """
    Ricompensa o penalizza il dottore in base alla coerenza
    del suo voto con il risultato finale.
    """
    if voted_approve == approved_final:
        doctor.reputation = min(1.0, round(doctor.reputation + REPUTATION_REWARD, 4))
    else:
        doctor.reputation = max(0.0, round(doctor.reputation - REPUTATION_PENALTY, 4))


# -----------------------------
# HELPER: finalizza record on-chain
# -----------------------------
def finalize_record_onchain(record, approved):
    """
    Chiama finalizeRecord sul contratto usando la private key
    dell'authority che ha proposto il record.
    """
    proposer_user = User.query.filter_by(
        wallet_address=record.authority_wallet
    ).first()

    if not proposer_user or not proposer_user.private_key:
        raise ValueError("Private key dell'authority non trovata")

    contract = get_contract()
    tx_data = contract.functions.finalizeRecord(
        record.blockchain_id,
        approved
    ).build_transaction(legacy_tx_params(record.authority_wallet))

    tx_hash, receipt = sign_and_send(tx_data, proposer_user.private_key)

    if receipt.status == 0:
        raise ValueError("finalizeRecord fallita on-chain (REVERT)")

    return tx_hash


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

    existing = Record.query.filter_by(visit_id=visit.id).first()
    if existing:
        return jsonify({
            "error": "Record già esistente per questa visita",
            "record_id": existing.id
        }), 409

    try:
        doctor, wallet_address, private_key = get_doctor_credentials(visit.doctor_id)

        contract = get_contract()
        data_hash = Web3.to_bytes(hexstr=visit.data_hash)

        print("=== DEBUG PROPOSE RECORD ===")
        print("DOCTOR WALLET:", wallet_address)
        print("visit.blockchain_id:", visit.blockchain_id)
        print("data_hash:", data_hash.hex())

        tx_data = contract.functions.proposeRecord(
            visit.blockchain_id,
            data_hash
        ).build_transaction(legacy_tx_params(wallet_address))

        tx_hash, receipt = sign_and_send(tx_data, private_key)

        print("TX STATUS:", receipt.status)

        if receipt.status == 0:
            return jsonify({"error": "Transazione fallita on-chain (REVERT)"}), 400

        events = contract.events.RecordProposed().process_receipt(receipt)
        if not events:
            return jsonify({"error": "Evento RecordProposed non trovato"}), 500

        blockchain_record_id = events[0].args.recordId

        # Crea record nel DB
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

        # Crea probabilità iniziale (prior = 0.50)
        probability = Probability(
            record_id=record.id,
            prior=50,
            posterior=50,
            blockchain_tx=tx_hash.hex(),
        )
        db.session.add(probability)
        db.session.commit()

        print(f"✅ Record {record.id} creato con probabilità iniziale 0.50")

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
# -----------------------------
@api.route("/records/<int:record_id>/vote", methods=["POST"])
def vote(record_id):
    data = request.get_json() or {}
    print("=== VOTE CHIAMATO ===")
    print("record_id:", record_id)
    print("data ricevuta:", data)

    approve = data.get("approve")
    doctor_id = data.get("doctor_id")

    if approve is None:
        return jsonify({"error": "Campo 'approve' obbligatorio (true/false)"}), 400
    if not doctor_id:
        return jsonify({"error": "Campo 'doctor_id' obbligatorio"}), 400

    record = Record.query.get(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    if record.status != "PENDING":
        return jsonify({"error": f"Record non votabile, stato: {record.status}"}), 400

    try:
        doctor, wallet_address, private_key = get_doctor_credentials(doctor_id)

        contract = get_contract()

        already_voted = contract.functions.hasVoted(
            record.blockchain_id,
            Web3.to_checksum_address(wallet_address)
        ).call()

        print("=== DEBUG VOTE ===")
        print("DOCTOR WALLET:", wallet_address)
        print("DOCTOR REPUTATION:", doctor.reputation)
        print("ALREADY VOTED:", already_voted)

        if already_voted:
            return jsonify({"error": "Hai già votato questo record"}), 409

        # Step 1: invia voto on-chain
        tx_data = contract.functions.vote(
            record.blockchain_id,
            approve
        ).build_transaction(legacy_tx_params(wallet_address))

        tx_hash, receipt = sign_and_send(tx_data, private_key)

        print("TX STATUS:", receipt.status)

        if receipt.status == 0:
            return jsonify({"error": "Transazione voto fallita on-chain (REVERT)"}), 400

        # Step 2: aggiorna contatori DB
        if approve:
            record.approve_votes += 1
        else:
            record.reject_votes += 1

        # Step 3: salva il voto nel DB
        vote_entry = Vote(
            record_id=record.id,
            doctor_id=doctor_id,
            approve=approve
        )
        db.session.add(vote_entry)

        # Step 4: aggiorna probabilità bayesiana
        probability = Probability.query.filter_by(
            record_id=record.id
        ).order_by(Probability.id.desc()).first()

        prior = (probability.posterior / 100.0) if probability else 0.5
        posterior = bayesian_update(prior, doctor.reputation, approve)
        posterior_int = round(posterior * 100)

        print("=== BAYESIAN UPDATE ===")
        print(f"Prior: {prior}")
        print(f"Reputation: {doctor.reputation}")
        print(f"Approve: {approve}")
        print(f"Posterior: {posterior}")

        new_probability = Probability(
            record_id=record.id,
            prior=round(prior * 100),
            posterior=posterior_int,
            blockchain_tx=tx_hash.hex(),
        )
        db.session.add(new_probability)

        # Step 5: controlla soglia bayesiana
        total_votes = record.approve_votes + record.reject_votes
        finalized = False
        approved_final = None

        if total_votes >= MIN_VOTES:
            if posterior >= APPROVAL_THRESHOLD:
                approved_final = True
                finalized = True
                print(f"✅ Soglia approvazione raggiunta: {posterior} >= {APPROVAL_THRESHOLD}")
            elif posterior <= REJECTION_THRESHOLD:
                approved_final = False
                finalized = True
                print(f"❌ Soglia rifiuto raggiunta: {posterior} <= {REJECTION_THRESHOLD}")

        if finalized:
            # Step 6: finalizza on-chain
            finalize_tx = finalize_record_onchain(record, approved_final)
            record.status = "APPROVED" if approved_final else "REJECTED"
            record.blockchain_tx = finalize_tx.hex()
            print(f"🏁 Record finalizzato: {record.status}")

            # Step 7: aggiorna reputazione di tutti i votanti
            for vote_entry in record.votes:
                update_reputation(vote_entry.doctor, approved_final, vote_entry.approve)
                print(f"  👤 {vote_entry.doctor.nome}: reputazione → {vote_entry.doctor.reputation}")

        db.session.commit()

        return jsonify({
            "status": "SUCCESS",
            "tx_hash": tx_hash.hex(),
            "record_status": record.status,
            "approve_votes": record.approve_votes,
            "reject_votes": record.reject_votes,
            "bayesian": {
                "prior": prior,
                "posterior": posterior,
                "threshold_approval": APPROVAL_THRESHOLD,
                "threshold_rejection": REJECTION_THRESHOLD,
                "finalized": finalized,
            }
        }), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print("❌ ERROR vote:", e)
        return jsonify({"error": str(e)}), 500


# -----------------------------
# POST /fund_address
# -----------------------------
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