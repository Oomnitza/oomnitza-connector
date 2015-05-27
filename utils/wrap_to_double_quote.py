def wrap_to_double_quote(src):
    db_quote_str = ''
    if src:
        if type(src) is list:
            db_quote_str = '['
            for item in src:
                db_quote_str += '"%s", ' %(str(item))
            db_quote_str = db_quote_str[:-2] + ']'
        elif type(src) is dict:
            db_quote_str = '{'
            for item in src.items():
                db_quote_str += '"%s":"%s", ' %(str(item[0]), str(item[1]))
            db_quote_str = db_quote_str[:-2] + '}'
    else:
        if type(src) is list:
            db_quote_str = '[]'
        elif type(src) is dict:
            db_quote_str = '{}'
    return db_quote_str