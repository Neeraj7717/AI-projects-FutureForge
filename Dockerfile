FROM python:3.11-slim-buster

WORKDIR /usr/app
COPY requirements.txt /usr/app/

RUN apt-get update && \
    apt-get install -y ffmpeg libsm6 libxext6 && \
    pip install --no-cache-dir -r requirements.txt

COPY . /usr/app
ENV PYTHONPATH /usr/app
CMD ["python3","core/main.py"]