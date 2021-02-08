from datetime import date, datetime
import requests
import six

from grnhse.exceptions import (
    HarvestForbiddenError,
    HarvestHTTPException,
    HarvestObjectNotFoundError,
    HarvestRateLimitError,
    HarvestServerError,
    HarvestUnauthorizedError,
    HarvestValidationError,
    InvalidAPIVersion,
    InvalidAPICallError,
    EndpointNotFound,
)
from grnhse.harvest.versions import api_versions
from grnhse.util import extract_header_links, strf_dt


def raise_harvest_exception(resp, *args, **kwargs):
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        if resp.status_code == requests.codes.UNAUTHORIZED:
            raise HarvestUnauthorizedError("Invalid Harvest API key")

        if resp.status_code == requests.codes.FORBIDDEN:
            raise HarvestForbiddenError("You do not have access to that record")

        if resp.status_code == requests.codes.NOT_FOUND:
            raise HarvestObjectNotFoundError("Resource not found")

        if resp.status_code == requests.codes.UNPROCESSABLE_ENTITY:
            try:
                data = resp.json()
                errors = data['errors']
            except ValueError:
                errors = []

            raise HarvestValidationError(
                "Validation Error",
                errors=errors,
            )

        if resp.status_code == requests.codes.TOO_MANY_REQUESTS:
            raise HarvestRateLimitError("Rate limit exceeded")

        if resp.status_code == requests.codes.INTERNAL_SERVER_ERROR:
            raise HarvestServerError("Server error")

        raise HarvestHTTPException('{r.status_code} {r.text}'.format(r=resp))


class SessionAuthMixin(object):
    _api_key = None
    _session = None

    def __init__(self, api_key):
        self._api_key = api_key
        self._session = requests.Session()
        self._session.hooks["response"] = [raise_harvest_exception]
        self._set_auth()

    def _set_auth(self):
        if self._api_key is not None:
            auth = (self._api_key, '')
            self._session.auth = auth


class Harvest(object):
    def __init__(self, api_key=None, version='v1'):
        self._api_key = api_key
        self._version = version

        self._api = api_versions.get(version, None)
        if self._api is None:
            raise InvalidAPIVersion(version)

        self._base_url = self._api['base']
        self._uris = self._api['uris']

    def __repr__(self):
        return '<Harvest API {self._version}>'.format(self=self)

    @property
    def api_key(self):
        key_last_4 = self._api_key[-4:]
        hidden_key = '********' + key_last_4
        return hidden_key

    def __getattr__(self, key):
        endpoint = str(key)
        uris = self._uris['direct'].get(endpoint, None)

        if uris is not None:
            related = self._uris['related'].get(endpoint, None)
            return HarvestObject(endpoint,
                                 self._api_key, self._base_url,
                                 uris.get('list'), uris.get('retrieve'),
                                 related=related)
        else:
            raise EndpointNotFound(endpoint)

    @staticmethod
    def versions():
        return ', '.join(api_versions.keys())


class HarvestObject(SessionAuthMixin):
    _object_id = None
    _params = None
    _on_behalf_of = None

    def __init__(self, name, api_key, base_url, list_uri, retrieve_uri, related=None, on_behalf_of=None):
        super(HarvestObject, self).__init__(api_key)

        self._base_url = base_url
        self._list = base_url + list_uri if list_uri else None
        self._retrieve = base_url + retrieve_uri if retrieve_uri else None

        self._related = related
        self._name = name.replace('_', ' ').title()

        self._on_behalf_of = on_behalf_of

        self._next_url = None
        self._last_url = None

    def __repr__(self):
        if self._object_id is not None:
            return '<{self._name} Endpoint (id={self._object_id})>'.format(self=self)
        return '<{self._name} Endpoint>'.format(self=self)

    def __call__(self, object_id=None, **params):
        self._object_id = object_id
        self._set_params(**params)
        return self

    def __getattr__(self, key):
        endpoint = str(key)
        uris = self._related.get(endpoint, None)
        if uris is not None:
            if self._object_id is None:
                raise InvalidAPICallError(
                    'Cannot query related object {} without selecting an object id first'.format(endpoint))

            list_uri = (
                uris['list'].format(rel_id=self._object_id) if uris.get('list') else None)
            retrieve_uri = (
                uris['retrieve'].format(rel_id=self._object_id) if uris.get('retrieve') else None)

            return HarvestObject(endpoint,
                                 self._api_key, self._base_url,
                                 list_uri, retrieve_uri)
        else:
            raise EndpointNotFound(endpoint)

    def __iter__(self):
        if self._object_id is not None:
            self._next_url = self._retrieve.format(id=self._object_id)
        else:
            self._next_url = self._list
        return self

    def __next__(self):
        try:
            return self.get_next()
        except AttributeError:
            raise StopIteration()

    next = __next__

    @property
    def records_remaining(self):
        return self._next_url is not None

    def _set_params(self, **params):
        if params:
            params = {
                k: strf_dt(v) if isinstance(v, (date, datetime)) else v
                for k, v in six.iteritems(params)}
            if self._params is None:
                self._params = {}
            self._params.update(**params)

    def _process_header_links(self, headers):
        header_links = extract_header_links(headers.get('link'))
        self._next_url = header_links.get('next', None)
        self._last_url = header_links.get('last', None)

    def _get(self, url, params=True):
        _params = self._params if params is True else None
        response = self._session.get(url, params=_params)

        self._process_header_links(response.headers)
        return response.json()

    def get(self, object_id=None, **params):
        oid = object_id or self._object_id
        if oid is not None:
            url = self._retrieve or self._list
            url = url.format(id=oid)
        elif self._list is not None:
            url = self._list
        else:
            raise InvalidAPICallError('Must provide object id')
        self._set_params(**params)
        return self._get(url)

    def get_next(self):
        if self._next_url is None:
            raise AttributeError('Next url is not set, try querying a plain get() first')
        return self._get(self._next_url, params=False)

    def get_last(self):
        if self._last_url is None:
            raise AttributeError('Last url is not set, try querying a plain get() first')
        return self._get(self._last_url, params=False)

    def _post(self, url, data, on_behalf_of):
        response = self._session.post(url, json=data, headers={'On-Behalf-Of': on_behalf_of})
        return response.json()

    def post(self, data, on_behalf_of=None):
        onb = on_behalf_of or self._on_behalf_of

        if onb is None:
            raise InvalidAPICallError('on_behalf_of must either be passed or set on the Harvest instance')

        if self._object_id:
            raise InvalidAPICallError('Cannot POST with an object id')

        if not self._list:
            raise InvalidAPICallError('Cannot POST without a list url')

        url = self._list
        return self._post(url, data, onb)
