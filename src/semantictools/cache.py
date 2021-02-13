import os
import pickle
from typing import Union
import glob
import tempfile


node_cache = {}


wikidata_query_cache = {}

wdq_cache_path = None


def get_cachepath(cachepath: str = None, suffix2: str = "", create_new_file: Union[bool, str] = True) -> Union[str, None]:
    """
    :param cachepath:           desired value to return
                                (useful for uniform kwarg-handling in load_ and save_save_wdq_cache)
    :param suffix2:             optional suffix
    :param create_new_file:     bool or "force"

    :return:    abspath of current cache file or None

    Side effects: change wdq_cache_path
    """

    global wdq_cache_path

    if cachepath and create_new_file != "force":
        wdq_cache_path = cachepath
        return cachepath

    suffix = f"_semantictools_wdq_cache{suffix2}.pcl"

    dirpath = tempfile.gettempdir()

    # this is a list of absolute paths
    list_of_files = glob.glob(os.path.join(dirpath, f"*{suffix}"))
    if list_of_files and create_new_file != "force":
        # use existing file
        latest_file = max(list_of_files, key=os.path.getctime)

        cachepath = latest_file
    elif create_new_file is True:
        # use exisiting filename or create a new one if necessary
        cachepath = wdq_cache_path or tempfile.mktemp(suffix=suffix)
    elif create_new_file == "force":
        cachepath = tempfile.mktemp(suffix=suffix)
    elif create_new_file is True:
        if wdq_cache_path is not None:
            msg = f"Not allowed to create a new cache filename because of already exsiting: {wdq_cache_path}" \
                   " use option `create_new_file='force' to override."
            raise ValueError(msg)
        cachepath = tempfile.mktemp(suffix=suffix)
    else:
        cachepath = None

    wdq_cache_path = cachepath
    return cachepath


def load_wdq_cache(**kwargs) -> dict:
    """

    :return:    loaded data (dict)
    """

    cachepath = get_cachepath(**kwargs)

    if not os.path.isfile(cachepath):
        return {}

    with open(cachepath, "rb") as pfile:
        wdq_cache = pickle.load(pfile)

        wikidata_query_cache.update(wdq_cache)

        return wdq_cache


def save_wdq_cache(**kwargs) -> None:
    """

    :return:     None
    """
    cachepath = get_cachepath(**kwargs)

    with open(cachepath, "wb") as pfile:
        pickle.dump(wikidata_query_cache, pfile)
