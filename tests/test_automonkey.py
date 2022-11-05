#!/usr/bin/env python

from automonkey import chain
# PositionTracker()
# track_mouse()

# to be tested:
MOUSE_ACTIONS = (
    "click",  # Works
    "leftclick",  # Works
    "rightclick",  # Works
    "doubleclick",  # Works - https://www.rapidtables.com/tools/click-counter.html
    "tripleclick",  # Works - https://www.rapidtables.com/tools/click-counter.html
    "scrollup",  # Works
    "scrolldown",  # Works
    "scrollleft",  # Does not work on windows
    "scrollright",  # Does not work on windows
)

WAIT_ACTIONS = (
    "waitwhile",  # Works - https://www.w3schools.com/howto/howto_js_progressbar.asp
    "waituntil",  # Works - https://www.w3schools.com/howto/howto_js_progressbar.asp
)

KEYBOARD_ACTIONS = ( 
    "write",  # Works - Only for English characters
    "pastetext",  # Works
    "keys",  # Works - https://en.key-test.ru/
    "keys2",  # Works - https://en.key-test.ru/
    "keys3",  # Works - https://en.key-test.ru/
    "keys4",  # Works - https://en.key-test.ru/
    "copy",  # Works
    "paste",  # Works
)

APPS_ACTIONS = (
    "startfile",  # Works
    "focus",  # Works
    "minimize",  # Works
    "maximize",  # Works
    "msoffice_replace",  # Works
)

# chain(
#     dict(click="tests/chrome.jpg"),
#     dict(waituntil="tests/chrome_opened", wait=1, monitor=1),
#     dict(leftclick=(1750, 900), wait=1),
#     dict(keys4="ctrl+shift+alt+del", wait=1),
#     debug=True
# )

# chain(
#     dict(click="tests/notepad.jpg"),
#     dict(waituntil="tests/notepad_opened", wait=1, monitor=1),
#     dict(leftclick=(400, 500), wait=1),
#     dict(copy="ctrl+shift+alt+del", wait=1),
#     dict(leftclick=(400, 500), wait=1),
#     dict(paste="", wait=1),
#     debug=True
# )

# chain(
#     dict(startfile=r"D:\Projects\Programming\automonkey\tests\CATIA - Tips and Tricks.docx", wait=2),
#     # dict(msoffice_replace=(r"Tools >", "Replace worked"), wait=2),
#     dict(msoffice_replace=("Replace worked", r"Tools >"), wait=2),
#     dict(keys="alt", wait=0.2),
#     dict(keys="1", wait=0.2),
#     dict(keys="alt+f4", wait=0),
#     debug=True
# )

chain(
    dict(focus_word=r"CATIA - Tips and Tricks.docx", wait=2),
    debug=True
)

chain(
    dict(minimize=r"Visual Studio Code", wait=3),
    dict(maximize=r"Visual Studio Code", wait=1),
    debug=True
)

chain(
    dict(close=r".*?CATIA.*?", wait=3),
    debug=True
)

print(get_text_from_region((136, 121, 53, 19)))  # 189, 140
print(get_text_from_region((136, 121), (189, 140)))  # 189, 140
print(get_text_from_region(136, 121, 189, 140))  # 189, 140
print(get_text_from_region(136, 121, 53, 19))  # 189, 140

chain(
    dict(get_text_from_region=(136, 121, 189, 140), wait=1),
    dict(click="tests/notepad.jpg"),
    dict(waituntil="tests/notepad_opened", wait=1, monitor=1),
    dict(leftclick=(400, 500), wait=1),
    dict(paste="", wait=1),
    debug=True
)