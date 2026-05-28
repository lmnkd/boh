from flask import Blueprint, request, jsonify, session
from database.database import User
from werkzeug.security import check_password_hash

auth = Blueprint("auth", __name__)

# =========================
# LOGIN CON PASSWORD
# =========================
@auth.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Credenziali non valide"}), 401

    # QUI INSERISCI LA SESSIONE
    session["user_id"] = user.id
    session["role"] = user.role

    return jsonify({
        "message": "Login OK",
        "role": user.role
    }), 200


