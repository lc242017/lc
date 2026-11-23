FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir --timeout 120 --retries 8 \
      streamlit==1.38.0 \
      pandas==2.2.2

COPY . /app

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.address", "0.0.0.0", "--server.port", "8501", \
     "--server.headless", "true"]
