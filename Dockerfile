FROM mcr.microsoft.com/playwright/python:v1.58.0

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

VOLUME [ "/data" ]

COPY . .
CMD [ "python3", "-u", "main.py" ]
