# Getting started with Gremlin

In this tutorial, we will use a simple application composed of 3
microservices, to understand how to use Gremlin to systematically inject a
failure and test whether the microservices behaved in the expected manner
during the failure. Specifically, we will be validating if the
microservices implemented
[stability patterns](http://cdn.oreillystatic.com/en/assets/1/event/79/Stability%20Patterns%20Presentation.pdf)
to handle the failure. When compared with simply injecting faults (killing
VMs, containers or failing requests randomly), one of the main advantages
of this systematic approach is that it gives the tester a good idea of
where things might be going wrong. He/She could then quickly fix the
service, rebuild, redeploy, and test again.

This example, while contrived, serves to illustrate the benefits of
systematically testing your microservices application for failure recovery
instead of randomly injecting failures without any useful validation.

## Setup on a local machine

#### Pre-requisites
  * Docker and docker-compose
  * REST client (curl, Chrome + Postman, etc.)

    This tutorial will assume that you are using Chome + Postman to make
    REST API calls to our sample application

  * Setup Gremlin Python SDK

    ```bash
    vagrant@vagrant-ubuntu-trusty-64:~$ git clone https://github.com/ResilienceTesting/gremlinsdk-python
    vagrant@vagrant-ubuntu-trusty-64:~$ cd gremlinsdk-python/python
    vagrant@vagrant-ubuntu-trusty-64:~gremlinsdk-python/python $ sudo python setup.py install
    ```

  * Setup the simple microservice application

    ![A Simple Bookinfo App](https://github.com/ResilienceTesting/gremlinsdk-python/blob/master/exampleapp/bookinfoapp.png)

    For trying out some of the recipes, we will be using a simple bookinfo
    application made of three microservices and an API gateway service
    (_gateway_) facing the user. The API gateway calls the _productpage_
    microservice, which in turn relies on _details_ microservice for ISBN
    info and the _reviews_ microservice for editorial reviews. The SDK
    contains all the code necessary to build out the Docker containers
    pertaining to each microservice. The application is written using
    Python's Flask framework.

    Lets first build the Docker images for each microservice.

    ```bash
    cd gremlinsdk-python/exampleapp; ./build-apps.sh
    ```

    The Docker images for the API _gateway_ and the _productpage_ service have
    the _gremlinproxy_ embedded inside them as a sidecar process. The
    microservices are connected to each other using Docker links. The
    entire application can be launched using ```docker-compose```. In real
    world, the microservices would be registering themselves with a service
    registry (e.g., Consul, Etcd, Zookeeper, etc.) and using a service
    proxy (i.e., dependency injection pattern), to dynamically discover the
    locations of other services and invoke their APIs. The _gremlinproxy_
    provided in this example is a simple reference implementation of a
    service proxy that relies on a static configuration file to indicate
    the location of other microservices.
    
    In addition to the 4 microservices for the Bookinfo app, there is a
    Logstash forwarder and an Elasticsearch container. Event logs from the
    Gremlin proxies are forwarded by the Logstash forwarder to the
    Elasticsearch server. The Gremlin SDK queries this Elasticsearch server
    during the behavior validation phase.

---

## Resilience testing: Checking for timeouts

#### Step 1: Bring up the application and services

```bash
cd gremlinsdk-python/exampleapp; ./runapps.sh
```

Open Postman and access the URL http://localhost:9180/productpage to make sure the page is up.


#### Step 2: Gremlin recipe - setting up failures

Lets run a very simple Gremlin recipe that fakes the overload of the
_reviews_ service (without needing to crash the service) and checks if the
_productpage_ service handles this scenario using the timeout pattern.  The
figure below illustrates the failure scenario and shows both the expected
and the unexpected behavior of the application. As noted earlier, this is a
very contrived example meant for the purpose of illustration. In real
world, you would be using a circuit breaker pattern to recover from such
failures.

![Expected & unexpected outcomes during failure](https://github.com/ResilienceTesting/gremlinsdk-python/blob/master/exampleapp/bookinfoapp-failure.png)

While it is possible to express Gremlin recipes purely in Python code, for
the purpose of this tutorial, we will be using a simple generic test
harness (```gremlinsdk-python/exampleapp/recipes/run_recipe_json.py```) that takes as input
three JSON files: the application's dependency graph, the failure scenario
and the assertions. You will find the following three JSON files in the
```gremlinsdk-python/exampleapp/recipes``` folder:

 + ```topology.json``` describes the applicaton topology for the bookinfo application that we setup earlier.
 + ```gremlins.json``` describes the failure scenario, wherein the
   _reviews_ service is overloaded. A symptom of this scenario is extremely
   delayed responses from the _reviews_ service. In our case, responses will
   be delayed by 8 seconds.

   **Scoping failures to synthetic users:** As we are doing this test in
   production, we don't want to affect real users with our failure
   tests. So lets restrict the failures to a set of synthetic requests. We
   distinguish synthetic requests using a special HTTP header
   ```X-Gremlin-ID```. Only requests carrying this header will be subjected
   to fault injection. Since multiple tests could be running
   simultaneously, we distinguish our test using a specific header value,
   ```testUser-timeout-*```. So any request from _productpage_ to
   _reviews_ that contains the HTTP header ```X-Gremlin-ID:
   testUser-timeout-<someval>``` will be subjected to the overload failure
   described in this JSON file.

 + ```checklist.json``` describes the list of behaviors we want to validate
   during such a scenario. In our case, we will check if the _productpage_
   service times out its API call to _reviews_ service and responds to the
   _gateway_ service within 100ms. This behavior is termed as
   _bounded\_response\_time_ in the ```checklist.json``` file.

Lets run the recipe.

```bash
cd gremlinsdk-python/exampleapp/recipes; ./run_recipe_json.py topology.json gremlins.json checklist.json
```

You should see the following output:

```
Use postman to inject test requests,
   with HTTP header X-Gremlin-ID: <header-value>
   press Enter key to continue to validation phase
```

*Note*: Realistically, load injection would be performed as part of the test
script. However, for the purposes of this tutorial, lets manually inject
the load into the application so that we can visually observe the impact of
fault injection and failure handling.

#### Step 3: Load injection

Go back to Postman. Add ```X-Gremlin-ID``` to the header field and set
```testUser-timeout-1``` as the value for the header.

Load the page (http://localhost:9180/productpage) and you should see that
the page takes *more than 8 seconds to load*.

This page load is an _example of poor handling of the failure
scenario_. The _reviews_ service was overloaded. It took a long time to
respond. _productpage_ service that was dependent on the _reviews_
service, did not timeout its API call.

Now, disable the header field in Postman and reload the page. You should
see that the _web page loads in less than 100ms without
```X-Gremlin-ID```_. In other words, normal traffic remains unaffected,
while only "tagged" test traffic carrying the X-Gremlin-ID header is
subjected to failure injection.

#### Step 4: Continuing recipe execution - behavior validation

Go back to console and complete the recipe execution, i.e., run the
behavior validation step.

```
Hit the enter key on the console
```

The validation code parses the log entries from gremlin service proxies to
check if the _productpage_ service loaded in less than 100ms for requests
containing ```X-Gremlin-ID```. You should see the following output on the
console:

```
Check bounded_response_rime productpage FAIL
```

#### Step 5: Fix the microservice and redeploy

Lets fix the buggy _productpage_ service, rebuild and redeploy. We will add
a 100ms timeout to API calls made to the _reviews_ service.

```bash
cd gremlinsdk-python/exampleapp
```

Open productpage/productpage.py in your favorite editor. Go to the getReview() function.

```python
def getReviews(headers):
    ##timeout is set to 10 milliseconds
    try:
        res = requests.get(reviews['url'], headers=headers) #, timeout=0.010)
    except:
        res = None

    if res and res.status_code == 200:
        return res.text
    else:
        return """<h3>Sorry, product reviews are currently unavailable for this book.</h3>"""
```

Uncomment the part related to 
```python
#timeout=0.010
```
and integrate it into the get API call like below:

```python
res = requests.get(reviews['url'], headers=headers, timeout=0.010)
```

Save and close the file.

Rebuild the app.

```bash
cd gremlinsdk-python/exampleapp; ./rebuild-productpage.sh
```

Redeploy the app.

```bash
cd gremlinsdk-python/exampleapp; ./killall.sh;./runall.sh
```

#### Step 6: Test again

Lets rerun the previous gremlin recipe to check if the product page service
passes the test criterion. Repeat steps 2, 3 and 4. This time, even if
```X-Gremlin-ID``` is present, the product page loads in less than 100ms,
and you should see

```
Sorry reviews are currently unavailable
```

You should also see the following console output during the behavior
validation phase:

```
Check bounded_response_time productpage PASS
```

FYI: If you want to re-run the demo, you should revert the application to its
old setup and rebuild the docker containers.  The ```undochanges.sh```
helper script automates all of these tasks.

```bash
cd gremlinsdk-python/exampleapp; ./undochanges.sh
```

---

## Takeaways

What we did above was to test an app for failure recovery, debugged it,
fixed the issue, redeployed and tested again to ensure that the bug has
been fixed properly. You could imagine automating the entire testing
process above and integrating it into your build pipeline, so that you can
run failure recovery tests just like your unit and integration tests.
