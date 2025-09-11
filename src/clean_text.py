import re

def strip_brackets(text: str):
    return re.sub(r"\[.*?\]", "", text)

def collapse_spaces(text: str):
    return re.sub(r"\s+", " ", text).strip()

def normalize(text: str):
    return collapse_spaces(strip_brackets(text))