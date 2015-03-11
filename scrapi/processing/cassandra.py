from __future__ import absolute_import

import json
import logging
from uuid import uuid4

from cqlengine import columns, Model

from scrapi import events
from scrapi import database  # noqa
from scrapi.processing.base import BaseProcessor


logger = logging.getLogger(__name__)
logging.getLogger('cqlengine.cql').setLevel(logging.WARN)


class CassandraProcessor(BaseProcessor):
    '''
    Cassandra processor for scrapi. Handles versioning and storing documents in Cassandra
    '''
    NAME = 'cassandra'

    @events.logged(events.PROCESSING, 'normalized.cassandra')
    def process_normalized(self, raw_doc, normalized):
        self.send_to_database(
            docID=normalized["id"]['serviceID'],
            source=normalized['source'],
            url=normalized['id']['url'],
            contributors=json.dumps(normalized['contributors']),
            id=normalized['id'],
            title=normalized['title'],
            tags=normalized['tags'],
            dateUpdated=normalized['dateUpdated'],
            properties=json.dumps(normalized['properties'])
        ).save()

    @events.logged(events.PROCESSING, 'raw.cassandra')
    def process_raw(self, raw_doc):
        self.send_to_database(**raw_doc.attributes).save()

    def send_to_database(self, docID, source, **kwargs):
        documents = DocumentModel.objects(docID=docID, source=source)
        if documents:
            document = documents[0]
            # Create new version, get UUID of new version, update
            versions = document.versions
            if document.url:
                version = VersionModel(key=uuid4(), **dict(document))
                version.save()
                versions.append(version.key)
            return document.update(versions=versions, **kwargs)
        else:
            # create document
            return DocumentModel.create(docID=docID, source=source, **kwargs)


@database.register_model
class DocumentModel(Model):
    '''
    Defines the schema for a metadata document in cassandra

    The schema contains denormalized raw document, denormalized
    normalized (so sorry for the terminology clash) document, and
    a list of version IDs that refer to previous versions of this
    metadata.
    '''
    __table_name__ = 'documents'

    # Raw
    docID = columns.Text(primary_key=True)
    source = columns.Text(primary_key=True, index=True, clustering_order="DESC")

    doc = columns.Bytes()
    filetype = columns.Text()
    timestamps = columns.Map(columns.Text, columns.Text)

    # Normalized
    url = columns.Text()
    title = columns.Text()
    properties = columns.Text()
    dateUpdated = columns.Text()
    description = columns.Text()
    contributors = columns.Text()  # TODO This should use user-defined types (when they're added)
    tags = columns.List(columns.Text())
    id = columns.Map(columns.Text, columns.Text)

    # Additional metadata
    versions = columns.List(columns.UUID)


@database.register_model
class VersionModel(Model):
    '''
    Defines the schema for a version of a metadata document in Cassandra

    See the DocumentModel class. This schema is very similar, except it is
    keyed on a UUID that is generated by us, rather than it's own metadata
    '''

    __table_name__ = 'versions'

    key = columns.UUID(primary_key=True, required=True)

    # Raw
    doc = columns.Bytes()
    docID = columns.Text()
    filetype = columns.Text()
    source = columns.Text(index=True)
    timestamps = columns.Map(columns.Text, columns.Text)

    # Normalized
    url = columns.Text()
    title = columns.Text()
    properties = columns.Text()  # TODO
    dateUpdated = columns.Text()
    description = columns.Text()
    contributors = columns.Text()  # TODO: When supported, this should be a user-defined type
    tags = columns.List(columns.Text())
    id = columns.Map(columns.Text, columns.Text)

    # Additional metadata
    versions = columns.List(columns.UUID)