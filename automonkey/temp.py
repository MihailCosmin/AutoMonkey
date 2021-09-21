def sequencer(img_list: list, debug=False):
    """[Runs a sequence of clicks and writes]
    Args:
        img_list (list): [A list of operations. Each item of the list is also
        a list with the following template:
        - Variable1 = Image to be found on screen or Text to be written.
        - Variable2 - operation: click, rightClick, doubleClick, write
        - Variable3 - time to sleep after operations
        - Variable4 - confidence for the image detection. 1 = very strict, 0.9 = a bit more relaxed]
        - Variable5 - vertical offset (positive or negative)
        - Variable6 - horizontal offset (positive or negative)
        - Variable7 - Skip if not found: True or False
    """

    current_position = ''
    current_height = ''
    current_width = ''

    for item in img_list:
        skip = False
        if len(item) == 7:
            skip = item[6]
        if debug:
            print(item)
        if item[1] != 'write' and item[0] != 'currentPosition'\
                and str(type(item[0])) != '<class \'pyscreeze.Box\'>'\
                and item[1] != 'keys'\
                and item[1] != 'copy'\
                and item[1] != 'type'\
                and 'wait' not in item[1]\
                and item[1] != 'excelScroll'\
                and ".jpg" in str(item[0]):
            sleeped = 0
            while not is_found(item[0])[0] and not skip:
                sleep(0.1)
                sleeped += 0.1
                if int(sleeped) == 30:  # For production make it 300
                    stop = confirm("Next position was not found for 5 minutes.\
                                    Would you like to continue or stop?",
                                   "Continue?",
                                   ["Continue", "Stop"]
                                   )
                    if stop == "Stop":
                        finish()

        try:
            try:
                if item[1] != 'write' and item[0] != 'currentPosition'\
                        and item[1] != 'keys'\
                        and item[1] != 'copy'\
                        and item[1] != 'type'\
                        and 'wait' not in item[1]:
                    if str(type(item[0])) == '<class \'pyscreeze.Box\'>':
                        variable = item[0]
                    else:
                        variable = locateOnScreen(item[0], confidence=item[3])
                        variable = centrator(variable, item[0])
            except OSError:
                alert(f"{item[0]} could not be located! Make sure that Citrix is on your main screen and TC is maximized.")
                continue
            except IndexError:
                continue
            if item[1] == 'click':
                if item[0] == 'currentPosition':
                    click(variable)
                else:
                    click(variable)
            elif item[1] == 'doubleClick':
                if item[0] == 'currentPosition':
                    doubleClick(current_position)
                else:
                    doubleClick(variable)
            elif item[1] == 'tripleClick':
                if item[0] == 'currentPosition':
                    tripleClick(variable)
                else:
                    tripleClick(variable)
            elif item[1] == 'rightClick':
                if item[0] == 'currentPosition':
                    rightClick(variable)
                else:
                    rightClick(variable)
            elif item[1] == 'write':
                temp_clip = paste()
                sleep(0.5)
                while paste() != str(item[0]):
                    clipboardcopy(str(item[0]))
                    print(f"paste1111: {paste()}")
                sleep(1)
                keys('ctrl+v')
                sleep(1)
                clipboardcopy(temp_clip)
                #write(str(item[0]))
            elif item[1] == 'type':
                write(str(item[0]))
            elif item[1] == 'keys':
                keys(item[0])
            elif item[1] == 'copy':
                clipboardcopy(item[0])
            elif item[1] == 'wait':
                # Custom Waits
                if item[0] == 'excelMultipleWorkbooksOpened.jpg':
                    sleep(5)
                    keys('alt+tab')
                    while not (is_found(item[0], 4)[0]):
                        sleep(0.1)
                else:
                    while not is_found(item[0])[0]:
                        sleep(0.1)
            elif item[1] == 'whilewait':
                # whilewait should be used to wait while some image is found.
                # For example, wait, while a loading window is displayed.
                while is_found(item[0])[0]:
                    sleep(0.1)

            elif item[1] == 'waituntil':
                # waituntil should be used to wait until an image comes to view
                # For example, wait, until an excel file opens
                while not is_found(item[0])[0]:
                    sleep(0.1)

            elif item[1] == 'excelCell':
                doubleClick(variable)
                click(variable)
                click(variable)
            elif item[1] == 'excelCopy':
                rightClick(variable)
                sleep(2)
                click(centrator(locateOnScreen("excelCopy.jpg", confidence=0.9)))
            elif item[1] == 'excelScroll':
                if item[0] == "excelScrollLeft.jpg":
                    if not is_found("excelScrollLeftDone.jpg")[0]:
                        for _ in range(0, 10):
                            click(variable)
                if item[0] == "excelScrollTop.jpg":
                    print(is_found(item[0])[0])
                    while not is_found(item[0])[0]:
                        scroll(100000)
            elif item[1] == 'scrollDown':
                while not is_found(item[0])[0]:
                    scroll(-10)
            elif item[1] == 'scrollUp':
                while not is_found(item[0])[0]:
                    scroll(10)
            elif item[1] == 'verticalClick':
                click(vertical_point(variable, item[4]))
            elif item[1] == 'verticalRightClick':
                rightClick(vertical_point(variable, item[4]))
            elif item[1] == 'frontTripleClick':  # Horizontal Click to the Right Side
                if item[0] == 'currentPosition':
                    tripleClick(horizontal_point(current_position, current_width))
                else:
                    tripleClick(horizontal_point(variable, get_width(item[0])))
            elif item[1] == 'frontClick':  # Horizontal Click to the Right Side
                if item[0] == 'currentPosition':
                    click(horizontal_point(current_position, current_width))
                else:
                    click(horizontal_point(variable, get_width(item[0])))
            elif item[1] == 'frontRightClick':  # Horizontal Right Click to the Right Side
                if item[0] == 'currentPosition':
                    rightClick(horizontal_point(current_position, current_width))
                else:
                    rightClick(horizontal_point(variable, get_width(item[0])))
            elif item[1] == 'diagonalClick':
                if item[0] == 'currentPosition':
                    click(diagonal_point(current_position, current_width, current_height))
                else:
                    click(diagonal_point(variable, get_width(item[0]), get_height(item[0])))
            elif item[1] == 'diagonalRightClick':
                if item[0] == 'currentPosition':
                    rightClick(diagonal_point(current_position, current_width, current_height))
                else:
                    rightClick(diagonal_point(variable, get_width(item[0]), get_height(item[0])))
            elif item[1] == 'aboveClick':
                if item[0] == 'currentPosition':
                    click(vertical_point(current_position, current_height))
                else:
                    click(vertical_point(variable, 0 - get_height(item[0])))
            elif item[1] == 'aboveRightClick':
                if item[0] == 'currentPosition':
                    rightClick(vertical_point(current_position, current_height))
                else:
                    rightClick(vertical_point(variable, 0 - get_height(item[0])))
            elif item[1] == 'aboveDoubleClick':
                if item[0] == 'currentPosition':
                    doubleClick(vertical_point(current_position, current_height))
                else:
                    doubleClick(vertical_point(variable, 0 - get_height(item[0])))
            elif item[1] == 'belowClick':
                if item[0] == 'currentPosition':
                    click(vertical_point(current_position, current_height))
                else:
                    click(vertical_point(variable, get_height(item[0])))
            elif item[1] == 'belowRightClick':
                if item[0] == 'currentPosition':
                    rightClick(vertical_point(current_position, current_height))
                else:
                    rightClick(vertical_point(variable, get_height(item[0])))
            elif item[1] == 'belowTripleClick':
                if item[0] == 'currentPosition':
                    tripleClick(vertical_point(current_position, current_height))
                else:
                    tripleClick(vertical_point(variable, get_height(item[0])))

            # most sequences wont't have item[4]
            # If a 4th item is given this can be used
            # as the vertical or horizontal offset.
            if 'vertical' in item[1]:
                current_position = vertical_point(variable, item[4])
                current_height = item[4]
            elif 'above' in item[1]:
                if item[0] != 'currentPosition':
                    current_height = get_height(item[0])
                current_position = vertical_point(variable, 0 - current_height)
            elif 'below' in item[1]:
                if item[0] != 'currentPosition':
                    current_height = get_height(item[0])
                current_position = vertical_point(variable, current_height)
            else:
                if item[1] != 'write' and str(type(item[0])) != '<class \'pyscreeze.Box\'>'\
                        and item[1] != 'keys'\
                        and item[1] != 'copy'\
                        and item[1] != 'type'\
                        and 'wait' not in item[1]:
                    if item[0] != 'currentPosition':
                        current_height = get_height(item[0])
                    current_position = variable
            if item[2] != 0:
                sleep(item[2])
        except Exception as e:
            print(f"Error has occurred processing item: {item}. The error was: \n{e}")


def word_replace(replace_this, with_this):    
    sequencer([
        ['ctrl+h', 'keys', 0.2, 0.9],
        [replace_this, 'copy', 0.2, 0.9],
        ['ctrl+v', 'keys', 0.2, 0.9],
        ['tab', 'keys', 0.2, 0.9],
        [with_this, 'copy', 0.2, 0.9],
        ['ctrl+v', 'keys', 0.2, 0.9],
        ['alt+a', 'keys', 0, 0.9],
        ['wordReplaceDone.jpg', 'waituntil', 0.2, 0.9],
        ['enter', 'keys', 0.2, 0.9],
        ['alt+f4', 'keys', 0.5, 0.9],
    ], debug=True)




def convert_date(date_str):
    """[Converts a date from one format to another]
    Args:
        date_str (str): A date in the format month/day/year
    Returns:
        str: A date converted to the format: dd.mm.yyyy
    """
    month = date_str.split("/")[0] if len(date_str.split("/")[0]) == 2 else "0" + date_str.split("/")[0]
    day = date_str.split("/")[1] if len(date_str.split("/")[1]) == 2 else "0" + date_str.split("/")[1]
    year = date_str.split("/")[2]
    return day + "." + month + "." + year



