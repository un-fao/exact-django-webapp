import re


def get_url_name(model_name):
    # Improved algorithm to handle sequences of capital letters correctly
    result = []
    current_word = ""

    for i, char in enumerate(model_name):
        if char.isupper():
            # If this is the start of the string, or previous was also uppercase and next is not lowercase,
            # append to current word
            if i == 0 or (model_name[i - 1].isupper() and (i == len(model_name) - 1 or not model_name[i + 1].islower())):
                current_word += char
            else:
                # New word starts
                if current_word:
                    result.append(current_word)
                current_word = char
        else:
            current_word += char

    if current_word:
        result.append(current_word)

    url_name = "-".join(result).lower()

    if url_name[-1] == "s":
        url_name += "es"
    else:
        url_name += "s"
    return url_name
