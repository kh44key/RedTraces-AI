FROM python:3.12-slim
WORKDIR /app
COPY docker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY docker/collectors/ /app/
RUN mkdir /data
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "unified_cti_api:app", "--host", "0.0.0.0", "--port", "8100"]
