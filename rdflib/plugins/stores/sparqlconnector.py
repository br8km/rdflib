import logging
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
import base64

from io import BytesIO

from rdflib.query import Result
from rdflib import BNode

log = logging.getLogger(__name__)


class SPARQLConnectorException(Exception):
    pass


# TODO: Pull in these from the result implementation plugins?
_response_mime_types = {
    "xml": "application/sparql-results+xml, application/rdf+xml",
    "json": "application/sparql-results+json",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "application/rdf+xml": "application/rdf+xml",
}


class SPARQLConnector(object):
    """
    this class deals with nitty gritty details of talking to a SPARQL server
    """

    def __init__(
        self,
        query_endpoint=None,
        update_endpoint=None,
        returnFormat="xml",
        method="GET",
        auth=None,
        **kwargs
    ):
        """
        auth, if present, must be a tuple of (username, password) used for Basic Authentication

        Any additional keyword arguments will be passed to to the request, and can be used to setup timesouts etc.
        """

        self.returnFormat = returnFormat
        self.query_endpoint = query_endpoint
        self.update_endpoint = update_endpoint
        self.kwargs = kwargs
        self.method = method
        if auth is not None:
            if type(auth) != tuple:
                raise SPARQLConnectorException("auth must be a tuple")
            if len(auth) != 2:
                raise SPARQLConnectorException("auth must be a tuple (user, password)")
            base64string = base64.b64encode(bytes('%s:%s' % auth, 'ascii'))
            self.kwargs.setdefault("headers", {})
            self.kwargs["headers"].update({"Authorization": "Basic %s" % base64string.decode('utf-8')})

    @property
    def method(self):
        return self._method

    @method.setter
    def method(self, method):
        if method not in ("GET", "POST"):
            raise SPARQLConnectorException('Method must be "GET" or "POST"')

        self._method = method

    def query(self, query, default_graph: str = None, named_graph: str = None):
        if not self.query_endpoint:
            raise SPARQLConnectorException("Query endpoint not set!")

        params = {"query": query}
        # this test ensures we don't have a useless (BNode) default graph URI, which calls to Graph().query() will add
        if default_graph is not None and type(default_graph) != BNode:
            params["default-graph-uri"] = default_graph

        headers = {"Accept": _response_mime_types[self.returnFormat]}

        args = dict(self.kwargs)

        # merge params/headers dicts
        args.setdefault("params", {})

        args.setdefault("headers", {})
        args["headers"].update(headers)

        if self.method == "GET":
            args["params"].update(params)
            qsa = "?" + urlencode(args["params"])
            try:
                res = urlopen(Request(self.query_endpoint + qsa, headers=args["headers"]))
            except Exception as e:
                raise ValueError("You did something wrong formulating either the URI or your SPARQL query")
        elif self.method == "POST":
            args["headers"].update({"Content-Type": "application/sparql-query"})
            try:
                res = urlopen(Request(self.query_endpoint, data=query.encode(), headers=args["headers"]))
            except HTTPError as e:
                return e.code, str(e), None
        else:
            raise SPARQLConnectorException("Unknown method %s" % self.method)
        return Result.parse(
            BytesIO(res.read()), content_type=res.headers["Content-Type"].split(";")[0]
        )

    def update(self, query, default_graph: str = None, named_graph: str = None):
        if not self.update_endpoint:
            raise SPARQLConnectorException("Query endpoint not set!")

        params = {}

        if default_graph is not None:
            params["using-graph-uri"] = default_graph

        if named_graph is not None:
            params["using-named-graph-uri"] = default_graph

        headers = {
            "Accept": _response_mime_types[self.returnFormat],
            "Content-Type": "application/sparql-update",
        }

        args = dict(self.kwargs)  # other QSAs

        args.setdefault("params", {})
        args["params"].update(params)
        args.setdefault("headers", {})
        args["headers"].update(headers)

        qsa = "?" + urlencode(args["params"])
        res = urlopen(Request(self.update_endpoint + qsa, data=query.encode(), headers=args["headers"]))
