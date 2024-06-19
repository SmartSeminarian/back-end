FROM python:3.8

# set working directory
WORKDIR /code

# install requirements
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code

EXPOSE 5000

CMD ["python3", "main.py"]    