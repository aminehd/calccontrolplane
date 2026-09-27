FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir grpcio xds-protos
COPY src/ src/
COPY config/ config/
ENV PYTHONPATH=/app/src
RUN python -c "from lib import xds; from envoy.config.core.v3 import base_pb2; print('imports ok')"
CMD ["python", "-u", "src/cmd/server.py"]
