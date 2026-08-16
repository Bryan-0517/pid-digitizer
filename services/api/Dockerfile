FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
ARG INSTALL_PYDEXPI=false
RUN if [ "$INSTALL_PYDEXPI" = "true" ]; then pip install --no-cache-dir '.[pydexpi]'; else pip install --no-cache-dir .; fi
COPY app ./app
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
