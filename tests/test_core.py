import os
import sys
import unittest
import semantictools as smt
import time

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception

BASEPATH = os.path.dirname(os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__)))


# noinspection PyPep8Naming
class TestWikidata(unittest.TestCase):
    def setUp(self):
        pass

    def test_get_superclass(self):
        base_node = smt.Node({"id": "Q125977", "label": "vector space"})

        res1 = smt.get_superclasses(base_node.id)
        self.assertEqual(len(res1), 2)
        res_nodes = [smt.get_node(data) for data in res1]
        self.assertEqual(res_nodes[0].label, "space (mathematics)")
        self.assertEqual(res_nodes[1].label, "free module")

    def test_build_graph(self):
        base_node = smt.Node({"id": "Q125977", "label": "vector space"})

        G = smt.build_graph(base_node, n=4)
        self.assertEquals(list(G.predecessors(base_node)), [])

        # select special node:
        n1 = [k for k in G.nodes.keys() if "flat module" in str(k)][0]

        scs = smt.get_superclasses(n1.id)
        res_nodes = [smt.get_node(data) for data in scs]
        self.assertEquals(list(G.successors(n1)), res_nodes)

    def test_load_cache(self):
        self.assertEqual(smt.cache.wdq_cache_path, None)
        res = smt.cache.load_wdq_cache(suffix2="_test")
        self.assertEqual(res, {})
        self.assertTrue(smt.cache.wdq_cache_path.endswith("_semantictools_wdq_cache_test.pcl"))

        self.assertEqual(len(smt.cache.wikidata_query_cache), 0)

        t1 = time.time()
        # with empty cache
        _ = smt.get_superclasses("Q125977")
        t2 = time.time()
        # with filled cache
        _ = smt.get_superclasses("Q125977")
        t3 = time.time()

        # ensure speedup due to cache
        self.assertGreater((t2 - t1) / (t3 - t2), 100)
        self.assertEqual(len(smt.cache.wikidata_query_cache), 1)

        smt.cache.save_wdq_cache(suffix2="_test")

        res = smt.cache.load_wdq_cache(suffix2="_test")
        self.assertEqual(len(res), 1)
        os.remove(smt.cache.wdq_cache_path)
