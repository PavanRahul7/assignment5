import sys
import types

# Minimal stub for pandas used in tests: DataFrame, read_csv
pd = types.ModuleType('pandas')

class DataFrame:
    def __init__(self, data=None, **kwargs):
        # Support DataFrame(dict) and DataFrame(columns=[...])
        if data is None:
            cols = kwargs.get('columns') or []
            self._data = {c: [] for c in cols}
        elif isinstance(data, dict):
            self._data = data
        else:
            self._data = data

    @property
    def empty(self):
        if not self._data:
            return True
        # consider empty if all columns have no entries
        return all(len(v) == 0 for v in self._data.values())

    def to_csv(self, *args, **kwargs):
        return None

    def iterrows(self):
        # Iterate rows yielding (index, dict)
        if not self._data:
            return iter(())
        cols = list(self._data.keys())
        n = max((len(v) for v in self._data.values()), default=0)
        def gen():
            for i in range(n):
                row = {c: (self._data[c][i] if i < len(self._data[c]) else None) for c in cols}
                yield i, row
        return gen()

pd.DataFrame = DataFrame

def read_csv(*args, **kwargs):
    # Return an empty DataFrame or accept dict-like via kwargs
    return DataFrame()

pd.read_csv = read_csv
sys.modules['pandas'] = pd

# Minimal stub for dotenv
dotenv = types.ModuleType('dotenv')
def load_dotenv(*a, **k):
    return None
dotenv.load_dotenv = load_dotenv
sys.modules['dotenv'] = dotenv
