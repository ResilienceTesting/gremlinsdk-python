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
            'reachability' : self.check_reachability,
            'bounded_retries' : self.check_bounded_retries,
            'circuit_breaker' : self.check_circuit_breaker
        }

    def _check_non_zero_results(self, data):
        """
        Checks wheter the output we got from elasticsearch is empty or not
        """
        return data["hits"]["total"] != 0 and len(data["hits"]["hits"]) != 0

    #was ProxyErrorsBad
    def check_no_proxy_errors(self, **args):
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

    def check_bounded_response_time(self, **args):
        assert 'source' in args and 'dest' in args and 'max_latency' in args
        dest = args['dest']
        source = args['source']
        max_latency = _parse_duration(args['max_latency'])
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

    def check_http_success_status(self, **args):
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
        for message in data["hits"]["hits"]:
            if message['_source']["status"] != 200:
                if self.debug:
                    print(message['_source'])
                result = False
        return GremlinTestResult(result, errormsg)

    ##check if the interaction between a given pair of services resulted in the required response status
    def check_http_status(self, **args):
        assert 'source' in args and 'dest' in args and 'status' in args and 'req_id' in args
        source = args['source']
        dest = args['dest']
        status = args['status']
        req_id = args['req_id']
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
        for message in data["hits"]["hits"]:
            if message['_source']["status"] != status:
                if self.debug:
                    print(message['_source'])
                result = False
        return GremlinTestResult(result, errormsg)

    def check_reachability(self, **args):
        # FIXME: implement request tracing/reachability assertion
        # ensure that at least some requests requests search dest from source
        return GremlinTestResult(True, "")

    def check_bounded_retries(self, **args):
        assert 'source' in args and 'dest' in args and 'retries' in args
        source = args['source']
        dest = args['dest']
        retries = args['retries']
        wait_time = args.pop('wait_time', None)
        errdelta = args.pop('errdelta', datetime.timedelta(milliseconds=10))
        by_uri = args.pop('by_uri', False)

        if self.debug:
            print 'in bounded retries (%s, %s, %s)' % (source, dest, retries)

        allreq = self._es.search(body={
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
            pprint.pprint(allreq)

        result = True
        errormsg = ""

        # Check number of req first
        for bucket in allreq["aggregations"]["byid"]["buckets"]:
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
        for bucket in allreq["aggregations"]["byid"]["buckets"]:
            req_id = bucket["key"]
            req_seq = _get_by_id(req_id, allreq["hits"]["hits"])
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
        return GremlinTestResult(result, errormsg)

    def check_circuit_breaker(self, **args): #dest, max_attempts, timeout, sthreshold):
        assert 'dest' in args and 'source' in args and 'max_attempts' in args and 'reset_time' in args
        dest = args['dest']
        source = args['source']
        max_attempts = args['max_attempts']
        reset_time = args['reset_time']

        # TODO: this has been tested for thresholds but not for recovery
        # timeouts
        allpairs = self._es.search(body={
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
                                {"term": {"testid": self._id}}
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
        reset_time = _parse_duration(reset_time)
        for bucket in allpairs["aggregations"]["bysource"]["buckets"]:
            service = bucket["key"]
            req_seq = _get_by("source", source, allpairs["hits"]["hits"])
            req_seq.sort(key=lambda x: isodate.parse_datetime(x['_source']["ts"]))
            count = 0
            tripped = None
            successes = 0
            # pprint.pprint(reqSeq)
            for req in req_seq:
                if tripped is not None:
                    # Restore to half-open
                    if isodate.parse_datetime(req['_source']["ts"]) - tripped >= reset_time:
                        tripped = None
                        count = - 1
                    else:  # We are in open state
                        # this is an assertion fail, no requests in open state
                        if req['_source']["msg"] == "Request":
                            if self.debug:
                                print("Service {} failed to trip circuit breaker")
                            result = False
                else:
                    if (req['_source']["msg"] == "Response" and req['_source']["status"] != 200) or\
                            (req['_source']["msg"] == "Request" and 
                             ("abort" in req['_source']["actions"])):
                        # Increment count
                        count += 1
                        # print(count)
                        # Trip CB, go to open state
                        if count > max_attempts:
                            tripped = isodate.parse_datetime(req['_source']["ts"])
                            successes = 0
                    elif (req['_source']["msg"] == "Response" and req['_source']["status"] == 200):
                        # Are we half-open?
                        if count > 0:
                            # We got a success!
                            successes += 1
                            # If over threshold, return to closed state
                            if successes > sthreshold:
                                count = 0
                    else:
                        print("Unknown state", req['_source'])

        # pprint.pprint(allpairs)
        return GremlinTestResult(result, "")

    def check_assertion(self, name=None, **args):
        # assertion is something like {"name": "bounded_response_time",
        #                              "service": "productpage",
        #                              "max_latency": "100ms"}

        assert name is not None and name in self.functiondict
        gremlin_test_result = self.functiondict[name](**args)
        if self.debug and not gremlin_test_result.success:
            print gremlin_test_result.errormsg

        return AssertionResult(name, str(args), gremlin_test_result.success, gremlin_test_result.errormsg)

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
