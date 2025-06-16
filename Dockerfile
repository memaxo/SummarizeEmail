# Use an official Python runtime as a parent image
# Using python:3.11-slim for a smaller image size
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables to prevent Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE 1
# Ensure that Python output is sent straight to the terminal without buffering
ENV PYTHONUNBUFFERED 1

# Install minimal system dependencies (curl is required for the container
# healthcheck defined in docker-compose.yml)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install pipenv for dependency management
RUN pip install --upgrade pip

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir disables the cache which is not needed in a container image
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY ./app /app/app

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define the command to run the application using uvicorn
# We bind to 0.0.0.0 to allow traffic from outside the container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 