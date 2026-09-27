FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir grpcio xds-protos
COPY src/ src/
COPY config/ config/
ENV PYTHONPATH=/app/src
CMD ["python", "-u", "src/server.py"]
