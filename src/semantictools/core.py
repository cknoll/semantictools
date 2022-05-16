import os
import sys
import requests
import json
import time
import re
import base64
from IPython.display import SVG, display, HTML

import networkx as nx
import owlready2 as owl2
from bs4 import BeautifulSoup
import nxv


from . import cache

from .release import __version__

# noinspection PyUnresolvedReferences
# for debugging
from ipydex import IPS, activate_ips_on_exception, set_trace


BASEPATH = os.path.dirname(
    (os.path.dirname(os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))))
)


class AttributeDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


class WikidataError(ValueError):
    pass


# local store of WDObjects
WD_store = {}

# local store of OWL-objects (instances)
onto_store = {}


class WDObject(object):
    """
    Encapsulates a wikidata object
    """

    # regex that matches labels wich start with "Q<number>"
    no_label = re.compile("Q\d+?.*")

    def __init__(self, source_data):
        """
        :param source_data: parsed json
        """
        # assume SERVICE wikibase:label <en>
        try:
            self.label = self.label_en = source_data["itemLabel"]["value"]
        except KeyError:
            self.label = self.label_en = source_data["label"]

        self.id = self.get_id_from_raw_data(source_data)
        self.source_data = source_data

        WD_store[id] = self

    @staticmethod
    def get_id_from_raw_data(source_data):

        try:
            id = source_data["item"]["value"]
        except KeyError:
            id = source_data["id"]
        return id.replace("http://www.wikidata.org/entity/", "")

    @property
    def has_label_en(self):
        return not self.no_label.match(self.label)

    def __repr__(self):
        return f"WDObject <{self.id}> ('{self.label_en}')"

    def create_onto_instance(self, cls):
        """
        :param cls: owl class
        """

        obj = cls(self.label)
        onto_store[self.id] = obj
        return obj

    @property
    def onto_instance(self):
        return onto_store[self.id]


try:
    # noinspection PyPackageRequirements
    from decouple import Config, RepositoryIni

    # https://meta.wikimedia.org/wiki/User-Agent_policy
    config_path = os.path.join(BASEPATH, "config.ini")
    config = Config(RepositoryIni(config_path))
    request_headers = {
        "User-Agent": f'semantictools/{__version__} {config("contact_email")}',
    }

except (ImportError, FileNotFoundError):
    request_headers = {}


# source: https://github.com/njanakiev/wikidata-mayors/blob/master/utils.py
def wikidata_query(query: str) -> dict:
    url = "https://query.wikidata.org/sparql"

    if cached_result := cache.wikidata_query_cache.get(query):
        # return cached result if possible (save wikidata requests)
        return cached_result

    try:
        # time.sleep(0.2)
        r = requests.get(url, params={"format": "json", "query": query}, headers=request_headers)
        if r.status_code != 200:
            # wikidata sometimes gives a 429 response as part of their rate-limiting policy
            # https://meta.wikimedia.org/wiki/User-Agent_policy
            print("waiting due to wikidata rate limit")
            time.sleep(2)
            r = requests.get(
                url, params={"format": "json", "query": query}, headers=request_headers
            )
        data = r.json()
    except json.JSONDecodeError as e:
        raise WikidataError(f"Invalid query: {e}")

    # save result for later usage
    cache.wikidata_query_cache[query] = data
    return data


cache.load_wdq_cache()  # load wikidata query cache


def get_superclasses(entity_id: str) -> list:
    """return json-list of direct superclasses

    :param entity_id:    str like "Q472971"
    """
    qs = f"wd:{entity_id} wdt:P279 ?item."

    return get_query_response(qs)


def get_instances(entity_id: str) -> list:
    """return json-list of direct superclasses

    :param entity_id:    str like "Q472971"
    """
    qs = f"?item wdt:P31 wd:{entity_id}."

    return get_query_response(qs)


