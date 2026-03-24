from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Patient(db.Model):
    __tablename__ = "patients"
    
    patient_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10))
    
    data_records = db.relationship("PatientData", backref="patient", lazy=True)

class PatientData(db.Model):
    __tablename__ = "patient_data"
    
    record_id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.patient_id"), nullable=False)
    data_type = db.Column(db.String(50), nullable=False)
    value = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    tx_hash = db.Column(db.String(66))  # hash Ethereum