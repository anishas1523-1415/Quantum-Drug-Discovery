FROM python:3.12-slim

# qiskit/scipy/rustworkx pull in a couple of packages without linux
# wheels for every platform combo; build-essential covers the fallback
# sdist-compile path so the image build doesn't depend on wheel luck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads processed

ENV PYTHONUNBUFFERED=1 \
    FLASK_DEBUG=false

EXPOSE 5000

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "app:app"]
