# Start with the Alpine base image with Python 3
FROM python:3.12-alpine

# Set the working directory inside the container
WORKDIR /app

# Install any required Python packages

COPY ./syftbox-0.1.0-py3-none-any.whl /app

RUN pip install uv
RUN uv pip install opendp==0.11.1 --system
RUN uv pip install pandas==2.2.2 --system
RUN uv pip install ./syftbox-0.1.0-py3-none-any.whl --system

COPY . /app

# # Specify the default command to run your Python application
CMD ["/bin/sh", "/app/run.sh"]


# add requirements.txt?
# docker run -it -v /tmp/output:/app/outputs/result -v /Users/madhavajay/dev/syft/users/madhava/me@madhavajay.com/datasets/trade_mock.csv:/app/inputs/trade_data/trade_mock.csv myanalysis