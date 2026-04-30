FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/docker/hermes-worker/entrypoint.sh

EXPOSE 3000

ENTRYPOINT ["/app/docker/hermes-worker/entrypoint.sh"]
