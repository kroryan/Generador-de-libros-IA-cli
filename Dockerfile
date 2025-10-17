FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para algunas librerías
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libxml2 libxml2-dev libxslt1-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de requerimientos primero para aprovechar cache de Docker
COPY requirements.txt ./

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . /app

# Crear directorio docs y usuario no root para ejecutar la app
RUN mkdir -p /app/docs
RUN useradd -m appuser || true
RUN chown -R appuser:appuser /app
USER appuser

# Puerto por defecto usado por la app
EXPOSE 5000

# No incluir .env en la imagen; el usuario debe montar uno en tiempo de ejecución
# Comando por defecto para ejecutar la interfaz web
CMD ["python", "src/app.py", "--web"]
