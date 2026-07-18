FROM python:3.11-slim

# Install native build dependencies.
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libxml2 libxml2-dev libxslt1-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Application working directory.
WORKDIR /app

# Copy dependencies first to preserve the build cache.
COPY requirements.txt ./

# Install Python dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application.
COPY . /app

# Run as a non-root user and retain generated projects in /app/books.
RUN mkdir -p /app/books
RUN useradd -m appuser || true
RUN chown -R appuser:appuser /app
USER appuser

# Web interface port.
EXPOSE 5000

# Mount .env at runtime; never bake secrets into the image.
CMD ["python", "src/app.py", "--web"]
