FROM ubuntu:14.04

RUN apt-get update && apt-get -y upgrade
RUN apt-get install -y supervisor
RUN mkdir -p /var/log/supervisor

ADD login.defs /etc/login.defs

RUN mkdir -p /opt/microservices
ADD start_all.sh /opt/microservices/start_all.sh
RUN chmod a+x /opt/microservices/start_all.sh

ADD gremlinproxy /opt/microservices/gremlinproxy
ADD gatewayconfig.json /opt/microservices/gatewayconfig.json
ADD gremlingateway-supervisor.conf /etc/supervisor/conf.d/gremlingateway.conf

EXPOSE 9080 9876
WORKDIR /opt/microservices


CMD ["/opt/microservices/start_all.sh"]
