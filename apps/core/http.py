"""A small JSON-over-HTTP client for the outside services CHORD calls.

Every outside call goes through ``request()``, so tests can swap the
transport (``use_transport``) and never touch the network. The test runner
installs a transport that fails loudly (see ``apps/core/testing.py``).
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field


class HttpError(Exception):
    """The request never got an answer: no network, a timeout, a bad host."""


@dataclass
class Response:
    status: int
    data: object = None  # the parsed JSON body, or None when it isn't JSON
    headers: dict = field(default_factory=dict)  # names in lower case
    text: str = ""

    @property
    def ok(self):
        return 200 <= self.status < 300


def urllib_transport(method, url, *, headers, body, timeout):
    request_ = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request_, timeout=timeout) as reply:  # noqa: S310
            return _response(reply.status, reply.headers, reply.read())
    except urllib.error.HTTPError as error:
        return _response(error.code, error.headers, error.read())
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise HttpError(str(getattr(error, "reason", error))) from error


def _response(status, headers, raw):
    text = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(text) if text else None
    except ValueError:
        data = None
    return Response(
        status=status,
        data=data,
        headers={name.lower(): value for name, value in headers.items()},
        text=text,
    )


_transport = urllib_transport


def request(
    method, url, *, params=None, headers=None, json_body=None, form=None, timeout=20
):
    """Send one request and return its ``Response`` (any status).

    ``params`` go in the query string, ``json_body`` is sent as JSON and
    ``form`` as a URL-encoded form. Raises ``HttpError`` when there is no
    answer at all.
    """
    if params:
        query = urllib.parse.urlencode(
            {key: value for key, value in params.items() if value not in (None, "")}
        )
        url = f"{url}?{query}"
    headers = dict(headers or {})
    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    elif form is not None:
        body = urllib.parse.urlencode(form).encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    return _transport(method, url, headers=headers, body=body, timeout=timeout)


@contextmanager
def use_transport(transport):
    """Send every request through ``transport`` inside the block."""
    global _transport
    previous, _transport = _transport, transport
    try:
        yield transport
    finally:
        _transport = previous


def set_transport(transport):
    """Replace the transport for the rest of the process; returns the old one."""
    global _transport
    previous, _transport = _transport, transport
    return previous
