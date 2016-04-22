# coding=utf-8
from collections import defaultdict
import networkx as nx

class ApplicationGraph(object):
    """Represent the topology of an application to be tested by Gremlin"""

    def __init__(self, model=None, debug=False):
        """
        @param dependency graph of microservices with some details
        {
          "services" : [
	   { "name": "gateway", "service_proxies": ["127.0.0.1:9877"] },
	   { "name": "productpage", "service_proxies": ["127.0.0.1:9876"] },
	   { "name": "reviews"},
	   { "name": "details"}
          ],

          "dependencies" : {
	  "gateway" : ["productpage"],
          "productpage" : ["reviews", "details"]
         }
        }
        """

        assert isinstance(debug, bool)
        assert model is None or isinstance(model, dict)

        self._graph = nx.DiGraph()
        self.debug = debug

        if model:
            assert 'services' in model and 'dependencies' in model
            for service in model['services']:
                self.add_service(**service)
            for source, destinations in model['dependencies'].iteritems():
                assert isinstance(destinations, list)
                for destination in destinations:
                    self.add_dependency(source, destination)

    def add_service(self, name, service_proxies=None):
        self._graph.add_node(name)
        if service_proxies is None:
            service_proxies = []
        self._graph.node[name]['instances'] = service_proxies

    def add_dependency(self, fromS, toS):
        self._graph.add_path([fromS, toS])

    def get_dependents(self, service):
        dservices = []
        for e in self._graph.in_edges(service):
            dservices.append(e[0])
        return dservices

    def get_dependencies(self, service):
        dservices = []
        for e in self._graph.out_edges(service):
            dservices.append(e[0])
        return dservices

    def get_services(self):
        return self._graph.nodes()

    def get_service_instances(self, service):
        if 'instances' in self._graph.node[service]:
            return self._graph.node[service]['instances']
        else:
            #print("No instances for service {}".format(service))
            return []

    def _get_networkX(self):
        return self._graph

    def __str__(self):
        retval = ""
        for node in self._graph.nodes():
            retval = retval + "Node: {}\n".format(node)
        for edge in self._graph.edges():
            retval = retval + "Edge: {}->{}\n".format(edge[0], edge[1])
        return retval
