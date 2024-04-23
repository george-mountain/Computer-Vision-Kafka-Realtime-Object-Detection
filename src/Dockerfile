FROM ultralytics/ultralytics:8.1.1
WORKDIR /code/
COPY requirements.txt /code/
RUN pip install -r requirements.txt
RUN apt-get update --allow-releaseinfo-change && apt-get install -y netcat
COPY . /code
COPY app.py /code/app.py