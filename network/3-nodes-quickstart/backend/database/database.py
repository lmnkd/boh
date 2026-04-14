from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# =========================
# 👤 PAZIENTI
# =========================
class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)

    wallet_address = db.Column(db.String(255), unique=True, nullable=False)

    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)
    data_nascita = db.Column(db.Date)

    # hash identificativo (match bytes32 on-chain)
    patient_hash = db.Column(db.String(66), unique=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    visits = db.relationship('Visit', backref='patient', lazy=True)


# =========================
# 🧑‍⚕️ MEDICI
# =========================
class Doctor(db.Model):
    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True)

    wallet_address = db.Column(db.String(255), unique=True, nullable=False)

    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)

    visits = db.relationship('Visit', backref='doctor', lazy=True)


# =========================
# 🏥 OSPEDALI
# =========================
class Hospital(db.Model):
    __tablename__ = 'hospitals'

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(255), nullable=False)
    indirizzo = db.Column(db.String(255))


# =========================
# 🩺 VISITE (STEP 1-2)
# =========================
class Visit(db.Model):
    __tablename__ = 'visits'

    id = db.Column(db.Integer, primary_key=True)

    # ID della blockchain
    blockchain_id = db.Column(db.Integer, unique=True)

    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)

    # hash dati visita (bytes32 → hex string)
    data_hash = db.Column(db.String(66), nullable=False)

    # hash paziente (match smart contract)
    patient_hash = db.Column(db.String(66), nullable=False)

    confirmed = db.Column(db.Boolean, default=False)

    blockchain_tx = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    records = db.relationship('Record', backref='visit', lazy=True)


# =========================
# 📄 RECORD VALIDATI (STEP 3-4)
# =========================
class Record(db.Model):
    __tablename__ = 'records'

    id = db.Column(db.Integer, primary_key=True)

    blockchain_id = db.Column(db.Integer, unique=True)

    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=False, unique=True)

    authority_wallet = db.Column(db.String(255), nullable=False)

    data_hash = db.Column(db.String(66), nullable=False)

    status = db.Column(db.String(50), default='PENDING')  # PENDING, APPROVED, REJECTED

    approve_votes = db.Column(db.Integer, default=0)
    reject_votes = db.Column(db.Integer, default=0)

    blockchain_tx = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    probabilities = db.relationship('Probability', backref='record', lazy=True)


# =========================
# 📊 PROBABILITÀ BAYESIANE (STEP 5)
# =========================
class Probability(db.Model):
    __tablename__ = 'probabilities'

    id = db.Column(db.Integer, primary_key=True)

    blockchain_id = db.Column(db.Integer, unique=True)

    record_id = db.Column(db.Integer, db.ForeignKey('records.id'), nullable=False)

    prior = db.Column(db.Integer, nullable=False)      # x10^6
    posterior = db.Column(db.Integer, nullable=False)  # x10^6

    blockchain_tx = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# INIT DATABASE
# =========================
def create_app_db(app: Flask):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        print("Database creato correttamente!")