from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# =========================
# 👤 USER (AUTH)
# =========================
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    wallet_address = db.Column(db.String(255), unique=True)
    email = db.Column(db.String(255), unique=True, nullable=False)

    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(50), nullable=False)  # PATIENT, DOCTOR, AUTHORITY

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relations
    patient = db.relationship('Patient', backref='user', uselist=False)
    doctor = db.relationship('Doctor', backref='user', uselist=False)
    admin = db.relationship('Admin', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# =========================
# 👤 PATIENT
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
# 🧑‍⚕️ DOCTOR
# =========================
class Doctor(db.Model):
    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)

    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)

    visits = db.relationship('Visit', back_populates='doctor', lazy=True)


# =========================
# 🏥 Autorità
# =========================
class Admin(db.Model):
    __tablename__ = 'admins'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)

    nome = db.Column(db.String(255), nullable=False)
    indirizzo = db.Column(db.String(255))


# =========================
# 🩺 VISIT
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

    # relations
    patient = db.relationship('Patient', back_populates='visits')
    doctor = db.relationship('Doctor', back_populates='visits')
    records = db.relationship('Record', back_populates='visit', lazy=True)


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

    # relations
    visit = db.relationship('Visit', back_populates='records')
    probabilities = db.relationship('Probability', back_populates='record', lazy=True)


# =========================
# 📊 PROBABILITY
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

    record = db.relationship('Record', back_populates='probabilities')


# =========================
# INIT DB
# =========================
def create_app_db(app: Flask):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        print("✅ Database creato correttamente!")


# =========================
# SEED (ESEMPIO)
# =========================
def seed_data():
    print("🌱 Seeding database...")

    u1 = User(
        wallet_address="0x1111111111111111111111111111111111111111",
        email="mario.rossi@test.com",
        role="PATIENT"
    )
    u1.set_password("password123")

    u2 = User(
        wallet_address="0x2222222222222222222222222222222222222222",
        email="luigi.verdi@test.com",
        role="DOCTOR"
    )
    u2.set_password("password123")

    u3 = User(
        wallet_address="0x7777777777777777777777777777777777777777",
        email="autorita@test.com",
        role="ADMIN"
    )
    u3.set_password("password123")

    db.session.add_all([u1, u2, u3])
    db.session.commit()

    p1 = Patient(
        user_id=u1.id,
        nome="Mario",
        cognome="Rossi",
        data_nascita=date(1990, 5, 10),
        patient_hash="0x" + "a"*64
    )

    d1 = Doctor(
        user_id=u2.id,
        nome="Luigi",
        cognome="Verdi"
    )

    a1 = Admin(
        user_id=u3.id,
        nome="Autorita",
        indirizzo="Via Roma 123, Milano"
    )

    db.session.add_all([p1, d1, a1])
    db.session.commit()

    print("✅ Seed completato!")