"""
Implementa o transformador da árvore sintática que converte entre as representações

    lark.Tree -> lox.ast.Node.

A resolução de vários exercícios requer a modificação ou implementação de vários
métodos desta classe.
"""

from typing import Callable
from lark import Transformer, v_args

from . import runtime as op
from .ast import *


def op_handler(op: Callable):
    """
    Fábrica de métodos que lidam com operações binárias na árvore sintática.

    Recebe a função que implementa a operação em tempo de execução.
    """

    def method(self, left, right):
        return BinOp(left, right, op)

    return method


@v_args(inline=True)
class LoxTransformer(Transformer):
    # Programa
    def program(self, *stmts):
        return Program(list(stmts))

    # Operações matemáticas básicas
    mul = op_handler(op.mul)
    div = op_handler(op.truediv)
    sub = op_handler(op.sub)
    add = op_handler(op.add)

    # Comparações
    gt = op_handler(op.gt)
    lt = op_handler(op.lt)
    ge = op_handler(op.ge)
    le = op_handler(op.le)
    eq = op_handler(op.eq)
    ne = op_handler(op.ne)

    def call(self, callee: Expr, params: list):
        return Call(callee, params)
        
    def params(self, *args):
        params = list(args)
        return params

    # Comandos
    def print_cmd(self, expr):
        return Print(expr)

    def VAR(self, token):
        name = str(token)
        return Var(name)

    def NUMBER(self, token):
        num = float(token)
        return Literal(num)
    
    def STRING(self, token):
        text = str(token)[1:-1]
        return Literal(text)
    
    def NIL(self, _):
        return Literal(None)

    def BOOL(self, token):
        return Literal(token == "true")

    def getattr(self, obj, name):
        return Getattr(obj, name.name)

    def not_(self, expr):
        return UnaryOp('!', expr)

    def neg(self, expr):
        return UnaryOp('-', expr)

    def and_(self, left, right):
        return And(left, right)
    
    def or_(self, left, right):
        return Or(left, right)

    def assign(self, name: Var, value: Expr):
        return Assign(name.name, value)
        
    def setattr_assign(self, target, value):
        return Setattr(target.obj, target.name, value)
    
    def var_decl(self, name, value=None):
        if value is None:
            value = Literal(None)
        return VarDef(name.name, value)
    
    def block(self, *declarations):
        return Block(list(declarations))
    
    def if_cmd(self, condition: Expr, then_branch: Stmt, else_branch: Stmt = None):
        if else_branch is None:
            else_branch = Block([])
        return If(condition, then_branch, else_branch)
    
    def while_cmd(self, condition: Expr, body: Stmt):
        return While(condition, body)
    
    def for_init(self, init_part=None):
        if init_part is None or (isinstance(init_part, str) and init_part == ';'):
            return Block([])
        
        if isinstance(init_part, VarDef):
            return init_part
        
        if isinstance(init_part, Expr):
            return Block([init_part])
        
        return init_part


    def for_cond(self, condition=None):
        if condition is None:
            return Literal(True)
        return condition


    def for_incr(self, increment_part=None):
        if increment_part is None:
            return Block([])
        
        if isinstance(increment_part, Expr):
            return Block([increment_part])
        
        return increment_part


    def for_cmd(self, init: Stmt, condition: Expr, increment: Stmt, body: Stmt):
        inner_while_body_stmts = [body]
        inner_while_body_stmts.append(increment)
        inner_while_body = Block(inner_while_body_stmts)

        while_loop = While(condition, inner_while_body)

        outer_block_stmts = []
        outer_block_stmts.append(init)
        outer_block_stmts.append(while_loop)

        return Block(outer_block_stmts)
