FROM python:3.11

WORKDIR /app

RUN apt-get update

## Not nessesary but useful for the debug
RUN apt-get install -y htop vim git net-tools psmisc curl

COPY ./app /app/
RUN mkdir -p /data

RUN pip3 install --upgrade pip

RUN pip3 install --root-user-action=ignore -r /app/requirements.txt

RUN apt-get clean

ENTRYPOINT /app/entrypoint.sh
