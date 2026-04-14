from network import db

class Medico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    specializzazione = db.Column(db.String(100))