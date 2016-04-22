#!/usr/bin/python
from flask import Flask, request, render_template
from flask_bootstrap import Bootstrap
import simplejson as json
import requests
import sys
from json2html import *
import logging
from datetime import datetime

def create_app():
    app = Flask(__name__)
    app.debug = True
    Bootstrap(app)
    return app

app = create_app()
log = logging.getLogger("myLogger")
log.setLevel(logging.DEBUG)

@app.before_first_request
def setup_logging():
    console = logging.StreamHandler()
    log.addHandler(console)

details = {
    "name" : "details",
    "url" : "http://localhost:9081/details",
    "children" : []
}

reviews = {
    "name" : "reviews",
    "url" : "http://localhost:9082/reviews",
    "children" : []
}

productpage = {
    "name" : "productpage",
    "children" : [details, reviews]
}

service_dict = {
    "productpage" : productpage,
    "details" : details,
    "reviews" : reviews,
}

if __name__ == '__main__':
    # To run the server, type-in $ python server.py
    if len(sys.argv) < 1:
        print "usage: %s port" % (sys.argv[0])
        sys.exit(-1)

    p = int(sys.argv[1])
    app.run(host='0.0.0.0', port=p, debug = True)

def getGremlinHeader(request):
    usertype= request.args.get('u','')
    gremlinHeader = request.headers.get('X-Gremlin-ID')

    headers = {}
    if gremlinHeader is not None:
        headers = {'X-Gremlin-ID': gremlinHeader}
    elif usertype is not None and usertype.startswith('test'):
        headers = {'X-Gremlin-ID': usertype}
    return headers

@app.route('/')
def index():
    """ Display productpage with normal user and test user buttons"""
    global productpage

    table = json2html.convert(json = json.dumps(productpage),
                              table_attributes="class=\"table table-condensed table-bordered table-hover\"")

    return render_template('index.html', serviceTable=table)


@app.route('/productpage')
def front():
    headers = getGremlinHeader(request)

    bookdetails = getDetails(headers)
    bookreviews = getReviews(headers)
    return render_template('productpage.html', details=bookdetails, reviews=bookreviews)

def getReviews(headers):
    ##timeout is set to 10 milliseconds
    try:
        res = requests.get(reviews['url'], headers=headers)#, timeout=0.010)
    except:
        res = None

    if res and res.status_code == 200:
        return res.text
    else:
        return """<h3>Sorry, product reviews are currently unavailable for this book.</h3>"""


def getDetails(headers):
    try:
        res = requests.get(details['url'], headers=headers)#, timeout=0.010)
    except:
        res = None

    if res and res.status_code == 200:
        return res.text
    else:
        return """<h3>Sorry, product details are currently unavailable for this book.</h3>"""
