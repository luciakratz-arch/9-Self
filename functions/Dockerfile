FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir flask pillow qrcode functions-framework firebase-admin firebase-functions reportlab google-cloud-firestore google-cloud-storage
CMD ["python", "main_run.py"]
