import hashlib
import uuid

class SentryBackend(object):
    def _get_schema_name(self, schema):
        return schema.__name__.lower()

    def _get_composite_key(self, *keys):
        return hashlib.md5('_'.join(keys)).hexdigest()

    def generate_key(self, schema):
        return uuid.uuid4().hex
