# Reuse the project's existing ROS Noetic / Gazebo image.
ARG BASE_IMAGE=docker-ros1_stack@sha256:bd7bb23f49c81b097e6d91aeed9af5373a3e7d7c90f25c40f5b6b198e7d28301
FROM ${BASE_IMAGE}
SHELL ["/bin/bash", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-noetic-turtlebot3-description ros-noetic-turtlebot3-msgs \
    ros-noetic-nlopt ros-noetic-pcl-ros ros-noetic-tf-conversions \
    libarmadillo-dev libeigen3-dev libqt5svg5-dev \
    python3-pyqt5 python3-scipy python3-shapely python3-lxml \
    python3-pandas python3-matplotlib python3-yaml python3-rospkg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /arena_ws
ENTRYPOINT ["/bin/bash"]
