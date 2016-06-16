# coding=utf-8
import argparse
from multiprocessing import Pool

import requests
from six.moves import range
from pygremlin import assertionchecker, configure_debug

hostname = 'localhost'
porta = 7777
portb = 7778
headers = {
    'X-Gremlin-ID': 'test'
}
eshost = [{'host': '192.168.99.100', 'port': '29200'}]


# README:
# This assumes that proxy is running at host specified above
# with two services configured to be pointed at httpbin.org
# ServiceA is asummed to be performing well, while service serviceB is delayed,
# as seen by the request url being "/delay/1" seconds
# We also assume the proxy has been configured to log the requests with
# specified header and headerpattern='test'

def req_with_bulkhead(num_req):
    pool1 = Pool(2)
    pool2 = Pool(2)
    pool1.apply_async(requests.get, ('http://{}:{}'.format(hostname, porta)),
                      {headers: headers})
    pool2.apply_async(requests.get, ('http://{}:{}/delay/1'.format(hostname,
                                                                   portb)),
                      {headers: headers})
    pool1.close()
    pool2.close()
    pool1.join()
    pool2.join()


def req_no_bulkhead(num_req):
    for i in range(num_req):
        requests.get('http://{}:{}'.format(hostname, porta), headers=headers)
        requests.get('http://{}:{}/delay/1'.format(hostname, portb),
                     headers=headers)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bulkhead', action='store_true',
                        help='Use the bulkhead simulation')
    parser.add_argument('-n', '--num', type=int, default=20,
                        help='Number of requests to send')
    parser.add_argument('-a', '--assertion-only', action='store_true',
                        help='Only run assertion (assumes data exists from '
                             'previous runs in ES')
    options = parser.parse_args()

    if not options.assertion_only:
        if options.bulkhead:
            req_with_bulkhead(options.num)
        else:
            req_no_bulkhead(options.num)

    logger = configure_debug()
    ac = assertionchecker.AssertionChecker(eshost, "")
    print(ac.check_has_bulkhead('Client'))
