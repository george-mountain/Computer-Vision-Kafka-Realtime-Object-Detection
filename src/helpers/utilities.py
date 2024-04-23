import threading
import json
import cv2
import logging
import datetime
import pandas as pd
import torch
from ultralytics import YOLO
from cap_from_youtube import cap_from_youtube
import pafy
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from sqlalchemy import create_engine

from kafka.errors import KafkaError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("kafka-producer")

db_config = {
    "host": "postgresql",
    "port": "5433",
    "database": "testdb",
    "user": "postgresuser",
    "password": "postgrespass",
}


class ObjectProcessor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.continue_processing = True
        self.model = YOLO("yolov8n.pt")
        self.lock = threading.Lock()

    def stop(self):
        self.continue_processing = False

    def calculate_bounding_box_percentage(self, bbox, original_shape):
        bbox_area = (bbox["x2"] - bbox["x1"]) * (bbox["y2"] - bbox["y1"])
        original_shape_area = original_shape[0] * original_shape[1]
        percentage = (bbox_area / original_shape_area) * 100
        return percentage

    def save_dataframe(self, df, filename):
        csv_filename = f"{filename}.csv"
        df.to_csv(csv_filename, index=False)
        excel_filename = f"{filename}.xlsx"
        df.to_excel(excel_filename, index=False)

    def detection_results_report(self, df, filename):
        if (
            "track_id" in df.columns
            and df["track_id"].notna().any()
            and df["track_id"].ne(0).any()
        ):
            df_filtered = df[(df["track_id"] != 0) & (df["track_id"].notna())].copy()
            summary_df = (
                df_filtered.groupby("track_id")
                .agg(
                    average_box_percentage=("box_percentage", "mean"),
                    min_timestamp=("timestamp", "min"),
                    max_timestamp=("timestamp", "max"),
                    most_common_class=(
                        "name",
                        lambda x: x.value_counts().index[0],
                    ),
                )
                .reset_index()
            )
            summary_df["max_timestamp"] = pd.to_datetime(summary_df["max_timestamp"])
            summary_df["min_timestamp"] = pd.to_datetime(summary_df["min_timestamp"])
            summary_df["duration"] = (
                summary_df["max_timestamp"] - summary_df["min_timestamp"]
            )
            self.save_dataframe(summary_df, "summary_results")
            output_string = "\n".join(
                f"{row['most_common_class']} with id {row['track_id']} was present in the video for {row['duration']} from {row['min_timestamp']} to {row['max_timestamp']} and was taking  {row['average_box_percentage']:.2f}% of the screen"
                for _, row in summary_df.iterrows()
            )
            with open(filename, "w") as f:
                f.write(output_string)
        else:
            output_string = "No objects were detected in the video"

    def on_send_success(self, record_metadata):
        log.info(
            f"Message sent to {record_metadata.topic} on partition {record_metadata.partition} with offset {record_metadata.offset}"
        )

    def on_send_error(self, excp):
        log.error("Error sending message", exc_info=excp)

    def process_single_link(self, producer, topic, link, live, saving_timer):
        try:
            if not live:
                cap = cap_from_youtube(link, "720p")
            if live and ("rtsp" in link or "rtmp" in link or "tcp" in link):
                cap = cv2.VideoCapture(link)
            elif live:
                video = pafy.new(link)
                best = video.getbest(preftype="mp4")
                cap = cv2.VideoCapture(best.url)

            all_results = []
            timestamp = datetime.datetime.now()
            last_save_time = timestamp
            filename = (
                link.split("=")[-1]
                + "_"
                + str(timestamp.time().strftime("%Y-%m-%d-%H-%M-%S"))
            )
            while self.continue_processing:
                while cap.isOpened():
                    success, frame = cap.read()
                    if success:
                        results = self.model.track(
                            frame, persist=True, device=self.device
                        )
                        timestamp = datetime.datetime.now()
                        for box in json.loads(results[0].tojson()):
                            box["input"] = link
                            box["timestamp"] = timestamp.isoformat()
                            box["date"] = timestamp.strftime("%Y-%m-%d")
                            box["time"] = timestamp.time().strftime("%H:%M:%S")
                            box["origin_shape"] = results[0].orig_shape
                            box["box_percentage"] = (
                                self.calculate_bounding_box_percentage(
                                    box["box"], results[0].orig_shape
                                )
                            )
                            box["full_process_speed"] = sum(results[0].speed.values())
                            all_results.append(box)
                            future = producer.send(topic, box)
                            future.add_callback(self.on_send_success).add_errback(
                                self.on_send_error
                            )
                            current_time = datetime.datetime.now()
                            if (
                                current_time - last_save_time
                            ).total_seconds() >= saving_timer * 60:
                                df = pd.DataFrame(all_results)
                                self.save_dataframe(df, filename)
                                self.detection_results_report(df, filename)
                                last_save_time = current_time
                    if not self.continue_processing or not success:
                        df = pd.DataFrame(all_results)
                        self.save_dataframe(df, filename)
                        self.detection_results_report(df, filename)
                        break
                if not self.continue_processing:
                    break
        except Exception as e:
            logging.error(f"Error processing link {link}: {e}")

    def process(self, producer, topic, links, live, saving_timer):
        self.continue_processing = True
        threads = []
        for link in links:
            thread = threading.Thread(
                target=self.process_single_link,
                args=(producer, topic, link, live, saving_timer),
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()


class KafkaManager:
    def __init__(self, bootstrap_servers):
        self.writing_to_database = False
        self.bootstrap_servers = bootstrap_servers
        self.admin_client = KafkaAdminClient(bootstrap_servers=self.bootstrap_servers)

    def stop_writing_to_database(self):
        self.writing_to_database = False

    def create_topic(self, topic_name, partitions=1, replication_factor=1):
        topic = NewTopic(
            name=topic_name,
            num_partitions=partitions,
            replication_factor=replication_factor,
        )
        try:
            self.admin_client.create_topics([topic])
            print(f"Topic '{topic_name}' created successfully!")
        except TopicAlreadyExistsError:
            print(f"Topic '{topic_name}' already exists.")

    def list_topics(self):
        topics = self.admin_client.list_topics()
        print("List of topics:")
        for topic in topics:
            print(topic)

    def process_and_store(self, db_url, messages):
        df = pd.DataFrame(messages)

        # Convert 'box' dictionary into a JSON string
        df["box"] = df["box"].apply(json.dumps)

        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Write DataFrame to PostgreSQL database
        engine = create_engine(db_url)
        df.to_sql("object_detection", engine, if_exists="append", index=False)

        print("Data written to PostgreSQL")

    def continuous_write_to_database(self, consumer, db_url):
        self.writing_to_database = True
        while self.writing_to_database:
            try:
                messages = []
                for message in consumer:
                    messages.append(message.value)
                    self.process_and_store(db_url, messages)
                    print(f"Data consumed and written to database: {messages}")
                    print("*" * 50)
                    messages = []  # Reset messages for next batch
            except KafkaError as e:
                print(f"KafkaError occurred: {e}")
            except Exception as ex:
                print(f"Error occurred: {ex}")