def get_query_response(essential_query_str: str, distinct=False) -> list:
    """
    :param essential_query_str:    str like "wd:Q472971 wdt:P279 ?item."
    """

    if distinct:
        distinct_str = "DISTINCT"
    else:
        distinct_str = ""

    q = f"""
    SELECT {distinct_str} ?item ?itemLabel
    WHERE 
    {{
      {essential_query_str}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
    }}
    """
    # noinspection PyUnusedLocal
    try:
        res = wikidata_query(q)
    except WikidataError as e:
        print(e)
        return []

    entities = res["results"]["bindings"]

    entity_objects = []
    for e in entities:

        stored_object = WD_store.get(WDObject.get_id_from_raw_data(e))

        if stored_object:
            entity_objects.append(stored_object)
        else:
            entity_objects.append(WDObject(e))

    return entity_objects


class Node(object):
    def __init__(self, data: WDObject, id_in_repr: bool = True):
        self.is_top_level = False

        if isinstance(data, dict):
            data = AttributeDict(data)

        self.id = data.id
        self.smart_label = self.label = data.label
        if len(self.label) > 12:
            tmp = self.label  # "-".join(camel_case_split(self.label))
            self.smart_label = tmp.replace(" ", "\n").replace("_", "_\n").replace("-", "-\n")

        cache.node_cache[self.id] = self

        if id_in_repr:
            self.repr_str = f"{{{self.id}}}\n{self.smart_label}"
        else:
            self.repr_str = f"{self.smart_label}"

    def __repr__(self):
        # return f'<a href="http://www.wikidata.org/entity/{self.id}">{self.id}</a>\n{self.label}'
        return self.repr_str


def get_node(data: WDObject, **kwargs) -> Node:
    assert isinstance(data, WDObject)
    if n := cache.node_cache.get(data.id):
        return n
    else:
        return Node(data, **kwargs)


class GraphVisualizer(object):
    def __init__(self, show_labels_for_concepts: bool = True,
                 nodeclass=None):
        """
        :param show_labels_for_concepts:    bool, default=True; if False, only show `name`
        :param nodeclass:                   custom Node class or None (default)

        """
        self.show_labels_for_concepts = show_labels_for_concepts
        if nodeclass:
            self.nodeclass = nodeclass
            self.use_legacy_nodeclass = False
        else:
            self.nodeclass = Node
            self.use_legacy_nodeclass = True


        # Some (long) concept names have labels ending with "__disp".
        # These should be used instead of the actual name, because they fit into the circles.
        self.use_disp_labels = True

        self.concept_node_mapping = {}

    def get_node_from_owl_concept(self, concept: owl2.ThingClass):
        """
        :param concept:
        :return:
        """

        if self.use_disp_labels:
            for lbl in concept.label:
                if lbl.endswith("__disp"):
                    concept.name = lbl[:-6].strip()

        if self.show_labels_for_concepts and concept.label:

            graph_label = f"{concept.name}\n{concept.label[0]}"
        else:
            graph_label = f"{concept.name}"


        if self.use_legacy_nodeclass:
            data = WDObject(dict(id=f"{concept.iri}", label=graph_label))

            node = get_node(data, id_in_repr=False)
        else:
            # see demo notebook ontomathpro_viz1.ipynb for usage example
            node = self.nodeclass(concept)

        # also store the original concept object
        node.concept = concept
        self.concept_node_mapping[concept] = node

        return node

    def generate_taxonomy_graph_from_onto(
        self, base_concept: owl2.ThingClass, world: owl2.World = None
    ) -> nx.DiGraph:

        if world is None:
            world = owl2.default_world

        G = nx.DiGraph()

        base_node = self.get_node_from_owl_concept(base_concept)

        active_nodes = [base_node]
        G.add_node(base_node)

        while True:

            res_entities = []
            # set_trace()
            # print(active_nodes)
            for node in active_nodes:

                raw_subclasses = list(node.concept.subclasses(world=world))
                # some (strange) ontologies have owl2.Thing as a subclass of other classes
                # to prevent an infinity loop we simply ignore this
                try:
                    raw_subclasses.remove(owl2.Thing)
                except:
                    pass


                # print(raw_subclasses)
                subclasses = [self.get_node_from_owl_concept(concept) for concept in raw_subclasses]

                for cls in subclasses:
                    G.add_node(cls)
                    G.add_edge(cls, node)

                res_entities.extend(subclasses)

            active_nodes = res_entities

            if not active_nodes:
                break

        return G


