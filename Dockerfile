FROM python:3.11-slim

WORKDIR /app

# Install dependencies before copying source for better layer caching
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "fastapi>=0.111.0" \
    "uvicorn[standard]>=0.29.0" \
    "supabase>=2.4.0" \
    "httpx>=0.27.0" \
    "beautifulsoup4>=4.12.0" \
    "python-dotenv>=1.0.0" \
    "email-validator>=2.1.0" \
    "jsonschema>=4.22.0"

COPY api/ api/

RUN addgroup --system appuser && adduser --system --ingroup appuser appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
