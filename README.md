## Gremlin - Systematic Resiliency Testing of Microservices

Gremlin is a framework for **systematically** testing the failure recovery
logic in microservices in a manner that is independent of the programming
language and the business logic in the microservices. Gremlin takes
advantage of the fact that microservices are loosely coupled and interact
with each other solely over the network, using well defined API over
standard protocols such as HTTP.  

Rather than actually crashing a service
to create a failure, Gremlin intercepts the network interactions (for e.g.,
REST API calls) between microservices and manipulates it to fake a failure
to the caller. 

By observing from the network, how other microservices are
reacting to this failure, it is now possible to express assertions on the
behavior of the end-to-end application during the failure.


### How it works

![Gremlin Architecture][gremlin-arch]
[gremlin-arch]: https://github.com/ResilienceTesting/gremlinsdk-python/raw/master/gremlin-testing-architecture.png  "Architecture of Gremlin Resilience Testing Framework"

Gremlin relies on the service proxy (a dependency injection pattern) to
inject failures into the API calls between microservices. Gremlin expects
the service proxy to expose a set of well-defined low-level fault injection
primitives, namely _abort, delay, and mangle_. The logs from the service proxy are
expected to be forwarded to a log store such as Elasticsearch.

For convenience, this project includes a reference implementation of the service proxy called [gremlinproxy](https://github.com/ResilienceTesting/gremlinproxy). This is a standalone process that can be used as a sidecar process running alongside the
microservice in the same container or VM.


####  Failure Injection and Assertion

**Recipes:** Using the SDK, you can build recipes - Python code that describes a dependency graph between
microservices, a failure scenario that impacts one or more services and
assertions on the behavior of other microservices in the system during the
failure. Recipes are mostly independent of the application's business
logic. It can be reused across different applications, as long as the
dependency graph between microservices is the same.

The Gremlin SDK provides a set of
abstractions built on top of the three fault injection primitives to enable the
user to design and execute a variety of failure scenarios. In
addition, it provides a set of simple abstractions on top of a log store
(Elasticsearch), from which behavioral assertions can be designed (e.g.,
was latency of service A <= 100ms?). 


### Example recipes

Consider the example application shown in the picture above. Lets say we
want to overload service C and validate whether the application as a whole
recovers in an expected manner.

First, lets check if microservice A responds to the user within 50ms.

```python
#!/usr/bin/python
from pygremlin import *
import sys, requests, json

#Load the dependency graph
dependency_graph_json = sys.argv[1]
with open(dependency_graph_json) as fp:
    app = json.load(fp)
topology = ApplicationGraph(app)

##Setup failure
fg = FailureGenerator(topology)
###push failure rules to service proxies
fg.overload_service(source='B', dest='C', headerpattern="overload-req-*")
###start a new test
testID = fg.start_new_test()

##Inject some load
for i in range(1000):
    requests.get("http://foo.com/A",
        headers={"X-Gremlin-ID": "overload-req-%d" % i}

##Run assertions
eventlog = AssertionChecker(elasticsearch_host, testID)
result = eventlog.check_bounded_response_time(source='gateway', dest='A', max_latency='50ms')
assert result.success
```

Now, lets say A passes the test. In other words, A times out API calls to B
in 50ms. This is great. We could *almost* say that this synthetic
application can handle overload of microservice C.

Out of curiosity, lets check how B reacts to C's overload. Ideally, B
should have timed out on C, much faster than A times out on B. So, here
goes a recipe to check if B times out by say 40ms. Since we have already
conducted the test, we just need to add more assertions to the same recipe
(lets assume that we know the test ID)

```python
##omitting boilerplate code
...

##Run assertions
eventlog = AssertionChecker(elasticsearch_host, testID)
resultB = eventlog.check_bounded_response_time(source='B', dest='C', max_latency='40ms')
assert result.success
```

What if B had a timeout of 100ms when calling C? This assertion would
fail. This is not an unrealistic scenario. In fact, this is quite common in
microservice-based applications, because each service is being developed by
different developers/teams. A and B have conflicting failure recovery policies.

### [Getting started](https://github.com/ResilienceTesting/gremlinsdk-python/blob/master/exampleapp)

The exampleapp folder contains a simple microservice application and a
step-by-step tutorial that walks you through the process of using the
recipes to conduct systematic resilience testing.

#### Note: Gremlin SDK is independent of the service proxy

Gremlin SDK is designed to be agnostic of the service proxy implementation, aslong as it supports the fundamental fault injection primitives (`abort`, `delay`, and `mangle`), and its logs are forwarded to a log store such as Elasticsearch. See the
[proxy interface](https://github.com/ResilienceTesting/gremlinsdk-python/blob/master/ProxyInterface.md)
document for details on the fault injection API that needs to be supported by a proxy implementation. With a little bit of porting, the Gremlin SDK can work equally well with fault injection proxies like
[Toxiproxy](https://github.com/shopify/toxiproxy) or a simple nginx proxy with OpenResty support, where you can use Lua code to inject faults into upstream API calls.
