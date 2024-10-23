def is_integer(text):
    try:
        int(text)
        return True
    except ValueError:
        return False


def is_float(text):
    try:
        float(text)
        return True
    except ValueError:
        return False
