import os
import sys
import requests
import json
import time

import networkx as nx
import owlready2 as owl2


from . import cache

from .release import __version__

# noinspection PyUnresolvedReferences
# for debugging
from ipydex import IPS


BASEPATH = os.path.dirname((os.path.dirname(os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__)))))


class WikidataError(ValueError):
    pass


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
def wikidata_query2(query: str) -> dict:
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
            r = requests.get(url, params={"format": "json", "query": query}, headers=request_headers)
        data = r.json()
    except json.JSONDecodeError as e:
        raise WikidataError(f"Invalid query: {e}")

    # save result for later usage
    cache.wikidata_query_cache[query] = data
    return data


def get_superclasses(entity_id: str) -> list:
    """
    :param entity_id:    str like "Q472971"
    """

    q = f"""
    SELECT ?item ?itemLabel 
    WHERE 
    {{
      wd:{entity_id} wdt:P279 ?item.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
    }}
    """
    # noinspection PyUnusedLocal
    try:
        res = wikidata_query2(q)
    except WikidataError as e:
        return []

    entities = res["results"]["bindings"]

    for ent in entities:
        ent["id"] = ent["item"]["value"].replace("http://www.wikidata.org/entity/", "")
        ent["label"] = ent["itemLabel"]["value"]

    return entities


class Node(object):
    def __init__(self, data: dict, id_in_repr: bool = True):
        self.is_top_level = False
        self.id = data["id"]
        self.smart_label = self.label = data["label"]
        if len(self.label) > 16:
            self.smart_label = self.label.replace(" ", "\n")

        cache.node_cache[self.id] = self

        if id_in_repr:
            self.repr_str = f"{{{self.id}}}\n{self.smart_label}"
        else:
            self.repr_str = f"{self.smart_label}"

    def __repr__(self):
        # return f'<a href="http://www.wikidata.org/entity/{self.id}">{self.id}</a>\n{self.label}'
        return self.repr_str


def get_node(data: dict, **kwargs) -> Node:
    if n := cache.node_cache.get(data["id"]):
        return n
    else:
        return Node(data, **kwargs)


def get_node_from_owl_concept(concept: owl2.ThingClass):
    """

    :param concept:
    :return:
    """

    if concept.label:

        graph_label = f"{concept.name}\n{concept.label[0]}"
    else:
        graph_label = f"{concept.name}"

    data = dict(id=f"{concept.iri}", label=graph_label)

    node = get_node(data, id_in_repr=False)

    # also store the original concept object
    node.concept = concept

    return node



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

cache.load_wdq_cache()


def generate_taxonomy_graph_from_onto(base_concept: owl2.ThingClass) -> nx.DiGraph:

    G = nx.DiGraph()

    base_node  = get_node_from_owl_concept(base_concept)

    active_nodes = [base_node]
    G.add_node(base_node)

    while True:

        res_entities = []
        for node in active_nodes:

            raw_subclasses = node.concept.subclasses()
            subclasses = [get_node_from_owl_concept(concept) for concept in raw_subclasses]

            for cls in subclasses:
                G.add_node(cls)
                G.add_edge(cls, node)

            res_entities.extend(subclasses)

        active_nodes = res_entities

        if not active_nodes:
            break

    return G
