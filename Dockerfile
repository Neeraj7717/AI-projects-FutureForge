# Use a base image with compatible CUDA and cuDNN versions
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu20.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /usr/app

# Install system dependencies including GStreamer components
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libsm6 \
        libxext6 \
        python3-pip \
        python3-dev \
        wget \
        git \
        libglib2.0-0 \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install compatible TensorFlow version with CUDA 11.8
RUN pip3 install --no-cache-dir --upgrade pip 

# Install any other requirements if needed
COPY requirements.txt /usr/app/
RUN pip3 install --no-cache-dir -r requirements.txt 

# Set environment variables for TensorFlow and CUDA
ENV PYTHONPATH=/usr/app

# Set TensorFlow to dynamically allocate GPU memory
ENV TF_FORCE_GPU_ALLOW_GROWTH=true
ENV PYTHONUNBUFFERED=1

# Copy project files
COPY . /usr/app

# Run the application
CMD ["python3", "core/main_test.py"]
