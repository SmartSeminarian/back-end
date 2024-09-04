FROM python:3.11

WORKDIR /app

# Install system dependencies including CMake
RUN apt-get update && apt-get install -y \
    htop \
    vim \
    git \
    net-tools \
    psmisc \
    curl \
    build-essential \
    libssl-dev \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY ./app /app/
COPY setup.cfg /app/
RUN mkdir -p /data

# Upgrade pip
RUN pip3 install --upgrade pip

# Install requirements without static OpenSSL linking
RUN pip3 install --root-user-action=ignore -r /app/requirements.txt

# Clean up
RUN apt-get clean

# Use JSON array format for ENTRYPOINT
ENTRYPOINT ["/app/entrypoint.sh"]