from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# =========================
# 👤 USER (AUTENTICAZIONE)
# =========================
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    wallet_address = db.Column(db.String(255), unique=True)
    email = db.Column(db.String(255), unique=True)

    password_hash = db.Column(db.String(255))

    role = db.Column(db.String(50), nullable=False)  # PATIENT, DOCTOR, AUTHORITY

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # metodi password
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# =========================
# 👤 PAZIENTI
# =========================
class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)

    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)
    data_nascita = db.Column(db.Date)

    patient_hash = db.Column(db.String(66), unique=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    visits = db.relationship('Visit', back_populates='patient', lazy=True)


# =========================
# 🧑‍⚕️ MEDICI
# =========================
class Doctor(db.Model):
    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)

    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)

    visits = db.relationship('Visit', back_populates='doctor', lazy=True)


# =========================
# 🏥 OSPEDALI
# =========================
class Hospital(db.Model):
    __tablename__ = 'hospitals'

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(255), nullable=False)
    indirizzo = db.Column(db.String(255))


# =========================
# 🩺 VISITE
# =========================
class Visit(db.Model):
    __tablename__ = 'visits'

    id = db.Column(db.Integer, primary_key=True)

    blockchain_id = db.Column(db.Integer, unique=True)

    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)

    data_hash = db.Column(db.String(66), nullable=False)
    patient_hash = db.Column(db.String(66), nullable=False)

    confirmed = db.Column(db.Boolean, default=False)

    blockchain_tx = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    records = db.relationship('Record', back_populates='visits', lazy=True)
    patient = db.relationship('Patient', back_populates='visits')
    doctor = db.relationship('Doctor', back_populates='visits')


# =========================
# 📄 RECORD
# =========================
class Record(db.Model):
    __tablename__ = 'records'

    id = db.Column(db.Integer, primary_key=True)

    blockchain_id = db.Column(db.Integer, unique=True)

    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=False, unique=True)

    authority_wallet = db.Column(db.String(255), nullable=False)

    data_hash = db.Column(db.String(66), nullable=False)

    status = db.Column(db.String(50), default='PENDING')

    approve_votes = db.Column(db.Integer, default=0)
    reject_votes = db.Column(db.Integer, default=0)

    blockchain_tx = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    probabilities = db.relationship('Probability', back_populates='record', lazy=True)
    visits = db.relationship('Visit', back_populates='records', lazy=True)


# =========================
# 📊 PROBABILITÀ
# =========================
class Probability(db.Model):
    __tablename__ = 'probabilities'

    id = db.Column(db.Integer, primary_key=True)

    blockchain_id = db.Column(db.Integer, unique=True)

    record_id = db.Column(db.Integer, db.ForeignKey('records.id'), nullable=False)

    prior = db.Column(db.Integer, nullable=False)
    posterior = db.Column(db.Integer, nullable=False)

    blockchain_tx = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    record = db.relationship('Record', back_populates='probabilities', lazy=True)


# =========================
# INIT DATABASE
# =========================
def create_app_db(app: Flask):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        print("Database creato correttamente!")


# =========================
# SEED
# =========================
def seed_data():
    print("🌱 Seeding database...")

    # =========================
    # USER
    # =========================
    u1 = User(
        wallet_address="0x1111111111111111111111111111111111111111",
        email="mario.rossi@test.com",
        role="PATIENT"
    )
    u1.set_password("password123")

    u2 = User(
        wallet_address="0x2222222222222222222222222222222222222222",
        email="luigi.verdi@test.com",
        role="PATIENT"
    )
    u2.set_password("password123")

    u3 = User(
        wallet_address="0x3333333333333333333333333333333333333333",
        email="giulia.bianchi@test.com",
        role="DOCTOR"
    )
    u3.set_password("password123")

    u4 = User(
        wallet_address="0x4444444444444444444444444444444444444444",
        email="anna.neri@test.com",
        role="DOCTOR"
    )
    u4.set_password("password123")

    db.session.add_all([u1, u2, u3, u4])
    db.session.commit()

    # =========================
    # PAZIENTI
    # =========================
    p1 = Patient(
        user_id=u1.id,
        nome="Mario",
        cognome="Rossi",
        data_nascita=date(1990, 5, 10),
        patient_hash="0x" + "a"*64
    )

    p2 = Patient(
        user_id=u2.id,
        nome="Luigi",
        cognome="Verdi",
        data_nascita=date(1985, 8, 20),
        patient_hash="0x" + "b"*64
    )

    # =========================
    # MEDICI
    # =========================
    d1 = Doctor(
        user_id=u3.id,
        nome="Giulia",
        cognome="Bianchi"
    )

    d2 = Doctor(
        user_id=u4.id,
        nome="Anna",
        cognome="Neri"
    )

    db.session.add_all([p1, p2, d1, d2])
    db.session.commit()

    print("✅ Seed completato!")