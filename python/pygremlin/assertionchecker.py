#!/usr/bin/python
# -*- coding: utf-8 -*-
import json

from elasticsearch import Elasticsearch
import datetime
import pprint
import warnings
import isodate
import sys

import re
from collections import defaultdict, namedtuple
import datetime
import time
from __builtin__ import dict

GremlinTestResult = namedtuple('GremlinTestResult', ['success','errormsg'])
AssertionResult = namedtuple('AssertionResult', ['name','info','success','errormsg'])

max_query_results = 2**31-1

def _parse_duration(s):
    r = re.compile(r"(([0-9]*(\.[0-9]*)?)(\D+))", re.UNICODE)
    start=0
    m = r.search(s, start)
    vals = defaultdict(lambda: 0)
    while m is not None:
        unit = m.group(4)
        try:
            value = float(m.group(2))
        except ValueError:
            print(s, unit, m.group(2))
            return datetime.timedelta()
        if unit == "h":
            vals["hours"] = value
        elif unit == 'm':
            vals["minutes"] = value
        elif unit == 's':
            vals["seconds"] = value
        elif unit == "ms":
            vals["milliseconds"] = value
        elif unit == "us" or unit == "µs":
            vals["microseconds"] = value
        else:
            raise("Unknown time unit")
        start = m.end(1)
        m = r.search(s, start)
    return datetime.timedelta(**vals)

def _since(timestamp):
    return time.time()-timestamp

def _check_value_recursively(key, val, haystack):
    """
    Check if there is key _key_ with value _val_ in the given dictionary.
    ..warning:
        This is geared at JSON dictionaries, so some corner cases are ignored,
        we assume all iterables are either arrays or dicts
    """
    if isinstance(haystack, list):
        return any([_check_value_recursively(key, val, l) for l in haystack])
    elif isinstance(haystack, dict):
        if not key in haystack:
            return any([_check_value_recursively(key, val, d) for k, d in haystack.items()
                        if isinstance(d, list) or isinstance(d, dict)])
        else:
            return haystack[key] == val
    else:
        return False


def _get_by(key, val, l):
    """
    Out of list *l* return all elements that have *key=val*
    This comes in handy when you are working with aggregated/bucketed queries
    """
    return [x for x in l if _check_value_recursively(key, val, x)]


def _get_by_id(ID, l):
    """
    A convenience wrapper over _get_by
    that fetches things based on the "reqID" field
    """
    return _get_by("reqID", ID, l)


class AssertionChecker(object):

    """
    The asssertion checker
    """

    def __init__(self, host, test_id, debug=False):
        """
        param host: the elasticsearch host
        test_id: id of the test to which we are reqstricting the queires
        """
        self._es = Elasticsearch(host)
        self._id = test_id
        self.debug=debug
        self.functiondict = {
            'no_proxy_errors' : self.check_no_proxy_errors,
            'bounded_response_time' : self.check_bounded_response_time,
            'http_success_status' : self.check_http_success_status,
            'http_status' : self.check_http_status,
#            'reachability' : self.check_reachability,
            'bounded_retries' : self.check_bounded_retries,
            'circuit_breaker' : self.check_circuit_breaker,
            'at_most_requests': self.check_at_most_requests
        }

    def _check_non_zero_results(self, data):
        """
        Checks wheter the output we got from elasticsearch is empty or not
        """
        return data["hits"]["total"] != 0 and len(data["hits"]["hits"]) != 0

    #was ProxyErrorsBad
    def check_no_proxy_errors(self, **kwargs):
        """
        Helper method to determine if the proxies logged any major errors related to the functioning of the proxy itself
        """
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "term": {
                            "level": "error"
                        }
                    }
                }
            }
        })
