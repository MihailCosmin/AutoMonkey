IMG_EXT = (
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
    ".gif",
    ".pdf",
    ".webp",
    ".PNG",
    ".JPG",
    ".JPEG",
    ".TIFF",
    ".TIF",
    ".BMP",
    ".GIF",
    ".PDF",
    ".WEBP"
)

MOUSE_ACTIONS = (
    "click",
    "leftclick",
    "rightclick",
    "doubleclick",
    "tripleclick",
    "scrollup",
    "scrolldown",
    "scrollleft",
    "scrollright",
    "moveup",
    "movedown",
    "moveleft",
    "moveright"
)

WAIT_ACTIONS = (
    "waitwhile",
    "waituntil",
)

KEYBOARD_ACTIONS = (
    "write",
    "pastetext",
    "keys",
    "keys2",
    "keys3",
    "keys4",
    "copy",
    "paste",
)

APPS_ACTIONS = (
    "close",
    "focus",
    "open_app",
    "startfile",
    "minimize",
    "maximize",
    "restore",
    "copy_from",
    "copy_from_to",
    "msoffice_replace",
)

IMG_ACTIONS = (
    "count_img",
    "get_text_from_region",
)

# pywinauto based actions. Target: window title, (window, control, ...) tuple or dict of arguments
CONTROL_ACTIONS = (
    "start_app",
    "click_control",
    "double_click_control",
    "right_click_control",
    "type_in_control",
    "set_control_text",
    "get_control_text",
    "select_menu",
    "select_item",
    "check_control",
    "uncheck_control",
    "wait_control",
    "list_controls",
)

COMMON_APPS = {
    "edge": "msedge",
    "msedge": "msedge",
    "microsoft edge": "msedge",
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "notepad": "notepad",
    "notepad++": "notepad++",
    "excel": "excel",
    "microsoft excel": "excel",
    "word": "word",
    "microsoft word": "word",
    "powerpoint": "powerpoint",
    "microsoft powerpoint": "powerpoint",
    "outlook": "outlook",
    "microsoft outlook": "outlook",
    "onenote": "onenote",
    "microsoft onenote": "onenote",
    "vscode": "code",
    "visual studio code": "code",
    "explorer": "explorer",
    "windows explorer": "explorer",
    "files": "explorer",
    "file explorer": "explorer",
    "cmd": "cmd",
    "command prompt": "cmd",
    "terminal": "cmd",
    "powershell": "powershell",
    "power shell": "powershell",
}