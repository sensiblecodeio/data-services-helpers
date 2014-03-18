#!/usr/bin/env python
# encoding: utf-8

from __future__ import unicode_literals

import datetime
import logging
import requests
import requests_cache
import time
import urlparse

from contextlib import contextmanager
from cStringIO import StringIO

from nose.tools import assert_equal, assert_raises
from mock import call, patch

import scraperwiki
from requests.structures import CaseInsensitiveDict
L = logging.getLogger('sw.ds.helpers')

_MAX_RETRIES = 5
_TIMEOUT = 60
_HIT_PERIOD = 2  # seconds between requests to the same domain

_RATE_LIMIT_ENABLED = True  # Used inside rate_limit_disabled() context manager
_LAST_TOUCH = {}            # domain name => datetime

_USER_AGENT = 'ScraperWiki Limited (bot@scraperwiki.com)'

__all__ = ["update_status", "install_cache", "download_url",
           "rate_limit_disabled", 'batch_processor']


@contextmanager
def batch_processor(callback, batch_size=2000):
    processor = BatchProcessor(callback, batch_size)
    try:
        yield processor
    finally:
        processor.flush()


class BatchProcessor(object):
    """
    You can push items here and they'll be stored in a queue. When batch_size
    items have been pushed, the given callback is called with the list of
    items and the queue is cleared.

    Note: You must call flush() to process the final items: this is not done
    automatically (yet)
    """
    def __init__(self, callback, batch_size):
        self.queue = []
        self.callback = callback
        self.batch_size = batch_size

    def push(self, row):
        self.queue.append(row)
        if len(self.queue) >= self.batch_size:
            self.flush()

    def flush(self):
        self.callback(self.queue)
        self.queue = []


def update_status(table_name="swdata", date_column="date"):
    """
    Set the status endpoint on ScraperWiki to the latest entry e.g.
    'Latest entry: 2013-10-01'
    """
    status_text = 'Latest entry: {}'.format(
        _get_most_recent_record(table_name, date_column))
    L.info(status_text)

    scraperwiki.status('ok', status_text)


def _get_most_recent_record(table_name, column):
    result = scraperwiki.sql.select(
        "MAX({1}) AS most_recent FROM {0} LIMIT 1".format(table_name, column))
    return result[0]['most_recent']


def install_cache(expire_after=12 * 3600):
    """
    Patches the requests library with requests_cache.
    """
    requests_cache.install_cache(
        expire_after=expire_after,
        allowable_methods=('GET',))


def download_url(url, back_off=True, **kwargs):
    """
    Get the content of a URL and return a file-like object.
    back_off=True provides retry
    """
    if back_off:
        return _download_with_backoff(url, as_file=True, **kwargs)
    else:
        return _download_without_backoff(url, as_file=True, **kwargs)

def request_url(url, back_off=True, **kwargs):
    if back_off:
        return _download_with_backoff(url, as_file=False, **kwargs)
    else:
        return _download_without_backoff(url, as_file=False, **kwargs)


@contextmanager
def rate_limit_disabled():
    global _RATE_LIMIT_ENABLED
    _RATE_LIMIT_ENABLED = False
    try:
        yield
    finally:
        _RATE_LIMIT_ENABLED = True


def _download_without_backoff(url, as_file=True, **kwargs):
    """
    Get the content of a URL and return a file-like object.
    """
    kwargs_copy = dict(kwargs)
    if not _url_in_cache(url):
        now = datetime.datetime.now()
        _rate_limit_for_url(url, now)
        _rate_limit_touch_url(url, now)

    L.info("Download {}".format(url))
    if 'timeout' not in kwargs_copy:
        kwargs_copy['timeout'] = _TIMEOUT
    if 'headers' in kwargs_copy:
        head_dict = CaseInsensitiveDict(kwargs_copy['headers'])
        if 'user-agent' not in head_dict:
            head_dict['user-agent'] = _USER_AGENT
        kwargs_copy['headers'] = head_dict
    else:
        kwargs_copy['headers'] = CaseInsensitiveDict({'user-agent': _USER_AGENT})

    response = requests.get(url, **kwargs_copy)

    L.debug('"{}"'.format(response.text))

    response.raise_for_status()

    if as_file:
        return StringIO(response.content)
    else:
        return response


def _download_with_backoff(url, **kwargs):
    next_delay = 10

    for n in range(0, _MAX_RETRIES):
        try:
            return _download_without_backoff(url, **kwargs)
        except requests.exceptions.RequestException as e:
            L.exception(e)
            L.info("Retrying in {} seconds: {}".format(next_delay, url))
            time.sleep(next_delay)
            next_delay *= 2

    raise RuntimeError('Max retries exceeded for {0}'.format(url))


def _url_in_cache(url):
    """
    If requests_cache is in use, return whether or not the URL is in the cache.
    If not, return False.
    """
    try:
        return requests_cache.get_cache().has_url(url)
    except AttributeError as e:  # requests_cache not enabled
        if e.message == "'Session' object has no attribute 'cache'":
            return False
        raise


def _rate_limit_for_url(url, now=datetime.datetime.now()):
    """
    """
    if not _RATE_LIMIT_ENABLED:
        return
    domain = _get_domain(url)
    last_touch = _LAST_TOUCH.get(domain)

    if last_touch:
        delta = now - last_touch
        if delta < datetime.timedelta(seconds=_HIT_PERIOD):
            wait = _HIT_PERIOD - delta.total_seconds()
            L.debug("Rate limiter: sleeping {}s".format(wait))
            time.sleep(wait)


def _rate_limit_touch_url(url, now=None):
    if now is None:
        now = datetime.datetime.now()
    domain = _get_domain(url)
    L.debug("Recording hit for domain {} at {}".format(domain, now))
    _LAST_TOUCH[domain] = now


