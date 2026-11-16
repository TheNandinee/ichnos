FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e .
COPY configs ./configs
COPY benchmarks ./benchmarks
COPY web/dist ./web/dist
COPY web/public/data ./web/public/data
EXPOSE 8000
CMD ["uvicorn", "ichnos.api:app", "--host", "0.0.0.0", "--port", "8000"]
