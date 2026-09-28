FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
COPY config/ config/
ENV PYTHONPATH=/app/src
RUN python -c "import envoycontrolplane.server, envoycontrolplane.syncer, envoydataplane.external_processor; print('imports ok')"
CMD ["python", "-u", "-m", "envoycontrolplane.server"]
