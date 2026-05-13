from flask import Flask, jsonify, render_template, request, session, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from web3 import Web3
from blockchain.config import w3
from blockchain.contract import get_contract
from blockchain.deploy import deploy_contract
from database.database import create_app_db, db, seed_data, Patient, Visit, Doctor, Admin, User
import os
import time
from controller.controller import api as controller_api
from controller.controller_visite import api as visite_api
from controller.controller_dottore import api as dottore_api
from controller.record_controller import api as record_api
from controller.auth import auth
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# =========================
# CONFIG
# =========================
DATABASE_URI = os.getenv(
    "DATABASE_URI",
    "postgresql://quorum:quorumpass@postgres:5432/quorumdb"
)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")

# =========================
# DB INIT
# =========================
create_app_db(app)

with app.app_context():
    try:
        existing = db.session.execute(text("SELECT 1 FROM doctors LIMIT 1")).fetchone()
        if not existing:
            seed_data()
    except Exception:
        seed_data()

# =========================
# HOME
# =========================
@app.route("/")
def test():
    db_status = "ERROR: Connection failed"

    for attempt in range(5):
        try:
            db.session.execute(text("SELECT 1"))
            db_status = "OK"
            break
        except Exception as e:
            db_status = f"ERROR: {str(e)}"
            if attempt < 4:
                time.sleep(4)

    try:
        block = w3.eth.get_block_number()
        bc_status = f"OK - current block: {block}"
    except Exception as e:
        bc_status = f"ERROR: {str(e)}"

    return render_template(
        "pagina_iniziale.html",
        db_status=db_status,
        bc_status=bc_status
    )

# =========================
# VALIDATORS
# =========================
@app.route("/validators", methods=["GET"])
def get_validators():
    try:
        contract = get_contract()
        validator_addresses = contract.functions.getValidators().call()

        validator_addresses = [
            Web3.to_checksum_address(a) for a in validator_addresses
        ]

        validators = []

        for address in validator_addresses:
            user = User.query.filter_by(wallet_address=address).first()

            if user and user.doctor:
                validators.append({
                    "wallet_address": address,
                    "nome": user.doctor.nome,
                    "cognome": user.doctor.cognome,
                    "email": user.email,
                })
            else:
                validators.append({
                    "wallet_address": address,
                    "nome": "Sconosciuto",
                    "cognome": "",
                    "email": "",
                })

        return jsonify({"validators": validators}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================
# CONTRACT STATUS
# =========================
@app.route("/contract/status")
def contract_status():
    try:
        contract = get_contract()
        return jsonify({
            "status": "OK",
            "address": contract.address
        })
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": str(e)
        }), 500

# =========================
# DEPLOY CONTRACT
# =========================
@app.route("/contract/deploy", methods=["POST"])
def deploy():
    try:
        data = request.get_json() or {}
        validators = data.get("validators")

        if not validators:
            validators = w3.eth.accounts

        if not validators:
            return jsonify({
                "status": "ERROR",
                "message": "Nessun account disponibile nel nodo"
            }), 400

        validators = [
            Web3.to_checksum_address(v) for v in validators
        ]

        address = deploy_contract(validators)

        return jsonify({
            "status": "SUCCESS",
            "address": address,
            "validators": validators
        }), 201

    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": str(e)
        }), 500

# =========================
# PAGES
# =========================
@app.route("/registrazione_dottore")
def registrazione_dottore():
    return render_template("registrazione_dottore.html")

@app.route("/patient")
def patient_dashboard():
    if session.get("role") != "PATIENT":
        return redirect("/")

    patient = Patient.query.filter_by(user_id=session["user_id"]).first()
    if not patient:
        return redirect("/")

    return render_template("patient.html", patient=patient, visits=patient.visits)

@app.route("/doctor")
def doctor_dashboard():
    if session.get("role") != "DOCTOR":
        return redirect("/")

    doctor = Doctor.query.filter_by(user_id=session["user_id"]).first()
    if not doctor:
        return redirect("/")

    visits = doctor.visits
    patients = Patient.query.all()
    confirmed_visits = Visit.query.filter_by(confirmed=True).all()

    return render_template(
        "doctor.html",
        doctor=doctor,
        visits=visits,
        patients=patients,
        confirmed_visits=confirmed_visits
    )

@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "ADMIN":
        return redirect("/")

    admin = Admin.query.filter_by(user_id=session["user_id"]).first()
    if not admin:
        return redirect("/")

    visits = Visit.query.all()
    return render_template("admin.html", admin=admin, visits=visits)

# =========================
# BLUEPRINTS
# =========================
app.register_blueprint(auth, url_prefix="/auth")
app.register_blueprint(controller_api, url_prefix="/api")
app.register_blueprint(visite_api, url_prefix="/api")
app.register_blueprint(dottore_api, url_prefix="/api")
app.register_blueprint(record_api, url_prefix="/api")

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)