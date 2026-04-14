from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Inizializza direttamente SQLAlchemy qui
db = SQLAlchemy()

# Definizione dei model direttamente in database.py
class Paziente(db.Model):
    __tablename__ = 'pazienti'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)
    data_nascita = db.Column(db.String(10))

class Medico(db.Model):
    __tablename__ = 'medici'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    specializzazione = db.Column(db.String(100), nullable=False)

class Appuntamento(db.Model):
    __tablename__ = 'appuntamenti'

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(20), nullable=False)
    paziente_id = db.Column(db.Integer, db.ForeignKey('pazienti.id'))
    medico_id = db.Column(db.Integer, db.ForeignKey('medici.id'))

def create_app_db(app: Flask):
    """
    Collega db all'app e crea tutte le tabelle
    """
    db.init_app(app)
    with app.app_context():
        db.create_all()
        print("Database creato correttamente!")