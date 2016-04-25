# Gremlin - Systematic Resiliency Testing of Microservices

Gremlin is a resiliency testing framework that enables developers to
systematically test the ability of their microservices to recover from
custom designed failure scenarios. This SDK is a set of abstractions
that enable developers to build and execute custom failure scenarios,
and validate the application behavior during the failure event.

Gremlin relies on the service proxy (a dependency injection pattern)
to inject failures into the API calls between microservices. Gremlin
expects the service proxy to expose a set of well-defined low-level
fault injection primitives, namely _abort, delay and mangle_. The
Gremlin SDK is a set of abstractions built on top of the fault
injection primitives to enable failure scenario creation and
execution. In addition, it provides a set of simple abstractions on
top of a log store (Elasticsearch), from which behavioral assertions
can be designed (e.g., was latency of service A <= 100ms?).  The logs
from the service proxy are expected to be forwarded to
Elasticsearch.

Gremlin is designed to be agnostic of the service proxy implementation, as
long as it supports the fundamental fault injection primitives (abort,
delay and mangle). See the
[proxy interface](https://github.com/ResilienceTesting/gremlinsdk-python/ProxyInterface.md)
document for details on the fault injection primitives. The reference
service proxy implementation
[gremlinproxy](https://github.com/ResilienceTesting/gremlinproxy) is a
standalone proxy meant to be used as a sidecar process alongside the
microservice, running in the same container or a VM. There are several ways
in which you could implement a service proxy. Some well known approaches
include sidecar-based solutions such as Nginx managed by
[Confd](https://github.com/kelseyhightower/confd),
[Ambassador containers in Kubernetes](http://blog.kubernetes.io/2015/06/the-distributed-system-toolkit-patterns.html),
[AirBnB SmartStack](https://github.com/airbnb/synapse),
[Netflix Prana](https://github.com/Netflix/Prana/), library-based options
such as[Netflix Ribbon](https://github.com/Netflix/Ribbon), or API gateway
patterns such as Mashape's [Kong](https://github.com/Mashape/Kong), and
cloud-hosted solutions such as
[IBM Service Proxy](https://developer.ibm.com/bluemix/2016/04/13/service-proxy-to-balance-monitor-and-test-your-microservices/).

For a step-by-step tutorial on Gremlin, checkout the [getting started](https://github.com/ResilienceTesting/gremlinsdk-python/Getting-Started.md) page.
