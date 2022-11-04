#!/usr/bin/env python

from automonkey import chain

chain(
    dict(click="tests/chrome.jpg", wait=0.5),
)
