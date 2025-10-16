FROM python:slim

WORKDIR /app

COPY main.py .
COPY requirements.txt .

RUN pip install -r requirements.txt

CMD ["python", "main.py"]