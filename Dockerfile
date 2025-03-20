FROM python:3.13.2

RUN mkdir /app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY spc_notifier spc_notifier

CMD ["python", "-u", "-m", "spc_notifier.main", "--loop"]
