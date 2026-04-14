from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from web3 import Web3
from database.database import create_app_db, db
import time

app = Flask(__name__)

# Configurazione PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://quorum:quorumpass@postgres:5432/quorumdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inizializza DB
create_app_db(app)

# Connessione Web3
w3 = Web3(Web3.HTTPProvider("http://node1:8545"))

@app.route("/")
def test():
    # Test DB with retry
    db_status = "ERROR: Connection failed"
    for attempt in range(5):  # Retry up to 5 times
        try:
            db.session.execute(text('SELECT 1'))
            db_status = "OK"
            break
        except Exception as e:
            db_status = f"ERROR: {str(e)}"
            if attempt < 4:  # Wait before retrying (except last attempt)
                time.sleep(4)  # 4-second delay

    # Test Blockchain
    try:
        block = w3.eth.get_block_number()
        bc_status = f"OK - current block: {block}"
    except Exception as e:
        bc_status = f"ERROR: {str(e)}"

    return jsonify({
        "database": db_status,
        "blockchain": bc_status
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)