#        if self.debug:
#            print(data)
        return GremlinTestResult(data["hits"]["total"] == 0, data)

    #was ProxyErrors
    def get_requests_with_errors(self):
        """ Helper method to determine if proxies logged any error related to the requests passing through"""
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "exists": {
                            "field": "errmsg"
                        }
                    }
                }
            }
        })
        return GremlinTestResult(False, data)

    def check_bounded_response_time(self, **kwargs):
        assert 'source' in kwargs and 'dest' in kwargs and 'max_latency' in kwargs
        dest = kwargs['dest']
        source = kwargs['source']
        max_latency = _parse_duration(kwargs['max_latency'])
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"msg": "Response"}},
                                {"term": {"source": source}},
                                {"term": {"dest": dest}},
                                {"term": {"testid": self._id}}
                            ]
                        }
                    }
                }
            }
        })
        if self.debug:
            pprint.pprint(data)

        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        for message in data["hits"]["hits"]:
            if _parse_duration(message['_source']["duration"]) > max_latency:
                result = False
                # Request ID from service did not
                errormsg = "{} did not reply in time for request {}, {}".format(
                    dest, message['_source']["reqID"], message['_source']["duration"])
                if self.debug:
                    print errormsg
        return GremlinTestResult(result, errormsg)

    def check_http_success_status(self, **kwargs):
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "exists": {
                            "field": "status"
                        }
                    }
                }
            }})
        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        for message in data["hits"]["hits"]:
            if message['_source']["status"] != 200:
                if self.debug:
                    print(message['_source'])
                result = False
        return GremlinTestResult(result, errormsg)

    ##check if the interaction between a given pair of services resulted in the required response status
    def check_http_status(self, **kwargs):
        assert 'source' in kwargs and 'dest' in kwargs and 'status' in kwargs and 'req_id' in kwargs
        source = kwargs['source']
        dest = kwargs['dest']
        status = kwargs['status']
        req_id = kwargs['req_id']
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool" : {
                            "must": [
                                {"term": {"msg": "Response"}},
                                {"term": {"source": source}},
                                {"term": {"dest": dest}},
                                {"term": {"req_id": req_id}},
                                {"term": {"protocol" : "http"}},
                                {"term": {"testid": self._id}}
                            ]
                        }
                    }
                }
            }})

        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        for message in data["hits"]["hits"]:
            if message['_source']["status"] != status:
                if self.debug:
                    print(message['_source'])
                result = False
        return GremlinTestResult(result, errormsg)

    def check_at_most_requests(self, source, dest, num_requests, **kwargs):
        """
        Check that source service sent at most num_request to the dest service
        :param source the source service name
        :param dest the destination service name
        :param num_requests the maximum number of requests that we expect
        :return:
        """
        # TODO: Does the proxy support logging of instances so that grouping by instance is possible?

        # Fetch requests for src->dst
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"msg": "Request"}},
                                {"term": {"source": source}},
                                {"term": {"dest": dest}},
                                {"term": {"protocol": "http"}},
                                {"term": {"testid": self._id}}
                            ]
                        }
                    }
                }
            },
            "aggs": {
                # Need size, otherwise only top buckets are returned
                "size": max_query_results,
                "byid": {
                    "terms": {
                        "field": "reqID",
                    }
                }
            }
        })

        if self.debug:
            pprint.pprint(data)

        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        # Check number of requests in each bucket
        for bucket in data["aggregations"]["byid"]["buckets"]:
            if bucket["doc_count"] > (num_requests + 1):
                errormsg = "{} -> {} - expected {} requests, but found {} "\
                         "requests for id {}".format(
                            source, dest, num_requests, bucket['doc_count'] - 1,
                            bucket['key'])
                result = False
                if self.debug:
                    print errormsg
                return GremlinTestResult(result, errormsg)
        return GremlinTestResult(result, errormsg)

    def check_bounded_retries(self, **kwargs):
        assert 'source' in kwargs and 'dest' in kwargs and 'retries' in kwargs
        source = kwargs['source']
        dest = kwargs['dest']
        retries = kwargs['retries']
        wait_time = kwargs.pop('wait_time', None)
        errdelta = kwargs.pop('errdelta', datetime.timedelta(milliseconds=10))
        by_uri = kwargs.pop('by_uri', False)

        if self.debug:
            print 'in bounded retries (%s, %s, %s)' % (source, dest, retries)

        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"source": source}},
                                {"term": {"msg": "Request"}},
                                {"term": {"dest": dest}},
                                {"term": {"testid": self._id}}
                            ]
                        }
                    }
                }
            },
            "aggs": {
                "byid": {
                    "terms": {
                        "field": "reqID" if not by_uri else "uri",
                    }
                }
            }
        })

        if self.debug:
            pprint.pprint(data)

        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        # Check number of req first
        for bucket in data["aggregations"]["byid"]["buckets"]:
            if bucket["doc_count"] > (num + 1):
                errormsg = "{} -> {} - expected {} retries, but found {} retries for request {}".format(
                    source, dest, retries, bucket['doc_count']-1, bucket['key'])
                result = False
                if self.debug:
                    print errormsg
                return GremlinTestResult(result, errormsg)
        if wait_time is None:
            return GremlinTestResult(result, errormsg)
 
        wait_time = _parse_duration(wait_time)
        # Now we have to check the timestamps
        for bucket in data["aggregations"]["byid"]["buckets"]:
            req_id = bucket["key"]
            req_seq = _get_by_id(req_id, data["hits"]["hits"])
            req_seq.sort(key=lambda x: isodate.parse_datetime(x['_source']["ts"]))
            for i in range(len(req_seq) - 1):
                observed = isodate.parse_datetime(
                    req_seq[i + 1]['_source']["ts"]) - isodate.parse_datetime(req_seq[i]['_source']["ts"])
                if not (((wait_time - errdelta) <= observed) or (observed <= (wait_time + errdelta))):
                    errormsg = "{} -> {} - expected {}+/-{}ms spacing for retry attempt {}, but request {} had a spacing of {}ms".format(
                        source, dest, wait_time, errdelta.microseconds/1000, i+1, req_id, observed.microseconds/1000)
                    result = False
                    if self.debug:
                        print errormsg
                    break
        return GremlinTestResult(result, errormsg)

    def check_circuit_breaker(self, **kwargs): #dest, closed_attempts, reset_time, halfopen_attempts):
        assert 'dest' in kwargs and 'source' in kwargs and 'closed_attempts' in kwargs and 'reset_time' in kwargs and 'headerprefix' in kwargs

        dest = kwargs['dest']
        source = kwargs['source']
        closed_attempts = kwargs['closed_attempts']
        reset_time = kwargs['reset_time']
        headerprefix = kwargs['headerprefix']
        if 'halfopen_attempts' not in kwargs:
            halfopen_attempts = 1
        else:
            halfopen_attempts = kwargs['halfopen_attempts']

        # TODO: this has been tested for thresholds but not for recovery
        # timeouts
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"source": source}},
                                {"term": {"dest": dest}},
                                {"prefix": {"reqID": headerprefix}}
                            ],
                            "should": [
                                {"term": {"msg": "Request"}},
                                {"term": {"msg": "Response"}},
                            ]
                        }
                    }
                }
            },
            "aggs": {
                "bysource": {
                    "terms": {
                        "field": "source",
                    }
                }
            }
        })

        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        reset_time = _parse_duration(reset_time)
        circuit_mode = "closed"

        # TODO - remove aggregations
        for bucket in data["aggregations"]["bysource"]["buckets"]:
            req_seq = _get_by("source", source, data["hits"]["hits"])
            req_seq.sort(key=lambda x: isodate.parse_datetime(x['_source']["ts"]))
            failures = 0
            circuit_open_ts = None
            successes = 0
            print "starting " + circuit_mode
            for req in req_seq:
                if circuit_mode is "open": #circuit_open_ts is not None:
                    req_spacing = isodate.parse_datetime(req['_source']["ts"]) - circuit_open_ts
                    # Restore to half-open
                    if req_spacing >= reset_time:
                        circuit_open_ts = None
                        circuit_mode = "half-open"
                        print "%d: open -> half-open" %(failures +1)
                        failures = 0 #-1
                    else:  # We are in open state
                        # this is an assertion fail, no requests in open state
                        if req['_source']["msg"] == "Request":
                            print "%d: open -> failure" % (failures + 1)
                            if self.debug:
                                print "Service %s failed to trip circuit breaker" % source
                            errormsg = "{} -> {} - new request was issued at ({}s) before reset_timer ({}s)expired".format(source,
                                                                                                                         dest,
                                                                                                                         req_spacing,
                                                                                                                         reset_time) #req['_source'])
                            result = False
                            break
                if circuit_mode is "half-open":
                    if ((req['_source']["msg"] == "Response" and req['_source']["status"] != 200)
                        or (req['_source']["msg"] == "Request" and ("abort" in req['_source']["actions"]))):
                        print "half-open -> open"
                        circuit_mode = "open"
                        circuit_open_ts = isodate.parse_datetime(req['_source']["ts"])
                        successes = 0
                    elif (req['_source']["msg"] == "Response" and req['_source']["status"] == 200):
                        successes += 1
                        print "half-open -> half-open (%d)" % successes
                        # If over threshold, return to closed state
                        if successes > halfopen_attempts:
                            print "half-open -> closed"
                            circuit_mode = "closed"
                            failures = 0
                            circuit_open_ts = None
                #else:
                elif circuit_mode is "closed":
                    if ((req['_source']["msg"] == "Response" and req['_source']["status"] != 200)
                        or (req['_source']["msg"] == "Request" and len(req['_source']["actions"]) > 0)):
                        # Increment failures
                        failures += 1
                        print "%d: closed->closed" % failures
                        # print(failures)
                        # Trip CB, go to open state
                        if failures > closed_attempts:
                            print "%d: closed->open" % failures
                            circuit_open_ts = isodate.parse_datetime(req['_source']["ts"])
                            successes = 0
                            circuit_mode = "open"

        # pprint.pprint(data)
        return GremlinTestResult(result, errormsg)

    def check_assertion(self, name=None, **kwargs):
        # assertion is something like {"name": "bounded_response_time",
        #                              "service": "productpage",
        #                              "max_latency": "100ms"}

        assert name is not None and name in self.functiondict
        gremlin_test_result = self.functiondict[name](**kwargs)
        if self.debug and not gremlin_test_result.success:
            print gremlin_test_result.errormsg

        return AssertionResult(name, str(kwargs), gremlin_test_result.success, gremlin_test_result.errormsg)

    def check_assertions(self, checklist, all=False):
        """Check a set of assertions
        @param all boolean if False, stop at first failure
        @return: False if any assertion fails.
        """

        assert isinstance(checklist, dict) and 'checks' in checklist

        retval = None
        retlist = []
        for assertion in checklist['checks']:
            retval = self.check_assertion(**assertion)
            retlist.append(retval)
            if not retval.success and not all:
                return retlist

        return retlist
