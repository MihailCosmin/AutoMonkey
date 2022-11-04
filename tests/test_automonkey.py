#!/usr/bin/env python

from automonkey import chain

chain(
    dict(click="tests/chrome.jpg", wait=1),
    dict(click=(260, 360), wait=0, monitor=2),
    dict(click=(260, 360), wait=0, monitor=2),
    dict(click=(260, 360), wait=0.5, monitor=2),
    dict(keys="ctrl+t", wait=1, monitor=2),
    dict(click=(260, 360), wait=0, monitor=2),
    dict(click=(260, 360), wait=0, monitor=2),
    dict(click=(260, 360), wait=0, monitor=2),
    dict(click=(260, 360), wait=0.5, monitor=2),
    dict(keys="tab", wait=0.5, monitor=2),
    dict(keys="tab", wait=0.5, monitor=2),
    dict(keys="tab", wait=0.5, monitor=2),
    dict(keys="tab", wait=0.5, monitor=2),
    dict(write="automonkey github", wait=0.5, monitor=2),
    debug=True
)
