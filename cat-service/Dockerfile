FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY window.py rules.py cat.py ./
CMD ["python", "-u", "cat.py"]
