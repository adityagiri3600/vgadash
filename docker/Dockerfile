FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    python3 python3-pip \
    qemu-system-x86 \
    busybox-static \
    cpio \
    && rm -rf /var/lib/apt/lists/*

# Install a kernel + headers inside the image so kver detection works.
# Using meta packages avoids “pinned version not found” problems.
RUN apt-get update && apt-get install -y \
    linux-image-generic linux-headers-generic \
    && rm -rf /var/lib/apt/lists/*

# Optional: for RabbitMQ publishing of test results
RUN pip3 install --no-cache-dir pika

WORKDIR /work
