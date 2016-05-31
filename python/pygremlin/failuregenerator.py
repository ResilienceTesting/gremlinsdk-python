# coding=utf-8

import requests
import json
from collections import defaultdict
import uuid
import logging
import httplib
logging.basicConfig()
requests_log = logging.getLogger("requests.packages.urllib3")

class FailureGenerator(object):

    def __init__(self, app, debug=False):
        """
        Create a new failure generator
        @param app ApplicationGraph: instance of ApplicationGraph object
        """
        self.app = app
        self.debug = debug
        self._id = None
        self._queue = []
        #some common scenarios
        self.functiondict = {
            'delay_requests' : self.delay_requests,
            'delay_responses' : self.delay_responses,
            'abort_requests' : self.abort_requests,
            'abort_responses' : self.abort_responses,
            'partition_services' : self.partition_services,
            'crash_service' : self.crash_service,
            'overload_service' : self.overload_service
        }
        if debug:
            httplib.HTTPConnection.debuglevel = 1
            logging.getLogger().setLevel(logging.DEBUG)
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True

    def _notify_proxies(self):
        if self.debug:
            print 'in _notifyProxies'
        # TODO: modify this so we can support more than one test at a time
        for service in self.app.get_services():
            if self.debug:
                print(service)
            for instance in self.app.get_service_instances(service):
                resp = requests.get("http://{}/gremlin/v1/test/{}".format(instance,self._id))
                resp.raise_for_status()


    def start_new_test(self):
        self._id = uuid.uuid4().hex
        for service in self.app.get_services():
            if self.debug:
                print(service)
            for instance in self.app.get_service_instances(service):
                resp = requests.put("http://{}/gremlin/v1/test/{}".format(instance,self._id))
                resp.raise_for_status()
        return self._id

    def get_test_id(self):
        return self._id


    def add_rule(self, **args):
        """
        @param args keyword argument list, consisting of:

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
        """
        #The defaults are indicated below
        myrule = {
                  "source": "",
                  "dest": "",
                  "messagetype": "request",
                  "headerpattern": "*",
                  "bodypattern": "*",
                  "delayprobability": 0.0,
                  "delaydistribution": "uniform",
                  "mangleprobability": 0.0,
                  "mangledistribution": "uniform",
                  "abortprobability": 0.0,
                  "abortdistribution": "uniform",
                  "delaytime": "0s",
                  "errorcode": -1,
                  "searchstring": "",
                  "replacestring": ""
        }
        rule = args.copy()
        #copy
        for i in rule.keys():
            if i not in myrule:
                continue
            myrule[i] = rule[i]
        #check defaults
        services = self.app.get_services()
        assert myrule["source"] != "" and myrule["dest"] != ""
        assert myrule["source"] in services and myrule["dest"] in services
        assert myrule['headerpattern'] != "" or myrule["bodypattern"] != ""
        assert myrule['delayprobability'] >0.0 or myrule['abortprobability'] >0.0 or myrule['mangleprobability'] >0.0
        if myrule["delayprobability"] > 0.0:
            assert myrule["delaytime"] != ""
        if myrule["abortprobability"] > 0.0:
            assert myrule["errorcode"] >= -1
        assert myrule["messagetype"] in ["request", "response", "publish", "subscribe"]
        self._queue.append(myrule)

    def clear_rules_from_all_proxies(self):
        """
            Clear fault injection rules from all known service proxies.
        """
        self._queue = []        
        if self.debug:
            print 'Clearing rules'
        for service in self.app.get_services():
            for instance in self.app.get_service_instances(service):
                if self.debug:
                    print 'Clearing rules for %s - instance %s' % (service, instance)
                resp = requests.delete("http://{}/gremlin/v1/rules".format(instance))
                if resp.status_code != 200:
                    print 'Failed to clear rules for %s - instance %s' % (service, instance)

    def list_rules(self, service=None):
        """
            List fault fault injection rules installed on instances of a given service (or all services)
            returns a JSON dictionary
        """
        rules = {}
        for service in self.app.get_services():
            rules[service] = {}
            for instance in self.app.get_service_instances(service):
                rules[service][instance] = {}
                resp = requests.get("http://{}/gremlin/v1/rules/list".format(instance))
                if resp.status_code != 200:
                    print 'Failed to fetch rules from %s - instance %s' % (service, instance)
                    continue
                rules[service][instance] = resp.json()
                return rules

    #TODO: Create a plugin model here, to support gremlinproxy and nginx
    def push_rules(self, continue_on_errors=False):
        for rule in self._queue:
            instances = self.app.get_service_instances(rule["source"])
            for instance in instances:
                try:
                    resp = requests.post("http://{}/gremlin/v1/rules/add".format(instance),
                                         headers = {"Content-Type" : "application/json"},
                                         data=json.dumps(rule))
                    resp.raise_for_status()
                except requests.exceptions.ConnectionError, e:
                    print "FAILURE: Could not add rule to instance %s of service %s" % (instance, rule["source"])
                    print e
                    if not continue_on_errors:
                        raise e

    def _generate_rules(self, rtype, **args):
        rule = args.copy()
        assert rtype is not None and rtype != "" and (rtype is "delay" or rtype is "abort")

        if rtype is "abort":
            rule['abortprobability']=rule.pop('abortprobability',1) or 1
            rule['errorcode']=rule.pop('errorcode',-1) or -1
        else:
            rule['delayprobability']=rule.pop('delayprobability',1) or 1
            rule['delaytime']=rule.pop('delaytime',"1s") or "1s"
            
        assert 'source' in rule or 'dest' in rule
        if 'source' in rule:
            assert rule['source'] != ""
        if 'dest' in rule:
            assert rule['dest'] != ""

        rule['headerpattern'] = rule.pop('headerpattern', '*') or '*'
        rule['bodypattern'] = rule.pop('bodypattern', '*') or '*'
        sources = []
        destinations = []
        if 'source' not in rule:
            sources = self.app.get_dependents(rule['dest'])
        else:
            sources.append(rule['source'])

        if 'dest'not in rule:          
            destinations = self.app.get_dependencies(rule['source'])
        else:
            destinations.append(rule['dest'])

        for s in sources:
            for d in destinations:
                rule["source"] = s
                rule["dest"] = d
                self.add_rule(**rule)
                if self.debug:
                    print '%s - %s' % (rtype, str(rule))

    def abort_requests(self, **args):
        args['messagetype']='request'
        self._generate_rules('abort', **args)

    def abort_responses(self, **args):
        args['messagetype']='response'
        self._generate_rules('abort', **args)

    def delay_requests(self, **args):
        args['messagetype']='request'
        self._generate_rules('delay', **args)

    def delay_responses(self, **args):
        args['messagetype']='response'
        self._generate_rules('delay', **args)

    """
    Gives the impression of an overloaded service. If no probability is given
    50% of requests will be delayed by 10s (default) and rest 50% will get HTTP 503.
    """
    def overload_service(self, **args):
        rule = args.copy()
        assert 'dest' in rule

        rule['delayprobability'] = rule.pop('delayprobability', 0.5) or 0.5
        rule['abortprobability'] = rule.pop('abortprobability', 0.5) or 0.5
        rule['delaytime'] = rule.pop('delaytime', "10s") or "10s"
        rule['errorcode'] = rule.pop("errorcode", 503) or 503
        rule['messagetype'] = rule.pop('messagetype', 'request') or 'request'
        rule['headerpattern'] = rule.pop('headerpattern', '*') or '*'
        rule['bodypattern'] = rule.pop('bodypattern','*') or '*'

        sources = []
        if 'source' not in rule or rule['source'] == "":
            sources = self.app.get_dependents(rule['dest'])
        else:
            sources.append(rule['source'])

        for s in sources:
            rule["source"] = s
            self.add_rule(**rule)
            if self.debug:
                print 'Overload %s ' % str(rule)

    def partition_services(self, **args):
        """Partitions two connected services. Not two sets of services (TODO)
        Expects usual arguments and srcprobability and dstprobability, that indicates probability of 
        terminating connections from source to dest and vice versa
        """
        rule = args.copy()
        assert 'source' in rule and 'dest' in rule
        #assert 'srcprobability' in rule and 'dstprobability' in rule
        assert rule['source'] != "" and rule['dest'] != ""
        #check if the two services are connected
        assert rule['dest'] in self.app.get_dependencies(rule['source'])

        rule['errorcode'] = rule.pop('errorcode', -1) or -1
        rule['abortprobability'] = rule.pop('srcprobability', 1) or 1
        self.abort_requests(**rule)

        rule['abortprobability'] = rule.pop('dstprobability', 1) or 1
        temp = rule['source']
        rule['source'] = rule['dest']
        rule['dest'] = temp
        self.abort_requests(**rule)

    """
    Causes the dest service to become unavailable to all callers
    """
    def crash_service(self, **args):
        rule = args.copy()
        rule['source']=''
        rule['errorcode']=rule.pop('errorcode', -1) or -1
        self.abort_requests(**rule)

    def setup_failure(self, scenario=None, **args):
        """Add a given failure scenario
        @param scenario: string 'delayrequests' or 'crash'
        """
        assert scenario is not None and scenario in self.functiondict
        self.functiondict[scenario](**args)

    def setup_failures(self, gremlins):
        """Add gremlins to environment"""

        assert isinstance(gremlins, dict) and 'gremlins' in gremlins
        for gremlin in gremlins['gremlins']:
            self.setup_failure(**gremlin)
        self.push_rules()
