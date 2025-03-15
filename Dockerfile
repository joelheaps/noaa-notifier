FROM python:3.13.2

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY spc_notifier/ .
COPY config.toml .

CMD ["python", "-u", "-m", "spc_notifier.main", "--loop"]
