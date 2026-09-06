FROM python:3.12-slim
LABEL name="cgv-open-push-v2"
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py config.example.json ./
ENV TZ=Asia/Seoul
EXPOSE 5000
# config.json / state.json / 로그는 볼륨으로 마운트해서 유지: -v $(pwd)/v2:/app
ENTRYPOINT ["python", "main.py"]
CMD ["run"]
