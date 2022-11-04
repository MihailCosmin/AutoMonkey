#!/usr/bin/env python

from automonkey import chain

chain(
    dict(write="this string", wait=0.5),
)
