#!/usr/bin/python

from pygremlin import *

import sys, requests, json, os

def passOrfail(result):
    if result:
        return "PASS"
    else:
        return "FAIL"

if len(sys.argv) < 4:
    print "usage: run_recipe.py topologySpec gremlins checklist"
    sys.exit(1)

_, topologyFilename, gremlinFilename, checklistFilename = sys.argv

debugMode = (os.getenv('GREMLINSDK_DEBUG', "") != "")
if not os.path.isfile(topologyFilename):
    print u"Topology file {} not found".format(topologyFilename)
    sys.exit(2)

if not os.path.isfile(gremlinFilename):
    print u"Gremlin file {} not found".format(gremlinFilename)
    sys.exit(2)

if not os.path.isfile(checklistFilename):
    print u"Checklist file {} not found".format(checklistFilename)
    sys.exit(2)

with open(topologyFilename) as fp:
    app = json.load(fp)

topology = ApplicationGraph(app)
if debugMode:
    print "Using topology:\n", topology

with open(gremlinFilename) as fp:
    gremlins = json.load(fp)

with open(checklistFilename) as fp:
    checklist = json.load(fp)

fg = FailureGenerator(topology, debug=debugMode)
fg.clear_rules_from_all_proxies()
fg.setup_failures(gremlins)
testID = fg.start_new_test()

print ('Use `postman` to inject test requests,\n\twith HTTP header X-Gremlin-ID: <header-value>\n\tpress Enter key to continue to validation phase')
a = sys.stdin.read(1)
sys.exit(0)

#ac = AssertionChecker(checklist['log_server'], testID, debug=debugMode)
#results = ac.checkAssertions(checklist)
exit_status = 0

for check in results:
    print 'Check %s %s %s' % (check.name, check.info, passOrfail(check.success))
    if not check.success:
        exit_status = 1

sys.exit(exit_status)
