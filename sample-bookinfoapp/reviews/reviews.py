#!/usr/bin/python
from flask import Flask, request
import simplejson as json
import requests
import sys
from json2html import *

app = Flask(__name__)

reviews_resp="""
<blockquote>
<p>
An extremely entertaining and comic series by Herge, with expressive drawings!
</p> <small>Reviewer1 <cite>New York Times</cite></small>
</blockquote>
<blockquote>
<p>
Its well-researched plots straddle a variety of genres: 
swashbuckling adventures with elements of fantasy, mysteries, 
political thrillers, and science fiction.
</p> <small>Reviewer2 <cite>Barnes and Noble</cite></small>
</blockquote>
"""

@app.route('/reviews')
def bookReviews():
    global reviews_resp
    return reviews_resp

@app.route('/')
def index():
    """ Display frontpage with normal user and test user buttons"""

    top = """
    <html>
    <head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <!-- Latest compiled and minified CSS -->
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css">

    <!-- Optional theme -->
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap-theme.min.css">

    <!-- Latest compiled and minified JavaScript -->
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.4/jquery.min.js"></script>

    <!-- Latest compiled and minified JavaScript -->
    <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/js/bootstrap.min.js"></script>

    </head>
    <title>Book reviews service</title>
    <body>
    <p><h2>Hello! This is the book reviews service. My content is</h2></p>
    <div>%s</div>
    </body>
    </html>
    """ % (reviews_resp)
    return top

if __name__ == '__main__':
    # To run the server, type-in $ python server.py
    if len(sys.argv) < 1:
        print "usage: %s port" % (sys.argv[0])
        sys.exit(-1)

    p = int(sys.argv[1])
    app.run(host='0.0.0.0', port=p, debug=False)
