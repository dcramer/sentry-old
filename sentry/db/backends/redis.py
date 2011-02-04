from __future__ import absolute_import

from sentry.db.backends.base import SentryBackend

import datetime
import redis

class RedisBackend(SentryBackend):
    def __init__(self, host='localhost', port=6379, db=0):
        self.conn = redis.Redis(host, port, db)
        # TODO: REMOVE THIS SHIT ASAP
        self.conn.flush()

    ## Hash table lookups

    def add(self, schema, **values):
        # generates a pk and sets the values
        pk = self.generate_key(schema)
        self.set(schema, pk, **values)
        return pk

    def set(self, schema, pk, **values):
        self.conn.hmset('data:%s:%s' % (self._get_schema_name(schema), pk), values)

    def get(self, schema, pk):
        return self.conn.hgetall('data:%s:%s' % (self._get_schema_name(schema), pk))

    def incr(self, schema, pk, key, amount=1):
        return self.conn.hincrby('data:%s:%s' % (self._get_schema_name(schema), pk), key, amount)

    ## Indexes using sorted sets

    def list(self, schema, index='default', offset=0, limit=0, desc=False):
        schema = self._get_schema_name(schema)
        pk_set = self.conn.zrange('index:%s:%s' % (schema, index), start=offset, end=offset+limit, desc=desc)
        return [(pk, self.conn.hgetall('data:%s:%s' % (schema, pk))) for pk in pk_set]

    def add_relation(self, from_schema, from_pk, to_schema, to_pk, score):
        # adds a relation to a sorted index for base instance
        if isinstance(score, datetime.datetime):
            score = score.strftime('%s.%m')
        self.conn.zadd('rindex:%s:%s:%s' % (self._get_schema_name(from_schema), from_pk, self._get_schema_name(to_schema)), to_pk, float(score))

    def list_relations(self, from_schema, from_pk, to_schema, offset=0, limit=100, desc=False):
        # lists relations in a sorted index for base instance
        # XXX: this is O(n)+1, ugh
        to_schema = self._get_schema_name(to_schema)

        pk_set = self.conn.zrange('rindex:%s:%s:%s' % (self._get_schema_name(from_schema), from_pk, to_schema), start=offset, end=offset+limit, desc=desc)
        return [(pk, self.conn.hgetall('data:%s:%s' % (to_schema, pk))) for pk in pk_set]

    def add_to_index(self, schema, pk, index, score):
        # adds an instance to a sorted index
        # TODO: this has to deal w/ partitioning the data otherwise the zset is too big
        #       to do this we parition the index by day and paginate through days until we get the
        #        number of results that we want.
        if isinstance(score, datetime.datetime):
            score = score.strftime('%s.%m')
        self.conn.zadd('index:%s:%s' % (self._get_schema_name(schema), index), pk, float(score))

    ## Generic indexes

    def add_to_cindex(self, schema, pk, **keys):
        # adds an index to a composite index (for checking uniqueness)
        self.conn.set('cindex:%s:%s' % (self._get_schema_name(schema), self._get_composite_key(**keys)), pk)

    def get_by_cindex(self, schema, **keys):
        # returns the primary key of an object from a composite index
        return self.conn.get('cindex:%s:%s' % (self._get_schema_name(schema), self._get_composite_key(**keys)))
