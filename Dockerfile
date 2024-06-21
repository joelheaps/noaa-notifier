# Use an official Python runtime as the base image
FROM python:3.11

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file to the working directory
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the notifier.py file to the working directory
COPY src/forecast_discussion_notifier .

# Set the command to run when the container starts
CMD ["python", "-u", "-m", "forecast_discussion_notifier.app"]