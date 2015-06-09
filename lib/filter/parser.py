__author__ = 'daniel'

import logging
import token as ttype
from token import tok_name

import operator
import inspect

LOG = logging.getLogger("lib/filter/parser")

from .tokenizer import tokenize
from .tree import Bool, And, Or, Set, If, FunctionCall, Literal, Field, RegEx

LanguageSpec = """
    ROOT ::= statement
    statement ::= and_stmt | or_stmt | if_stmt | [ bool_stmt | set_stmt ] ';'
    and_stmt ::= 'AND' '{' ( statement )* '}'
    or_stmt ::= 'OR' '{' ( statement )* '}'
    set_stmt ::= 'set' field '=' expression ';'
    if_stmt ::= 'if' '(' bool_stmt ')' '{' ( statement )* '}' ( 'else' '{' ( statement )* '}' )+
    bool_stmt ::= expression operator expression
    operator ::= < | > | <= | >= | == | != | *=

    expression ::= function_call | literal | field
    field ::= NAME ( '.' [ NAME | NUMBER ] )*
    function_call ::= NAME '(' params ')'
    params ::= None | ( expression ( ',' expression )* )+ ( NAME '=' expression ( ',' NAME '=' expression )* )+
"""

# Operators defines the mappings between the filter binary operator
# and the python code which does the work.
# the operator is used heavily. (man, python makes this easy)
# Values can be either:
#  - a callable taking 2 params (lvalue, rvalue)
#  - a Class taking 2 constructor params (lexpr, rexpr)
Operators = {
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
    "*=": RegEx,
}


class TokenSyntaxError(SyntaxError):
    def __init__(self, token, msg, *args):
        super(TokenSyntaxError, self).__init__(
            msg % args,
            # lineno=token[2][0], offset=token[2][1],
            # text=token[4]
        )
        self._token = token

    @property
    def token(self):
        return self._token


