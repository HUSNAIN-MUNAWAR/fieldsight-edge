FROM python:3.12-slim
WORKDIR /agent
COPY agent.py .
CMD ["python", "agent.py", "--api", "http://api:8000", "--device", "edge-03"]
