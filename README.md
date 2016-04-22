# Gremlin

## A framework for systematic resiliency testing of microservices

Gremlin is a resiliency testing framework that enables developers to
systematically test the ability of their microservices to recover from
custom designed failure scenarios. This SDK is a set of abstractions
that enable developers to build and execute custom failure scenarios,
and validate the application behavior during the failure event.

Gremlin relies on the service proxy (a dependency injection pattern)
to inject failures into the API calls between microservices. Gremlin
expects the service proxy to expose a set of well-defined low-level
fault injection primitives, namely abort, delay and mangle. The
Gremlin SDK is a set of abstractions built on top of the fault
injection primitives to enable failure scenario creation and
execution. In addition, it provides a set of simple abstractions on
top of a log store (Elasticsearch), from which behavioral assertions
can be designed (e.g., was latency of service A <= 100ms?).  The logs
from the service proxy are expected to be forwarded to
Elasticsearch. Support for other log storage systems will be added in
future.

Gremlin is designed to be agnostic of the service proxy
implementation, as long as it supports the fundamental fault injection
primitives (abort, delay and mangle). See the [proxy
interface](https://github.com/ResilienceTesting/gremlinsdk-python/ProxyInterface.md)
document for details on the fault injection primitives. The reference
service proxy implementation
[gremlinproxy](https://github.com/ResilienceTesting/gremlinproxy) is
a standalone proxy. There are other client-side library based
implementations, such as [Netflix
Ribbon](https://github.com/Netflix/Ribbon), [Spotify
Hermes](http://www.slideshare.net/protocol7/spotify-architecture-pressing-play),
etc.

# Getting Started

### Pre-requisites

##### Setup Vagrant
Install Vagrant from this [link](https://www.vagrantup.com/downloads.html)

Then
```bash
shriram@shrirams-mbp:~ $ mkdir Documents/vagrant
shriram@shrirams-mbp:~ $ cd Documents/vagrant
shriram@shrirams-mbp:~/Documents/vagrant $ vagrant init ubuntu/trusty64
```

Now, lets setup the port mappings needed to access the apps inside the VM. Open the ```Vagrantfile``` in your favorite editor. Below the opening block for Vagrant configure (shown below)
```ruby
Vagrant.configure(2) do |config|
```
add this line:
```ruby
  # Create a forwarded port mapping which allows access to a specific port
  # within the machine from a port on the host machine. In the example below,
  # accessing "localhost:9180" will access port 9080 on the guest machine.
  config.vm.network "forwarded_port", guest: 9080, host: 9180
 ```

Optional: I would also suggest increasing the memory and CPU allocated to the VM. To do so, add the following in the config block:
```ruby
config.vm.provider "virtualbox" do |vb|
     vb.memory = "4096"
     vb.cpus = 2
  end
```

Now boot the VM.

```bash
shriram@shrirams-mbp:~/Documents/vagrant $ vagrant up
shriram@shrirams-mbp:~/Documents/vagrant $ vagrant ssh
```

##### Setup docker and docker-compose

These instructions are based on the [tutorial](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-compose-on-ubuntu-14-04) from DigitalOcean

```bash
vagrant@vagrant-ubuntu-trusty-64:~$ sudo wget -qO- https://get.docker.com/ | sh
vagrant@vagrant-ubuntu-trusty-64:~$ sudo usermod -aG docker $(whoami)
vagrant@vagrant-ubuntu-trusty-64:~$ sudo apt-get -y install python-pip
vagrant@vagrant-ubuntu-trusty-64:~$ sudo pip install docker-compose==1.4.2
```

##### Setup Gremlin SDK

Clone and install the gremlinsdk from github.ibm.com. 

```bash
vagrant@vagrant-ubuntu-trusty-64:~$ git clone ssh://git@github.ibm.com/shriram/gremlinsdk.git
vagrant@vagrant-ubuntu-trusty-64:~$ cd gremlinsdk/python
vagrant@vagrant-ubuntu-trusty-64:~gremlinsdk/python $ sudo python setup.py develop
```

##### Setup the synthetic application

For trying out some of the recipes right away, we will be using a
simple bookinfo application made of three microservices. An _API
gateway_ facing the user. The API gateway calls the _Product page_
service, which in turn relies on _Details_ service for ISBN info and
the _Reviews_ service for editorial reviews. The SDK contains all the
code necessary to build out the Docker containers pertaining to each
microservice. The application is written using Python's Flask
framework.

Lets first build the Docker images for each microservice (note: this
step may take a while to finish)

```bash
cd gremlinsdk/sample-bookinfoapp; ./build-apps.sh
```

The Docker images for the API gateway and the productpage service have
the gremlinproxy embedded inside them as a side car. The microservices
are connected to each other using Docker links. The entire application
can be launched using ```docker-compose```. In addition to the 4
microservices for the Bookinfo app, there is a Logstash forwarder and
an Elasticsearch container. Logs from the service proxies are
forwarded by the Logstash forwarder to Elasticsearch server. The
Gremlin SDK queries this Elasticsearch server during the behavior
validation phase.
 
##### Install Postman

Assuming that you are using Chrome browser, install the [Postman
Chrome
extension](https://chrome.google.com/webstore/detail/postman/fhbjgbiflinjbdggehcddcbncdddomop?hl=en). With
Postman, we can craft and send HTTP requests to our sample
application, with custom headers and also view the responses in a nice
web page.

---

## Subjecting Bookinfo App to Resiliency Testing

#### Step 1: Bring up apps and services

```bash
cd gremlinsdk/sample-bookinfoapp; ./runapps.sh
```

Open Postman and access the URL http://localhost:9180/productpage to make sure the page is up.

#### Step 2: Gremlin recipe - setting up failures

A Gremlin recipe is a combination of application topology, failure scenario and expected application behavior during the failure. These aspects are captured in the following three JSON files in the SDK:
 + ```topology.json``` describes the applicaton topology for the bookinfo application that we setup earlier.
 + ```gremlins.json``` describes the failure scenario: __wherein the _Reviews service is overloaded_. A symptom of this scenario is extremely delayed responses from the Reviews service. In our case, responses will be delayed by 8 seconds. 
 + ```checklist.json``` describes the list of behaviors we want to validate during such a scenario. In our case, we will check if the Product page service times out its API call to Reviews service and responds to the Gateway service within 100ms. This behavior is termed as _BoundedResponseTime_ in the ```checklist.json``` file.

The ```run_recipe.py``` is a generic test harness that takes an application topology, the set of gremlins to inject into the application and the set of behavior validation checks to perform.

```bash
cd gremlinsdk/recipes; ./run_recipe.py topology.json gremlins.json checklist.json
```

You should see the following output:

```
Use postman to inject test requests,
   with HTTP header X-Gremlin-ID: testUser-timeout-[NUM]
   press Enter key to continue to validation phase
```

#### Step 3: Load injection

Go back to Postman. Add ```X-Gremlin-ID``` to the header field and set ```testUser-timeout-1``` as the value for the header.

Load the page (http://localhost:9180/productpage) and you should see that the page takes *more than 8 seconds to load*. **Do not cancel the request** (temporary hack. please bear with me for a couple of weeks).

This page load is an _example of poor handling of the failure
scenario_. Review service was overloaded. It took a long time to
respond. Product page service that was dependent on the Review
service, did not timeout its API call.

Now, disable the header field in Postman and reload the page. You
should see that the _web page loads in less than 100ms without ```X-Gremlin-ID```_. In other words, normal traffic remains unaffected, while only "tagged" test traffic carrying the X-Gremlin-ID header is subjected to failure injection.

#### Step 4: Continuing recipe execution - behavior validation

Go back to console and complete the recipe execution, i.e., run the behavior validation step.

```
Hit the enter key on the console
```

The validation code parses the log entries from gremlin service proxies to check if the product page service loaded in less than 100ms for requests containing ```X-Gremlin-ID```. You should see the following output on the console:

```
Check BoundedResponseTime productpage FAIL
```

#### Step 5: Fix the application

Lets fix the buggy product page service, rebuild and redeploy.

```bash
cd gremlinsdk/sample-bookinfoapp
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
cd gremlinsdk/sample-bookinfoapp; ./rebuild-productpage.sh
```

Redeploy the app.

```bash
cd gremlinsdk/sample-bookinfoapp; ./killall.sh;./runall.sh
```

#### Step 6: Test again

Lets rerun the previous gremlin recipe to check if the product page service passes the test criterion. Repeat steps 2, 3 and 4. This time, even if  ```X-Gremlin-ID``` is present, the product page loads in less than 100ms, and you should see
```
Sorry reviews are currently unavailable
```

You should also see the following console output during the behavior validation phase:

```
Check BoundedResponseTime productpage PASS
```

If you want to re-run the demo, you should revert the application back to its old setup and rebuild the docker containers.
The ```undochanges.sh``` helper script automates all of these tasks.

```bash
cd gremlinsdk/sample-bookinfoapp; ./undochanges.sh
```

Now you can start from Step 1
---

Additional recipes are found in the gremlin/recipes folder, in generic_gremlin_templates.json file.
