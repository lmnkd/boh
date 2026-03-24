import psycopg2

conn = psycopg2.connect(
    dbname="postgres",
    user="postgres",
    password="password",  # metti la tua password reale
    host="localhost"
)

conn.autocommit = True
cur = conn.cursor()

# Creazione database
try:
    cur.execute("CREATE DATABASE hospital;")
except Exception as e:
    print("Database già esistente")

# Creazione utente
try:
    cur.execute("CREATE USER hospital_user WITH PASSWORD 'password123';")
except Exception as e:
    print("Utente già esistente")

# Permessi
cur.execute("GRANT ALL PRIVILEGES ON DATABASE hospital TO hospital_user;")

cur.close()
conn.close()

print("Database pronto ✅")