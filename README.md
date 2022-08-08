# AutoMonkey
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
        dict(click=(700, 10), wait=1, monitor=2),  
        dict(keys3="ctrl+t", wait=1),  
        dict(write="https://github.com/MihailCosmin/AutoMonkey", wait=2),  
        debug=True  
    )
```



Note: above example counts on having an image of the chrome icon in the same folder as the python script.