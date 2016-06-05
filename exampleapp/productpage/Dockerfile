FROM ubuntu:14.04

RUN apt-get update && apt-get -y upgrade
RUN apt-get install python-pip python-dev wget -y
RUN pip install flask flask_json json2html simplejson gevent
RUN pip install flask-bootstrap
RUN pip install gunicorn

RUN apt-get install -y supervisor
RUN mkdir -p /var/log/supervisor

ADD login.defs /etc/login.defs

RUN mkdir -p /opt/microservices
ADD start_all.sh /opt/microservices/start_all.sh
RUN chmod a+x /opt/microservices/start_all.sh

ADD gremlinproxy /opt/microservices/gremlinproxy
ADD proxyconfig.json /opt/microservices/proxyconfig.json
ADD gremlinproduct-supervisor.conf /etc/supervisor/conf.d/gremlinproxy.conf

ADD templates /opt/microservices/templates
ADD productpage-supervisor.conf /etc/supervisor/conf.d/productpage.conf
ADD productpage.py /opt/microservices/productpage.py

#WORKDIR /opt
#RUN wget ftp://public.dhe.ibm.com/cloud/bluemix/containers/logstash-mtlumberjack.tgz && \
#        tar -xzf logstash-mtlumberjack.tgz
#ADD logstash.conf /opt/logstash/conf.d/
#ADD supervisord.conf /etc/supervisor/conf.d/supervisord.conf


EXPOSE 9080 9876
WORKDIR /opt/microservices


CMD ["/opt/microservices/start_all.sh"]
