import threading

try:
    import requests  # type: ignore
except Exception:
    requests = None  # type: ignore

_tls = threading.local()


def get_thread_session(timeout: float = 10.0, pool_maxsize: int = 10):
    if requests is None:
        return None
    sess = getattr(_tls, "session", None)
    if sess is None:
        sess = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=pool_maxsize, pool_maxsize=pool_maxsize, max_retries=0)
        sess.mount("http://", adapter)
        sess.mount("https://", adapter)
        _tls.session = sess
    return sess

