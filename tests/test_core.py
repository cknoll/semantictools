import os
import sys
import unittest
import typing
import pydantic

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception

BASEPATH = os.path.dirname(os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__)))


# noinspection PyPep8Naming
class TestCore(unittest.TestCase):
    def setUp(self):
        pass

    def test1(self):
        pass
