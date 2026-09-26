FROM python:3.12-slim
WORKDIR /app
COPY . .
CMD ["python", "src/server.py"]
