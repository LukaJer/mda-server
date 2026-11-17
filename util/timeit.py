from functools import wraps
from time import time


class _Colors:
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


_CRITICAL_EXECUTION_TIME_IN_MS = 40.0


def timeit(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time()
        result = f(*args, **kw)
        te = time()
        duration = (te-ts)*1000

        timing_color = _Colors.GREEN if duration < _CRITICAL_EXECUTION_TIME_IN_MS else _Colors.RED
        if duration > _CRITICAL_EXECUTION_TIME_IN_MS:
            print(f'# Timing: {_Colors.BLUE}{f.__name__}{_Colors.END}(args={args}, kwargs={kw}) {timing_color}{(te-ts)*1000}{_Colors.END}ms')
        return result
    return wrap