class FilterParser(object):
    def __init__(self):
        self.__init("")
        self._enable_if = True
        self._enable_set = True

    def __init(self, filter_str):
        self._filter_str = filter_str
        self._tokens = list(tokenize(filter_str))

    def _consume_token(self, ttype, tstr=None):
        """
        I pull the top token off and return it, matching the token type.
        I will optionally match the token string as well.
        :param ttype: the token type (int) to match
        :param tstr: (optional) string to match against token string
        :return: the top token if match, raises TokenSyntaxError
        """
        LOG.debug("consume_token: %r", self._tokens[0])
        if self._tokens[0][0] != ttype:
            raise TokenSyntaxError(
                self._tokens[0],
                "Expected %r, got %r", tok_name[ttype], self._tokens[0]
            )
        if tstr and self._tokens[0][1] != tstr:
            raise TokenSyntaxError(
                self._tokens[0],
                "Expected %r, got %r", (tok_name[ttype], tstr), self._tokens[0]
            )
        return self._tokens.pop(0)

    def _consume_statement(self):
        """
        statement ::= and_stmt | or_stmt | bool_stmt ';'
        """
        if self._tokens[0][1] == "AND":
            return self._consume_and_stmt()
        if self._tokens[0][1] == "OR":
            return self._consume_or_stmt()
        if self._tokens[0][1] == "set":
            return self._consume_set_stmt()
        if self._tokens[0][1] == "if":
            return self._consume_if_stmt()

        bool_stmt = self._consume_bool_stmt()
        self._consume_token(ttype.SEMI)
        return bool_stmt

    def _consume_and_stmt(self):
        """
        and_stmt ::= 'AND' '{' ( statement )* '}'
        """
        children = []
        self._consume_token(ttype.NAME, "AND")
        self._consume_token(ttype.LBRACE)

        while self._tokens[0][0] != ttype.RBRACE:
            children.append(self._consume_statement())

        self._consume_token(ttype.RBRACE)
        return And(children)

    def _consume_or_stmt(self):
        """
        and_stmt ::= 'OR' '{' ( statement )* '}'
        """
        children = []
        self._consume_token(ttype.NAME, "OR")
        self._consume_token(ttype.LBRACE)

        while self._tokens[0][0] != ttype.RBRACE:
            children.append(self._consume_statement())

        self._consume_token(ttype.RBRACE)
        return Or(children)

    def _consume_set_stmt(self):
        """
        set_stmt ::= 'set' field '=' expression ';'
        """
        if not self._enable_set:
            raise TokenSyntaxError(self._tokens[0], "Invalid token 'set'.")

        self._consume_token(ttype.NAME, "set")
        field = self._consume_field()
        self._consume_token(ttype.OP, '=')
        expr = self._consume_expression()
        self._consume_token(ttype.SEMI)
        return Set(field, expr)

    def _consume_if_stmt(self):
        """
        if_stmt ::= 'if' '(' bool_stmt ')' '{' ( statement )* '}' ( 'else' '{' ( statement )* '}' )+
        """
        if not self._enable_if:
            raise TokenSyntaxError(self._tokens[0], "Invalid token 'if'.")

        true_children = []
        false_children = []

        self._consume_token(ttype.NAME, "if")
        self._consume_token(ttype.LPAR)
        test = self._consume_bool_stmt()
        self._consume_token(ttype.RPAR)

        self._consume_token(ttype.LBRACE)

        while self._tokens[0][0] != ttype.RBRACE:
            true_children.append(self._consume_statement())

        self._consume_token(ttype.RBRACE)

        if self._tokens[0][0] == ttype.NAME and self._tokens[0][1] == 'else':
            self._consume_token(ttype.NAME, "else")
            self._consume_token(ttype.LBRACE)

            while self._tokens[0][0] != ttype.RBRACE:
                false_children.append(self._consume_statement())

            self._consume_token(ttype.RBRACE)

        return If(test, true_children, false_children)

    def _consume_bool_stmt(self):
        """
        bool_stmt ::= expression operator expression
        """
        lexpr = self._consume_expression()
        oper = self._consume_operator()
        rexpr = self._consume_expression()
        if inspect.isclass(oper):
            return oper(lexpr, rexpr)
        return Bool(lexpr, oper, rexpr)

    def _consume_expression(self):
        """
        expression ::= function_call | literal | field
        """
        if self._tokens[0][0] == ttype.NAME:
            # function_call | field
            if self._tokens[1][0] == ttype.LPAR:
                return self._consume_function_call()
            return self._consume_field()
        elif self._tokens[0][0] == ttype.STRING:
            return Literal(self._consume_token(ttype.STRING)[1][1:-1])
        elif self._tokens[0][0] == ttype.NUMBER:
            return Literal(self._consume_token(ttype.NUMBER)[1])
        raise TokenSyntaxError(
            self._tokens[0],
            "_consume_expression: can't handle input!"
        )

    def _consume_function_call(self):
        """
        function_call ::= NAME '(' params ')'
        """
        name_token = self._consume_token(ttype.NAME)
        self._consume_token(ttype.LPAR)

        params = self._consume_params()

        self._consume_token(ttype.RPAR)
        return FunctionCall(name_token, params)

    def _consume_field(self):
        """
        field ::= NAME ( '.' [ NAME | NUMBER ] )*
        """
        keys = [self._consume_token(ttype.NAME)[1]]
        while True:
            if self._tokens[0][0] == ttype.OP and self._tokens[0][1] == '.':
                self._consume_token(ttype.OP, '.')
                keys.append(self._consume_token(ttype.NAME)[1])
            elif self._tokens[0][0] == ttype.NUMBER and self._tokens[0][1][0] == '.':
                keys.append(self._consume_token(ttype.NUMBER)[1][1:])
            else:
                return Field(keys)

    def _consume_params(self):
        """
        params ::= None | ( expression ( ',' expression )* )+ ( NAME '=' expression ( ',' NAME '=' expression )* )+
        """
        args = []
        kwargs = {}
        in_kwargs = False
        while self._tokens[0][0] != ttype.RPAR:
            if self._tokens[0][0] == ttype.NAME and \
               self._tokens[1][0] == ttype.OP and self._tokens[1][1] == '=':
                in_kwargs = True
            if in_kwargs:
                name_token = self._consume_token(ttype.NAME)
                self._consume_token(ttype.OP, '=')
                kwargs[name_token[1]] = self._consume_expression()
            else:
                args.append(self._consume_expression())

            if self._tokens[0][0] == ttype.COMMA:
                self._consume_token(ttype.COMMA)
            elif self._tokens[0][0] != ttype.RPAR:
                raise TokenSyntaxError(
                    self._tokens[0],
                    "Expected ',', found: %r",
                    self._tokens[0][1],
                )

        return args, kwargs

    def _consume_operator(self):
        """
        operator ::= < | > | <= | >= | == | != | *=
        """
        kind, oper = self._tokens[0][0], self._tokens[0][1]
        op = Operators.get(oper, None)
        if op is None:
            raise TokenSyntaxError(
                self._tokens[0],
                "Unknown operator: %r",
                self._tokens[0][1]
            )
        self._consume_token(kind, oper)
        return op

    def parse_filter(self, filter_str):
        self.__init(filter_str)
        return self._consume_statement()

parser = FilterParser()
parse_filter = parser.parse_filter
