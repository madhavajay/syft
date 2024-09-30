# Start with the Alpine base image with Python 3
FROM python:3.12-alpine

# Set the working directory inside the container
WORKDIR /app
COPY . /app

RUN pip install uv
RUN uv venv .venv
RUN uv pip install -e .

# CMD ["ash", "/app/scripts/server.sh"]

