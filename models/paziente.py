from sqlalchemy import Table, Column, Integer, String
from sqlalchemy.orm import mapper
from database.database import metadata, db_session

class Paziente(object):
    query = db_session.query_property()

    def __init__(self, name=None, email=None):
        self.name = name
        self.email = email

    def __repr__(self):
        return f'<User {self.name!r}>'

pazienti = Table('users', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(50), unique=True),
    Column('email', String(120), unique=True)
)
mapper(Paziente, pazienti)