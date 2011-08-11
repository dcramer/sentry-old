"""
sentry.db.backends.sqlalchemy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

from sentry.db.backends.base import SentryBackend

import datetime

from sqlalchemy import create_engine
from sqlalchemy.sql import select

from sentry.db.backends.sqlalchemy.models import metadata, model_map

class SQLAlchemyBackend(SentryBackend):
    def __init__(self, uri, **kwargs):
        self.engine = create_engine(uri, **kwargs)
        metadata.bind = self.engine

    def create_model(self, schema):
        metadata.create(model_map[schema])

    ## Hash table lookups

    def add(self, schema, **values):
        # generates a pk and sets the values
        pk = self.generate_key(schema)
        table = model_map[schema]
        table.insert().execute(id=pk, **values)
        return pk

    def delete(self, schema, pk):
        table = model_map[schema]
        table.delete(table.c.id==pk).execute()

    def set(self, schema, pk, **values):
        table = model_map[schema]
        table.update(table.c.id==pk).execute(**values)

    def get(self, schema, pk):
        table = model_map[schema]
        query = select([table], table.c.id==pk)
        return query.execute().fetchone()

    def incr(self, schema, pk, key, amount=1):
        table = model_map[schema]
        table.update(table.c.id==pk).execute(getattr(table.c, key)==getattr(table.c, key) + amount)
    
    # meta data is stored in a seperate key to avoid collissions and heavy getall pulls

    def set_meta(self, schema, pk, **values):
        self.conn.hmset(self._get_metadata_key(schema, pk), values)

    def get_meta(self, schema, pk):
        return self.conn.hgetall(self._get_metadata_key(schema, pk))

    def get_data(self, schema, pk):
        return self.conn.hgetall(self._get_data_key(schema, pk))


    def count(self, schema, index='default'):
        return self.conn.zcard(self._get_index_key(schema, index))

    def list(self, schema, index='default', offset=0, limit=-1, desc=False):
        if limit > 0:
            end = offset+limit
        else:
            end = limit
        pk_set = self.conn.zrange(self._get_index_key(schema, index), start=offset, end=end, desc=desc)
        return [(pk, self.get_data(schema, pk)) for pk in pk_set]

    ## Indexes using sorted sets

    def add_relation(self, from_schema, from_pk, to_schema, to_pk, score):
        # adds a relation to a sorted index for base instance
        if isinstance(score, datetime.datetime):
            score = score.strftime('%s.%m')
        self.conn.zadd(self._get_relation_key(from_schema, from_pk, to_schema), to_pk, float(score))

    def remove_relation(self, from_schema, from_pk, to_schema, to_pk=None):
        if to_pk:
            self.conn.zrem(self._get_relation_key(from_schema, from_pk, to_schema), to_pk)
        else:
            self.conn.delete(self._get_relation_key(from_schema, from_pk, to_schema))

    def list_relations(self, from_schema, from_pk, to_schema, offset=0, limit=-1, desc=False):
        # lists relations in a sorted index for base instance
        # XXX: this is O(n)+1, ugh
        if limit > 0:
            end = offset+limit
        else:
            end = limit
            
        pk_set = self.conn.zrange(self._get_relation_key(from_schema, from_pk, to_schema), start=offset, end=end, desc=desc)

        return [(pk, self.conn.hgetall(self._get_data_key(to_schema, pk))) for pk in pk_set]

    def add_to_index(self, schema, pk, index, score):
        # adds an instance to a sorted index
        if isinstance(score, datetime.datetime):
            score = score.strftime('%s.%m')
        self.conn.zadd(self._get_index_key(schema, index), pk, float(score))

    def remove_from_index(self, schema, pk, index):
        self.conn.zrem(self._get_index_key(schema, index), pk)

    ## Generic indexes

    # TODO: can we combine constraint indexes with sort indexes? (at least the API)

    def add_to_cindex(self, schema, pk, **kwargs):
        # adds an index to a composite index (for checking uniqueness)
        self.conn.sadd(self._get_constraint_key(schema, kwargs), pk)

    def remove_from_cindex(self, schema, pk, **kwargs):
        # adds an index to a composite index (for checking uniqueness)
        self.conn.srem(self._get_constraint_key(schema, kwargs), pk)

    def list_by_cindex(self, schema, **kwargs):
        # returns a list of keys associated with a constraint
        return list(self.conn.smembers(self._get_constraint_key(schema, kwargs)))
