FROM python:3.11

WORKDIR /home/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh
RUN sed -i 's/\r$//' entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]