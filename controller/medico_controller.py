from models import db
from models.medico import Medico

def crea_medico(data):
    medico = Medico(
        nome=data['nome'],
        specializzazione=data['specializzazione']
    )
    db.session.add(medico)
    db.session.commit()
    return medico

def get_medici():
    return Medico.query.all()