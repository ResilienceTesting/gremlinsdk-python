Gremlin is agnostic of the service proxy implementation. It only requires
the proxy to be capable of injecting the three basic types of faults into
API calls between microservices.

There are several ways in which you could implement a service proxy. Some
well known approaches include sidecar-based solutions such as Nginx managed
by [Confd](https://github.com/kelseyhightower/confd),
[Ambassador containers in Kubernetes](http://blog.kubernetes.io/2015/06/the-distributed-system-toolkit-patterns.html),
[AirBnB SmartStack](https://github.com/airbnb/synapse),
[Netflix Prana](https://github.com/Netflix/Prana/), library-based options
such as[Netflix Ribbon](https://github.com/Netflix/Ribbon), or API gateway
patterns such as Mashape's [Kong](https://github.com/Mashape/Kong), and
cloud-hosted solutions such as
[IBM Service Proxy](https://developer.ibm.com/bluemix/2016/04/13/service-proxy-to-balance-monitor-and-test-your-microservices/).

The only requirement for Gremlin is that the service proxy should support
fault injection, and should be programmable over a REST API. A reference
implementation of a service proxy with fault injection support can be found
at [gremlinproxy](https://github.com/ResilienceTesting/gremlinproxy).

* For fault injection, a service proxy implementation needs to support 3
  key primitives: abort, delay, and mangle.

* Any fault injection rule comprises of a set of regexes that match a
  request/response, and a combination of one or more of the failure
  primitives.

* A service proxy should be able to receive the fault injection rules via a
  REST API and inject faults on requests matching the rule.

* A failure scenario is comprised of a set of fault injection rules
  distributed across one or more service proxies that sit in front of
  microservices.

The REST APIs that need to be implemented by any type of service proxy are
given below.

```POST /gremlin/v1/rules/add```: add a Rule. Rule will be posted as a JSON. Format is as follows

```javascript
{
  source: <source service name>,
  dest: <destination service name>,
  messagetype: <request|response|publish|subscribe|stream>
  headerpattern: <regex to match against the value of the X-Gremlin-ID trackingheader present in HTTP headers>
  bodypattern: <regex to match against HTTP message body>
  delayprobability: <float, 0.0 to 1.0>
  delaydistribution: <uniform|exponential|normal> probability distribution function

  mangleprobability: <float, 0.0 to 1.0>
  mangledistribution: <uniform|exponential|normal> probability distribution function

  abortprobability: <float, 0.0 to 1.0>
  abortdistribution: <uniform|exponential|normal> probability distribution function

  delaytime: <string> latency to inject into requests <string, e.g., "10ms", "1s", "5m", "3h", "1s500ms">
  errorcode: <Number> HTTP error code or -1 to reset TCP connection
  searchstring: <string> string to replace when Mangle is enabled
  replacestring: <string> string to replace with for Mangle fault
}
```

```POST /gremlin/v1/rules/remove``` : remove the rule specified in the message body (see rule format above)

```DELETE /gremlin/v1/rules```: clear all rules
