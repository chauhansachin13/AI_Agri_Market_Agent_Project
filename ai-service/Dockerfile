FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so the layer is cached across source changes.
COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
