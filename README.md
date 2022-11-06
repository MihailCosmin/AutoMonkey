# AutoMonkey
<img alt="AutoMonkey" src="img/monkey.ico" width="100px" height="100px"/>

Python Automation using Mouse and Keyboard, for the masses

# Installation
pip install git+https://github.com/MihailCosmin/AutoMonkey

# Usage
Main function to be used is "chain"  

This will allow you to "chain" together most of the other functions of automonkey.  
Which in turn will enable you to create sequences of mouse and/or keyboard actions in order to automate any given task.

1. You can connect multiple click (or rightclick) actions together by using the "chain" function. Just by doing this you can generally automate most of the tasks you would do on a daily basis.
    * There are 2 main ways to click, either by giving the coordinates of the position where to click or by giving the filename of the image you want to click on.

    1.1. In order to find the coordinates of a position on the screen you can use the "track_mouse" function or the PositionTracker class.
    ```
        from automonkey import track_mouse
        track_mouse()
    ```
    <img alt="AutoMonkey" src="demo/track_mouse.gif" width="416px" height="304px"/>



Ex:

```
    chain(  
        dict(click="chrome.jpg", wait=1),  
        dict(click=(700, 10), wait=1),  
        dict(keys3="ctrl+t", wait=1),  
        dict(write="https://github.com/MihailCosmin/AutoMonkey", wait=2),  
        debug=True  
    )
```

or

```
    chain(  
        {"click": "chrome.jpg", "wait": 1},  
        {"click": (700, 10), "wait": 1},  
        {"keys3": "ctrl+t", "wait": 1},  
        {"write": "https://github.com/MihailCosmin/AutoMonkey", "wait": 2},  
        debug=True  
    )
```


Note: above example counts on having an image of the chrome icon in the same folder as the python script.