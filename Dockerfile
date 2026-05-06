FROM python:slim

WORKDIR /usr/src/app

COPY ./requirements.txt .

RUN pip install -i https://pypi.devneeds.ir/simple/ --no-cache-dir --upgrade -r requirements.txt

COPY ./app .