from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

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

def seed_data():
    print("🌱 Seeding database...")

    # =========================
    # PAZIENTI
    # =========================
    p1 = Patient(
        wallet_address="0x1111111111111111111111111111111111111111",
        nome="Mario",
        cognome="Rossi",
        data_nascita=date(1990, 5, 10),
        patient_hash="0x" + "a"*64
    )

    p2 = Patient(
        wallet_address="0x2222222222222222222222222222222222222222",
        nome="Luigi",
        cognome="Verdi",
        data_nascita=date(1985, 8, 20),
        patient_hash="0x" + "b"*64
    )

    # =========================
    # MEDICI
    # =========================
    d1 = Doctor(
        wallet_address="0x3333333333333333333333333333333333333333",
        nome="Giulia",
        cognome="Bianchi"
    )

    d2 = Doctor(
        wallet_address="0x4444444444444444444444444444444444444444",
        nome="Anna",
        cognome="Neri"
    )

    # =========================
    # OSPEDALI
    # =========================
    h1 = Hospital(
        nome="Ospedale Centrale",
        indirizzo="Via Roma 1"
    )

    h2 = Hospital(
        nome="Clinica San Marco",
        indirizzo="Via Milano 45"
    )

    db.session.add_all([p1, p2, d1, d2, h1, h2])
    db.session.commit()

    # =========================
    # VISITE
    # =========================
    v1 = Visit(
        blockchain_id=1,
        patient_id=p1.id,
        doctor_id=d1.id,
        data_hash="0x" + "c"*64,
        patient_hash=p1.patient_hash,
        confirmed=True
    )

    db.session.add(v1)
    db.session.commit()

    # =========================
    # RECORD
    # =========================
    r1 = Record(
        blockchain_id=1,
        visit_id=v1.id,
        authority_wallet="0x5555555555555555555555555555555555555555",
        data_hash="0x" + "d"*64,
        status="APPROVED",
        approve_votes=3,
        reject_votes=0
    )

    db.session.add(r1)
    db.session.commit()

    # =========================
    # PROBABILITÀ
    # =========================
    prob1 = Probability(
        blockchain_id=1,
        record_id=r1.id,
        prior=500000,
        posterior=750000
    )

    db.session.add(prob1)
    db.session.commit()

    print("✅ Seed completato!")