# handle legacy typo
def vizualize_taxonomy(*args, **kwargs):
    return  visualize_taxonomy(*args, **kwargs)


def visualize_taxonomy(
    onto: owl2.Ontology, style: dict = None, svg_fname: str = None, scale: float = 1.0,
    nodeclass=None
):
    """
    create a svg image and display it in a Jupyter Notebook.

    :param onto:
    :param style:       (optional), hardcoded default
    :param svg_fname:   (optional), default -> tempfile
    :param scale:       scaling factor, default: 1.0
    :param nodeclass:   custom Node class, default: None

    :return:        IPython.display.HTML-Object
    """
    base_concept = owl2.Thing
    assert base_concept

    gv = GraphVisualizer(nodeclass=nodeclass)
    G = gv.generate_taxonomy_graph_from_onto(base_concept, world=onto.world)

    default_style = nxv.Style(
        graph={
            "rankdir": "BT",
        },
        node=lambda u, d: {
            "shape": "circle",
            "fixedsize": True,
            "width": 1,
            "fontsize": 10,
        },
        edge=lambda u, v, d: {"style": "solid", "arrowType": "normal", "label": "is a"},
    )

    if style is None:
        style = default_style
    svg_data = nxv.render(G, style, format="svg")
    if svg_fname is None:
        import tempfile

        svg_fname = tempfile.mktemp(suffix=".svg")

    with open(svg_fname, "wb") as svgfile:
        svgfile.write(svg_data)

    svg_abspath = os.path.abspath(svg_fname)
    url = f"file://{svg_abspath}"

    # unfortunately in jupyter notebooks links to absolute paths dont work
    display(HTML(f"path of the created image: {svg_abspath}"))

    res = SVG(svg_abspath)
    scale_svg(res, scale)
    return res


# http://www.graphviz.org/doc/info/attrs.html#d:nodesep
# define a style for unlabeled taxonomy
style_taxo_unlabeled = nxv.Style(
    graph={"rankdir": "BT", "nodesep": 0.05},
    node=lambda u, d: {
        "shape": "point",
        "fixedsize": True,
        "width": 0.1,
        "fontsize": 10,
    },
    edge=lambda u, v, d: {"style": "solid", "arrowhead": "none", "color": "#959595ff"},
)


def scale_svg(svg_object, scale=1.0):

    soup = BeautifulSoup(svg_object.data, "lxml")
    svg_elt = soup.find("svg")
    w = svg_elt.attrs["width"].rstrip("pt")
    h = svg_elt.attrs["height"].rstrip("pt")

    ws = float(w) * scale
    hs = float(h) * scale

    svg_elt.attrs["width"] = f"{ws}pt"
    svg_elt.attrs["height"] = f"{hs}pt"
    svg_elt.attrs["viewbox"] = f"0.00 0.00 {ws} {hs}"

    g_elt = svg_elt.find("g")
    tf = g_elt.attrs["transform"]
    # non-greedy regex-search-and-replace
    tf2 = re.sub("scale\(.*?\)", f"scale({scale} {scale})", tf)
    g_elt.attrs["transform"] = tf2

    svg_object.data = str(svg_elt)

    return svg_object


# noinspection PyShadowingNames
def build_graph(base_node: Node, n: int = 3) -> nx.DiGraph:
    """

    :param base_node:
    :param n:
    :return:
    """
    G = nx.DiGraph()
    active_nodes = [base_node]
    G.add_node(base_node)

    for i in range(n):

        res_entities = []
        for node in active_nodes:

            raw_sclss = get_superclasses(node.id)

            sclss = [get_node(data_dict) for data_dict in raw_sclss]

            if not sclss:
                node.is_top_level = True
            else:
                node.is_top_level = False

            for cls in sclss:
                G.add_node(cls)
                G.add_edge(node, cls)

            res_entities.extend(sclss)

        active_nodes = res_entities

    return G
