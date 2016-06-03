#!/usr/bin/python

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
import logging
import logging.handlers

#es_logger = logging.getLogger('elasticsearch')
#es_logger.setLevel(logging.DEBUG)
#es_logger.addHandler(logging.StreamHandler())

# es_tracer = logging.getLogger('elasticsearch.trace')
# es_tracer.setLevel(logging.DEBUG)
# es_tracer.addHandler(logging.StreamHandler())

GremlinTestResult = namedtuple('GremlinTestResult', ['success','errormsg'])
AssertionResult = namedtuple('AssertionResult', ['name','info','success','errormsg'])

max_query_results = 500

def _duration_to_floatsec(s):
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
        elif unit == "us":
            vals["microseconds"] = value
        else:
            raise("Unknown time unit")
        start = m.end(1)
        m = r.search(s, start)
    td = datetime.timedelta(**vals)
    duration_us = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6)
    return duration_us/(1.0 * 10**6)

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


def _get_by_id(header, ID, l):
    """
    A convenience wrapper over _get_by
    that fetches things based on the req_tracking_header field
    """
    return _get_by(header, ID, l)


class A8AssertionChecker(object):

    """
    The asssertion checker
    """

    def __init__(self, host, test_id, header='X-Gremlin-ID', pattern='*', debug=False):
        """
        param host: the elasticsearch host
        test_id: id of the test to which we are reqstricting the queires
        """
        self._es = Elasticsearch(hosts=[host])
        self._id = test_id
        self.debug=debug
        self.header = 'http_'+str(header).lower().replace('-','_')
        self.pattern = pattern
        self.functiondict = {
            'bounded_response_time' : self.check_bounded_response_time,
            'http_success_status' : self.check_http_success_status,
            'http_status' : self.check_http_status,
            'bounded_retries' : self.check_bounded_retries,
            'at_most_requests': self.check_at_most_requests
        }

    def _check_non_zero_results(self, data):
        """
        Checks wheter the output we got from elasticsearch is empty or not
        """
        return data["hits"]["total"] != 0 and len(data["hits"]["hits"]) != 0

    def check_bounded_response_time(self, **kwargs):
        assert 'source' in kwargs and 'dest' in kwargs and 'max_latency' in kwargs
        dest = kwargs['dest']
        source = kwargs['source']
        max_latency = _duration_to_floatsec(kwargs['max_latency'])
        data = self._es.search(index="nginx", body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"src": source}},
                                {"prefix": {"dst": dest}},
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
            if float(message['_source']["upstream_response_time"]) > max_latency:
                result = False
                errormsg = "{} did not reply in time for request from {}: found one instance where resp time was {}s - max {}s".format(
                    dest, source, message['_source']["upstream_response_time"], max_latency)
                if self.debug:
                    print errormsg
        return GremlinTestResult(result, errormsg)

    #This isn't working with elasticsearch 2.0+. Neither does regexp
    def check_http_success_status(self, **kwargs):
        data = self._es.search(index="nginx", body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "and" : [
                            {"exists": {"field": "status"}},
                            { "prefix": {self.header: self.pattern}}
                        ]
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
            if int(message['_source']["status"]) != 200:
                errormsg = "{} -> {} - expected HTTP 200 but found found HTTP {}".format(
                    message["_source"]["src"], message["_source"]["dst"], message["_source"]["status"])
                result = False
        return GremlinTestResult(result, errormsg)

    ##check if the interaction between a given pair of services resulted in the required response status
    def check_http_status(self, **kwargs):
        assert 'source' in kwargs and 'dest' in kwargs and 'status' in kwargs
        source = kwargs['source']
        dest = kwargs['dest']
        status = kwargs['status']
        ## TBD: Need to further filter this query using the header and pattern
        data = self._es.search(index="nginx", body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool" : {
                            "must": [
                                {"term": {"src": source}},
                                {"prefix": {"dst": dest}}
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
            if int(message['_source']["status"]) != status:
                errormsg = "{} -> {} - expected HTTP {} but found found HTTP {}".format(
                    message["_source"]["src"], message["_source"]["dst"], status, message["_source"]["status"])
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
        data = self._es.search(index="nginx", body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"src": source}},
                                {"prefix": {"dst": dest}},
                                {"prefix": {self.header: self.pattern}}
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
                        "field": self.header,
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
        errdelta = kwargs.pop('errdelta', 0.0) #datetime.timedelta(milliseconds=10))
        by_uri = kwargs.pop('by_uri', False)

        if self.debug:
            print 'in bounded retries (%s, %s, %s)' % (source, dest, retries)

        data = self._es.search(index="nginx", body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"src": source}},
                                {"prefix": {"dst": dest}},
                                {"prefix": {self.header: self.pattern}}
                            ]
                        }
                    }
                }
            },
            "aggs": {
                "byid": {
                    "terms": {
                        "field": self.header if not by_uri else "uri",
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

        wait_time = _duration_to_floatsec(wait_time)
        # Now we have to check the timestamps
        for bucket in data["aggregations"]["byid"]["buckets"]:
            req_id = bucket["key"]
            req_seq = _get_by_id(self.header, req_id, data["hits"]["hits"])
            req_seq.sort(key=lambda x: int(x['_source']["timestamp_in_ms"]))
            for i in range(len(req_seq) - 1):
                observed = (req_seq[i + 1]['_source']["timestamp_in_ms"] - req_seq[i]['_source']["timestamp_in_ms"])/1000.0
                if not (((wait_time - errdelta) <= observed) or (observed <= (wait_time + errdelta))):
                    errormsg = "{} -> {} - expected {}+/-{}s spacing for retry attempt {}, but request {} had a spacing of {}s".format(
                        source, dest, wait_time, errdelta, i+1, req_id, observed)
                    result = False
                    if self.debug:
                        print errormsg
                    break
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
