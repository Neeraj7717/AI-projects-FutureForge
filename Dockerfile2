FROM python:3.11-slim-buster

WORKDIR /usr/app
COPY requirements.txt /usr/app/

RUN apt-get update && \
    apt-get install -y ffmpeg libsm6 libxext6 && \
    pip install --no-cache-dir -r requirements.txt && \
    # Add this to avoid TF warnings
    export TF_CPP_MIN_LOG_LEVEL=2

# Set environment variables to control TensorFlow behavior
ENV TF_ENABLE_ONEDNN_OPTS=0
ENV PYTHONPATH=/usr/app
ENV TF_CPP_MIN_LOG_LEVEL=2

COPY . /usr/app
CMD ["python3", "core/main.py"]