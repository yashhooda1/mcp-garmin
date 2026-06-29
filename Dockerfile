FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

# Remote transport for hosted deploys (Railway/Fly/Render)
ENV TRANSPORT=streamable-http
ENV HOST=0.0.0.0
# Railway injects $PORT; default for local docker run
ENV PORT=8000
EXPOSE 8000

CMD ["garmin-mcp"]
