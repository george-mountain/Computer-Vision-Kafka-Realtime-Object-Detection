from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pydantic import BaseModel
from helpers.utilities import ObjectProcessor, KafkaManager
from helpers.models import Models
from sqlalchemy import create_engine
import json
import pandas as pd
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

app = FastAPI(title="Realtime Detection", version="1.0.0")

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bootstrap_servers = "kafka:9092"

# PostgreSQL configuration
db_url = "postgresql://postgresuser:postgrespass@postgres:5432/testdb"

# Initialize ObjectProcessor
processor = ObjectProcessor()

# Initialize KafkaProducer
producer = KafkaProducer(
    bootstrap_servers=["kafka:9092"],
    value_serializer=lambda x: json.dumps(x).encode("utf-8"),
)

# Initialize KafkaManager
kafka_manager = KafkaManager(bootstrap_servers)


@app.post("/start-detection")
def start_detection(
    background_tasks: BackgroundTasks, request_body: Models.DetectionRequest
):
    topic = request_body.topic
    links = request_body.links
    live = request_body.live
    saving_timer = request_body.saving_timer

    kafka_manager.create_topic(topic)
    data = {
        "status": "Process started",
        "topic": topic,
        "links": links,
        "live": live,
        "saving_timer": saving_timer,
    }
    print(f"Data: {data}")
    print("*" * 50)
    background_tasks.add_task(
        processor.process, producer, topic, links, live, saving_timer
    )
    return {"status": "Process started"}


@app.get("/stop-detection")
def stop_detection():
    processor.stop()
    return {"status": "Process stopped"}


@app.post("/consume-data")
async def consume_data(request_body: Models.ConsumeDataRequest):
    topic = request_body.topic
    limit = request_body.limit
    try:
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        )

        messages = []

        for message in consumer:
            messages.append(message.value)
            print(f"Received message: {message.value}")

            if len(messages) >= limit:
                kafka_manager.process_and_store(db_url, messages)
                return {"status": "Data consumed and processed", "message": messages}
    except KafkaError as e:
        print(f"KafkaError occurred: {e}")
        return {"error": f"KafkaError occurred: {e}"}
    except Exception as ex:
        print(f"Error occurred: {ex}")
        return {"error": f"Error occurred: {ex}"}


@app.post("/start-writing-to-database")
def start_writing_to_database(
    background_tasks: BackgroundTasks,
    request_body: Models.StartWritingToDatabaseRequest,
):
    topic = request_body.topic
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )

    background_tasks.add_task(
        kafka_manager.continuous_write_to_database, consumer, db_url
    )
    return {"status": "Writing to database started"}


@app.get("/stop-writing-to-database")
def stop_writing_to_database():
    kafka_manager.stop_writing_to_database()
    return {"status": "Writing to database stopped"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