def _get_domain(url):
    """
    _get_domain('http://foo.bar/baz/')
    u'foo.bar'
    """
    return urlparse.urlparse(url).netloc


def test_rate_limit_touch_url_works():

    time = datetime.datetime(2010, 11, 1, 10, 15, 30)

    with patch.dict(_LAST_TOUCH, {}, clear=True):
        assert_equal({}, _LAST_TOUCH)
        _rate_limit_touch_url('http://foo.com/bar', now=time)
        assert_equal({'foo.com': time}, _LAST_TOUCH)


@patch('time.sleep')
def test_rate_limit_no_sleep_if_outside_period(mock_sleep):
    previous_time = datetime.datetime(2013, 10, 1, 10, 15, 30)

    with patch.dict(_LAST_TOUCH, {}, clear=True):
        _rate_limit_touch_url('http://foo.com/bar', now=previous_time)
        _rate_limit_for_url(
            'http://foo.com/bar',
            now=previous_time + datetime.timedelta(seconds=_HIT_PERIOD))

    mock_sleep.assert_not_called()


@patch('time.sleep')
def test_rate_limit_sleeps_up_to_correct_period(mock_sleep):
    previous_time = datetime.datetime(2013, 10, 1, 10, 15, 30)

    with patch.dict(_LAST_TOUCH, {}, clear=True):
        _rate_limit_for_url(
            'http://foo.com/bar',
            now=previous_time)

        mock_sleep.assert_not_called()

        _rate_limit_touch_url('http://foo.com/bar', now=previous_time)

        _rate_limit_for_url(
            'http://foo.com/bar',
            now=previous_time + datetime.timedelta(
                seconds=1, microseconds=500000))

    mock_sleep.assert_called_once_with(_HIT_PERIOD - 1.5)

@patch('dshelpers.requests.get')
def test_passes_headers_through(mock_requests_get):
    fake_response = requests.Response()
    fake_response.status_code = 200
    fake_response._content = str("Hello")
    mock_requests_get.return_value = fake_response
    _download_with_backoff('http://fake_url.com', headers={'this':'included'})
    mock_requests_get.assert_called_with(u'http://fake_url.com', headers=CaseInsensitiveDict({u'this': u'included', u'user-agent': u'ScraperWiki Limited (bot@scraperwiki.com)'}), timeout=60)

@patch('time.sleep')
@patch('dshelpers.requests.get')
def test_override_timeout(mock_requests_get, mock_time_sleep):
    fake_response = requests.Response()
    fake_response.status_code = 200
    fake_response._content = str("Hello")
    mock_requests_get.return_value = fake_response
    _download_with_backoff('http://fake_url.com', timeout=10)
    mock_requests_get.assert_called_with(u'http://fake_url.com', headers=CaseInsensitiveDict({u'user-agent': u'ScraperWiki Limited (bot@scraperwiki.com)'}), timeout=10)

@patch('time.sleep')
@patch('dshelpers.requests.get')
def test_get_response_object_on_good_site(mock_requests_get, mock_sleep):
    fake_response = requests.Response()
    fake_response.status_code = 200
    fake_response._content = str("Hello")
    mock_requests_get.return_value = fake_response
    assert_equal("Hello", request_url('http://fake_url.com').content)

@patch('time.sleep')
@patch('dshelpers.requests.get')
def test_backoff_function_works_on_a_good_site(mock_requests_get, mock_sleep):
    fake_response = requests.Response()
    fake_response.status_code = 200
    fake_response._content = str("Hello")
    mock_requests_get.return_value = fake_response
    assert_equal("Hello", _download_with_backoff('http://fake_url.com').read())


@patch('time.sleep')
@patch('dshelpers.requests.get')
def test_backoff_function_works_after_one_failure(
        mock_requests_get, mock_sleep):

    def response_generator():
        bad_response = requests.Response()
        bad_response.status_code = 500

        good_response = requests.Response()
        good_response.status_code = 200
        good_response._content = str("Hello")

        yield bad_response
        yield bad_response
        yield good_response

    mock_requests_get.side_effect = response_generator()

    with rate_limit_disabled():
        assert_equal(
            "Hello",
            _download_with_backoff('http://fake_url.com').read())

    assert_equal(
        [call(10), call(20)],
        mock_sleep.call_args_list)
    expected_call = call('http://fake_url.com', timeout=_TIMEOUT,
                         headers=CaseInsensitiveDict({'user-agent': _USER_AGENT}))
    assert_equal(
        [expected_call,
         expected_call,
         expected_call],
        mock_requests_get.call_args_list)


@patch('time.sleep')
@patch('dshelpers.requests.get')
def test_backoff_raises_on_five_failures(mock_requests_get, mock_sleep):
    fake_response = requests.Response()
    fake_response.status_code = 500

    mock_requests_get.return_value = fake_response

    with rate_limit_disabled():
        assert_raises(RuntimeError, lambda:
                      _download_with_backoff('http://fake_url.com'))

    assert_equal(
        [call(10), call(20), call(40), call(80), call(160)],
        mock_sleep.call_args_list)


@patch('dshelpers.requests.get')
def test_download_url_sets_user_agent(mock_requests_get):
    fake_response = requests.Response()
    fake_response.status_code = 200
    fake_response._content = str("Hello")
    mock_requests_get.return_value = fake_response

    _download_without_backoff('http://invalid')

    expected_user_agent = 'ScraperWiki Limited (bot@scraperwiki.com)'
    expected_call = call(
        u'http://invalid',
        timeout=60,
        headers=CaseInsensitiveDict({'user-agent': expected_user_agent})
    )

    assert_equal(
        [expected_call],
        mock_requests_get.call_args_list)
