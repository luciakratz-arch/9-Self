import os

class _Param:
    def __init__(self, val): self._val = val
    @property
    def value(self): return self._val

GMAIL_PASS     = _Param(os.environ.get('GMAIL_PASS', ''))
MP_TOKEN       = _Param(os.environ.get('MP_TOKEN', ''))
STORAGE_BUCKET = _Param(os.environ.get('STORAGE_BUCKET', 'entrevista-inicial.firebasestorage.app'))
