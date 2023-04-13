# Use the official Python base image
FROM python:3.11

# Set the working directory
WORKDIR /app

# Set the environment variables
ENV FLASK_APP=web/app.py

# Copy the Pipfile and Pipfile.lock files into the container
COPY Pipfile Pipfile.lock ./

# Install pipenv
RUN pip install --no-cache-dir pipenv

# Install the Python dependencies
RUN pipenv install --system --deploy --ignore-pipfile

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app will run on
EXPOSE 8080

# Start the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
