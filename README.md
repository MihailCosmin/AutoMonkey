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

    There are 2 main ways to click, either by giving the coordinates of the position where to click or by giving the filename of the image you want to click on

    1.1. Clicking by coordinates
        
        1.1.1. In order to find the coordinates of a position on the screen you can use the "track_mouse" function or the PositionTracker class

    ```python
        from automonkey import track_mouse
        track_mouse()
    ```

    <img alt="track_mouse" src="demo/track_mouse.gif" width="416px" height="304px"/>


    ```python
        from automonkey import PositionTracker
        PositionTracker()
    ```

        <img alt="PositionTracker" src="demo/PositionTracker.gif" width="918px" height="574px"/>

        1.2.1. Now that you have the coordinates of the position you want to click on, you can use the "chain" function to click on it


        ```python
            from automonkey import chain
            chain(  
                dict(click=(780, 1175), wait=1),  
                dict(click=(444, 194), wait=1),  
                dict(click=(1892, 110), wait=1),  
                debug=True  
            )
        ```

        <img alt="click" src="demo/click.gif" width="960px" height="576px"/>

    1.2. Clicking by image

        1.2.1. To click on an image you first need to make a screenshot of the area you want to click on and save it somewhere on your computer.
            For this you can use any screenshot tool you want, or you could use monkeyshot: https://github.com/MihailCosmin/monkeyshot
            For example you can make a screenshot of the Edge icon from your toolbar, then we can click on it by using the "chain" function.
            <img alt="edge_toolbar" src="demo/edge_toolbar.gif" width="33px" height="33px"/>

        1.2.2. Now that we have the image we want to click on, we can use the "chain" function to click on it

        ```python
            chain(
                dict(click="demo/edge_toolbar.jpg"),
                dict(click="demo/google_create_account", wait=1),
                dict(click="demo/personal_use", wait=1),
                debug=True
            )
        ```

        <img alt="click_image" src="demo/click_image.gif" width="918px" height="600px"/>