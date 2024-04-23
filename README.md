## Kafka Realtime Object Detection - Fastapi, Kafka, Yolo, Postgresql, Grafana

### Introduction
This project is a Kafka-based realtime object detection system. It allows you to process and analyze data in real time using Kafka streams, computer visions, Fastapi and Grafana. 

### Prerequisites
Before running the application, make sure you have the following prerequisites installed:
- Docker: [Installation Guide](https://docs.docker.com/get-docker/)

### Getting Started
1. Fork or Clone the repository:
    To clone the repository:
    ```shell
    git clone https://github.com/george-mountain/Computer-Vision-Kafka-Realtime-Object-Detection.git
    ```

2. Create a new file named `.env` in the project root directory and copy the contents of `.env-sample` to this `.env` file. Modify the credentials in the `.env` file, such as the PostgreSQL credentials, if needed.

3. Build and run the application using Docker:
    ```shell
    docker-compose up --build -d
    ```
4. To see the detection and processing in realtime from the terminal, run the docker command below after running the command on step 3 above.
     ```shell
    docker-compose up 
    ```


    Alternatively, if you have a Makefile in your PC, you can use the following commands:
    - `make build` to build the Docker containers
    - `make up-v` to run the Docker containers

### Usage
After running the application, you can access the following endpoints and URLs:

1. FastAPI Endpoints Documentation:
    [http://localhost:8000/docs](http://localhost:8000/docs)

2. Grafana URL:
    [http://127.0.0.1:3000](http://127.0.0.1:3000)

3. pgAdmin URL:
    [http://127.0.0.1:5080](http://127.0.0.1:5080)

Feel free to explore and use the application as needed!
