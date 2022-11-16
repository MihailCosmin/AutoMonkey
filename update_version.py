from re import search
from re import sub

VER_FILES = [
    "setup.py",
    "setup.cfg",
    "pyproject.toml",
    "__init__.py",
    "automonkey/__init__.py",
]

VER_REGEX = r"([ \"']{1})(\d.\d.\d)([ \"'\n]{1})"

def extract_number(ver: str) -> int:
    """Extract all numbers from a  string."""
    return int(sub(r'\D', '', ver))

def increase_version(ver: int) -> int:
    return ver + 1

def int_to_version(ver: int) -> str:
    return f'0.0.{ver}' if ver < 10 else f'0.{ver//10}.{ver%10}' if ver < 100 else f'{ver//100}.{ver//10}.{ver%10}'

def bump_version():
    for ver_file in VER_FILES:
        with open(ver_file, 'r', encoding="utf-8") as f:
            data = f.read()
        ver = search(VER_REGEX, data)
        if ver:
            start = ver.group(1)
            end = ver.group(3)
            ver = ver.group(2)
            ver = extract_number(ver)
            ver = increase_version(ver)
            ver = int_to_version(ver)
            data = sub(VER_REGEX, start + ver + end, data)
            with open(ver_file, 'w') as f:
                f.write(data)

if __name__ == '__main__':
    bump_version()
