from fastapi import FastAPI, BackgroundTasks
from typing import List
from helpers.utilities import ObjectProcessor, KafkaManager
from sqlalchemy import create_engine
import json
import pandas as pd
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

app = FastAPI()


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
def start_process(
    background_tasks: BackgroundTasks,
    topic: str,
    links: List[str],
    live: bool,
    saving_timer: int,
):
    # Create a new topic using KafkaManager
    kafka_manager.create_topic(topic)

    # Add task to background tasks
    background_tasks.add_task(
        processor.process, producer, topic, links, live, saving_timer
    )
    return {"status": "Process started"}


@app.get("/stop-detection")
def stop_process():
    processor.stop()
    return {"status": "Process stopped"}


@app.post("/consume-data")
async def consume_data(topic: str, limit: int):
    try:
        # Create a Kafka consumer
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        )

        # Create an empty list to store the received messages
        messages = []

        # Consume messages from Kafka
        for message in consumer:
            messages.append(message.value)
            print(f"Received message: {message.value}")

            # Process messages in batches of 'limit'
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
    topic: str,
):
    # Create a Kafka consumer
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )

    background_tasks.add_task(
        kafka_manager.continuous_write_to_database, consumer, db_url
    )
    return {"status": "Writing to database started"}


@app.post("/stop-writing-to-database")
def stop_writing_to_database():
    kafka_manager.stop_writing_to_database()
    return {"status": "Writing to database stopped"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
