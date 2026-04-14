from models import db
from models.paziente import Paziente

def crea_paziente(data):
    paziente = Paziente(
        nome=data['nome'],
        cognome=data['cognome'],
        data_nascita=data['data_nascita']
    )
    db.session.add(paziente)
    db.session.commit()
    return paziente

def get_pazienti():
    return Paziente.query.all()