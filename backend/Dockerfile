# Use an official Python runtime as a parent image
FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy requirements file first to leverage Docker's build cache
COPY requirements.txt .

# Install the Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Make the entrypoint script executable
RUN chmod +x /app/worker_entrypoint.sh

# The command to run will be specified in docker-compose.yml or Cloud Run