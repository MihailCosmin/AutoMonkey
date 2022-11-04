from automonkey import chain

chain(
    dict(click="tests/chrome.jpg", wait=1),
    dict(click=(260, 360), wait=0),
    dict(click=(260, 360), wait=0),
    dict(click=(260, 360), wait=0.5),
    dict(keys="ctrl+t", wait=1),
    dict(click=(260, 360), wait=0),
    dict(click=(260, 360), wait=0),
    dict(click=(260, 360), wait=0),
    dict(click=(260, 360), wait=0.5),
    dict(keys="tab", wait=0.5),
    dict(keys="tab", wait=0.5),
    dict(keys="tab", wait=0.5),
    dict(keys="tab", wait=0.5),
    dict(write="automonkey github", wait=0.5),
    debug=True
)