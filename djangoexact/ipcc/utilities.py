import re


def get_url_name(model_name):
    url_name = model_name

    # regex split on capital letters
    url_name = re.split(r"(?<!^)(?=[A-Z](?![A-Z]|$))", url_name)

    # If an entry of the array contains two capital letters in a row, split only on the first one of the sequence
    for i in range(len(url_name)):
        if len(url_name[i]) > 1:
            # cycle through the string and find a sequence of two capital letters
            for j in range(len(url_name[i])):
                if url_name[i][j].isupper() and url_name[i][j + 1].isupper():
                    # split on the first capital letter of the sequence
                    url_name[i] = url_name[i][:j] + "-" + url_name[i][j:]
                    break

    url_name = "".join([f"-{x}" for x in url_name]).lower()
    url_name = url_name[1:]

    if url_name[-1] == "s":
        url_name += "es"
    else:
        url_name += "s"
    return url_name
