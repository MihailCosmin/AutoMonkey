# AutoMonkey
<img alt="AutoMonkey" src="img/monkey.ico" width="100px" height="100px"/>

Python Automation using Mouse and Keyboard, for the masses

# Installation
pip install git+https://github.com/MihailCosmin/AutoMonkey

# Usage
Main function to be used is "chain"  

This will allow you to "chain" together most of the other functions of automonkey.  
Which in turn will enable you to create sequences of mouse and/or keyboard actions in order to automate any given task.  
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