FROM python:3.9-alpine
RUN apk --update add gcc build-base
RUN pip install --no-cache-dir kubernetes python-json-logger
ADD scheduler.py /
#CMD kopf run --namespace="default" /scheduler.py --verbose
CMD python /scheduler.py
