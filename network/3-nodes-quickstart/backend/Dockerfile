FROM python:3.11

WORKDIR /app

# Installa dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice
COPY . .

EXPOSE 5000

CMD ["python", "app.py"]