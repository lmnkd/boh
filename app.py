from flask import Flask, request, jsonify
from models.patient import db, Patient, PatientData
from web3 import Web3
import os

app = Flask(__name__)

# Configurazione PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@localhost/hospital'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Connessione Web3 alla blockchain locale
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:22000"))  # Cambia se necessario

# Funzione per creare tabelle
with app.app_context():
    db.create_all()

# Endpoint per aggiungere un paziente
@app.route("/add_patient", methods=["POST"])
def add_patient():
    data = request.json
    patient = Patient(
        name=data["name"],
        dob=data["dob"],
        gender=data.get("gender")
    )
    db.session.add(patient)
    db.session.commit()
    return jsonify({"message": "Patient added", "patient_id": patient.patient_id})

# Endpoint per aggiungere dati paziente
@app.route("/add_patient_data", methods=["POST"])
def add_patient_data():
    data = request.json
    patient_id = data["patient_id"]
    data_type = data["data_type"]
    value = data["value"]
    
    # Qui inserisci il dato sulla blockchain tramite smart contract
    # Per esempio:
    # contract.functions.addData(patient_id, data_type, value).transact({'from': w3.eth.accounts[0]})
    # tx_hash = ...

    # Per ora mettiamo tx_hash dummy
    tx_hash = "0x123abc..."

    record = PatientData(
        patient_id=patient_id,
        data_type=data_type,
        value=value,
        tx_hash=tx_hash
    )
    db.session.add(record)
    db.session.commit()
    return jsonify({"message": "Patient data added", "tx_hash": tx_hash})