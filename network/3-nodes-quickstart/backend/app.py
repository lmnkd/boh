from flask import Flask, jsonify, render_template, request
from flask import session, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from web3 import Web3
from blockchain.config import w3
from blockchain.contract import get_contract
from blockchain.deploy import deploy_contract
from database.database import create_app_db, db, seed_data, Patient, Visit, Doctor, Admin
import os
import time
from controller.controller import api as controller_api
from controller.controller_visite import api as visite_api
from controller.controller_dottore import api as dottore_api
from controller.auth import auth
from dotenv import load_dotenv

app = Flask(__name__)

load_dotenv()

# Configurazione PostgreSQL (da variabili d'ambiente)
DATABASE_URI = os.getenv(
    'DATABASE_URI',
    'postgresql://quorum:quorumpass@postgres:5432/quorumdb'
)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")


# Inizializza DB
create_app_db(app)

with app.app_context():
    try:
        existing = db.session.execute(text("SELECT 1 FROM doctors LIMIT 1")).fetchone()
        if not existing:
            seed_data()
    except Exception:
        seed_data()

@app.route("/")
def test():
    # Test DB with retry
    db_status = "ERROR: Connection failed"
    for attempt in range(5):  # Retry up to 5 times
        try:
            db.session.execute(text('SELECT 1'))
            db_status = "OK"
            break
        except Exception as e:
            db_status = f"ERROR: {str(e)}"
            if attempt < 4:  # Wait before retrying (except last attempt)
                time.sleep(4)  # 4-second delay

    # Test Blockchain
    try:
        block = w3.eth.get_block_number()
        bc_status = f"OK - current block: {block}"
    except Exception as e:
        bc_status = f"ERROR: {str(e)}"

    return render_template("pagina_iniziale.html", db_status=db_status, bc_status=bc_status)

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

@app.route("/contract/deploy", methods=["POST"])
def deploy():
    """
    Deploya lo smart contract HealthDataValidator.
    
    Parametri opzionali (JSON):
    - validators: array di indirizzi (se non fornito, usa gli account del nodo)
    """
    try:
        # Ottieni i validatori dal body o usa gli account del nodo
        data = request.get_json() or {}
        validators = data.get("validators")
        
        if not validators:
            # Usa gli account disponibili dal nodo Quorum
            validators = w3.eth.accounts
            if not validators:
                return jsonify({
                    "status": "ERROR",
                    "message": "❌ Nessun account disponibile nel nodo"
                }), 400
        
        # Converti a checksum addresses
        validators = [Web3.to_checksum_address(v) for v in validators]
        
        print(f"📝 Deploying contract con validatori: {validators}")
        
        # Deploy il contratto
        address = deploy_contract(validators)
        
        return jsonify({
            "status": "SUCCESS",
            "message": "✅ Contratto deployato con successo",
            "address": address,
            "validators": validators
        }), 201
        
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": f"❌ Errore durante il deploy: {str(e)}"
        }), 500

@app.route("/registrazione_dottore")
def registrazione_dottore():
    return render_template("registrazione_dottore.html")

@app.route("/patient")
def patient_dashboard():
    if session.get("role") != "PATIENT":
        return redirect("/")
    # return render_template("patient.html")
    patient = Patient.query.filter_by(user_id=session["user_id"]).first()
    if not patient:
        return redirect("/")
    visits = patient.visits
    return render_template("patient.html", patient=patient, visits=visits)

@app.route("/doctor")
def doctor_dashboard():
    #return render_template("doctor.html")
    if session.get("role") != "DOCTOR":
        return redirect("/")
    doctor = Doctor.query.filter_by(user_id=session["user_id"]).first()
    if not doctor:
        return redirect("/")
    visits = doctor.visits
    patients = Patient.query.all()  # Per selezionare pazienti nella creazione visita
    return render_template("doctor.html", doctor=doctor, visits=visits, patients=patients)

@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "ADMIN":
        return redirect("/")
    admin = Admin.query.filter_by(user_id=session["user_id"]).first()
    if not admin:
        return redirect("/")
    visits = Visit.query.all()
    return render_template("admin.html", admin=admin, visits=visits)

app.register_blueprint(auth, url_prefix="/auth")
app.register_blueprint(controller_api, url_prefix="/api")
app.register_blueprint(visite_api, url_prefix="/api")
app.register_blueprint(dottore_api, url_prefix="/api")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)