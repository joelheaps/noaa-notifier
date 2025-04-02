FROM python:3.13.2

RUN mkdir /app
WORKDIR /app

COPY pyproject.toml .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir .

COPY spc_notifier spc_notifier

CMD ["python", "-u", "-m", "spc_notifier.main", "--loop"]
