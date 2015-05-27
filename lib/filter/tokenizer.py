
import logging
import token as ttype
from token import tok_name
import tokenize as _tokenize
import cStringIO

LOG = logging.getLogger(__name__)


def tokenize(filter_str):
    """
    Wrapper around generate_tokens() from tokenize module.
    Token tuple:
        the token type; (int)
        the token string;
        a 2-tuple (srow, scol) of ints specifying the row and column where the token begins in the source;
        a 2-tuple (erow, ecol) of ints specifying the row and column where the token ends in the source;
        and the line on which the token was found.

    :param filter_str: the filter string to turn into tokens
    :return: list of tokens
    """

    filter_str = "AND { %s }" % filter_str
    src = cStringIO.StringIO(filter_str).readline
    tokens = []
    for token in _tokenize.generate_tokens(src):
        if token[0] in (53, 54):
            continue  # eat comment(53), NL(54)

        # the python token generator treats some tokens as ttype.OP.
        # this method converts a few special cases into the more specific token.
        # this makes consuming the tokens much easier for this simple filter.
        if token[0] == ttype.OP:
            if token[1] == '(':
                token = (ttype.LPAR, token[1], token[2], token[3], token[4])
            elif token[1] == ')':
                token = (ttype.RPAR, token[1], token[2], token[3], token[4])
            elif token[1] == '{':
                token = (ttype.LBRACE, token[1], token[2], token[3], token[4])
            elif token[1] == '}':
                token = (ttype.RBRACE, token[1], token[2], token[3], token[4])
            elif token[1] == ';':
                token = (ttype.SEMI, token[1], token[2], token[3], token[4])
            elif token[1] == ',':
                token = (ttype.COMMA, token[1], token[2], token[3], token[4])

        LOG.debug("%s: %r", tok_name[token[0]], token)
        tokens.append(token)

    return tokens
