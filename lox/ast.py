from abc import ABC
from dataclasses import dataclass
from typing import Callable

from .ctx import Ctx

# Declaramos nossa classe base num módulo separado para esconder um pouco de
# Python relativamente avançado de quem não se interessar pelo assunto.
#
# A classe Node implementa um método `pretty` que imprime as árvores de forma
# legível. Também possui funcionalidades para navegar na árvore usando cursores
# e métodos de visitação.
from .node import Node


#
# TIPOS BÁSICOS
#

# Tipos de valores que podem aparecer durante a execução do programa
Value = bool | str | float | None


class Expr(Node, ABC):
    """
    Classe base para expressões.

    Expressões são nós que podem ser avaliados para produzir um valor.
    Também podem ser atribuídos a variáveis, passados como argumentos para
    funções, etc.
    """


class Stmt(Node, ABC):
    """
    Classe base para comandos.

    Comandos são associdos a construtos sintáticos que alteram o fluxo de
    execução do código ou declaram elementos como classes, funções, etc.
    """


@dataclass
class Program(Node):
    """
    Representa um programa.

    Um programa é uma lista de comandos.
    """

    stmts: list[Stmt]

    def eval(self, ctx: Ctx):
        for stmt in self.stmts:
            stmt.eval(ctx)


#
# EXPRESSÕES
#
@dataclass
class BinOp(Expr):
    """
    Uma operação infixa com dois operandos.

    Ex.: x + y, 2 * x, 3.14 > 3 and 3.14 < 4
    """

    left: Expr
    right: Expr
    op: Callable[[Value, Value], Value]

    def eval(self, ctx: Ctx):
        left_value = self.left.eval(ctx)
        right_value = self.right.eval(ctx)
        return self.op(left_value, right_value)


@dataclass
class Var(Expr):
    """
    Uma variável no código

    Ex.: x, y, z
    """

    name: str

    def eval(self, ctx: Ctx):
        try:
            return ctx[self.name]
        except KeyError:
            raise NameError(f"variável {self.name} não existe!")


@dataclass
class Literal(Expr):
    """
    Representa valores literais no código, ex.: strings, booleanos,
    números, etc.

    Ex.: "Hello, world!", 42, 3.14, true, nil
    """

    value: Value

    def eval(self, ctx: Ctx):
        return self.value


@dataclass
class And(Expr):
    """
    Uma operação infixa com dois operandos.

    Ex.: x and y
    """
    left: Expr
    right: Expr
    
    def eval(self, ctx: Ctx):
        left_val = self.left.eval(ctx)
        if left_val is False or left_val is None:
            return left_val
        return self.right.eval(ctx)


@dataclass
class Or(Expr):
    """
    Uma operação infixa com dois operandos.
    Ex.: x or y
    """
    left: Expr
    right: Expr
    
    def eval(self, ctx: Ctx):
        left_val = self.left.eval(ctx)
        if left_val is not False and left_val is not None:
            if isinstance(left_val, float) and left_val == 0: return left_val
            if isinstance(left_val, str) and left_val == "": return left_val
            return left_val
        return self.right.eval(ctx)


@dataclass
class UnaryOp(Expr):
    """
    Uma operação prefixa com um operando.

    Ex.: -x, !x
    """
    op: str  # '!' ou '-'
    expr: Expr

    def eval(self, ctx: Ctx):
        val = self.expr.eval(ctx)
        if self.op == '!':
            return not val
        elif self.op == '-':
            return -val
        else:
            raise Exception(f"Operador unário desconhecido: {self.op}")


@dataclass
class Call(Expr):
    """
    Uma chamada de função.

    Ex.: fat(42)
    """
    callee: Expr
    params: list[Expr]
    
    def eval(self, ctx: Ctx):
        func = self.callee.eval(ctx)
        args = [param.eval(ctx) for param in self.params]

        if callable(func):
            return func(*args)
        raise TypeError(f"'{func}' não é uma função!")


@dataclass
class This(Expr):
    """
    Acesso ao `this`.

    Ex.: this
    """


@dataclass
class Super(Expr):
    """
    Acesso a method ou atributo da superclasse.

    Ex.: super.x
    """


@dataclass
class Assign(Expr):
    """
    Atribuição de variável.

    Ex.: x = 42
    """
    name: str
    value: Expr

    def eval(self, ctx: Ctx):
        result = self.value.eval(ctx)
        ctx[self.name] = result
        return result


@dataclass
class Getattr(Expr):
    """
    Acesso a atributo de um objeto.

    Ex.: x.y
    """
    obj: Expr
    name: str

    def eval(self, ctx: Ctx):
        obj_value = self.obj.eval(ctx)
        try:
            return getattr(obj_value, self.name)
        except AttributeError:
            raise AttributeError(f"O objeto {obj_value} não possui o atributo '{self.name}'")


@dataclass
class Setattr(Expr):
    """
    Atribuição de atributo de um objeto.

    Ex.: x.y = 42
    """
    obj: Expr
    name: str
    value: Expr

    def eval(self, ctx: Ctx):
        obj_val = self.obj.eval(ctx)
        val = self.value.eval(ctx)
        setattr(obj_val, self.name, val)
        return val


#
# COMANDOS
#
@dataclass
class Print(Stmt):
    """
    Representa uma instrução de impressão.

    Ex.: print "Hello, world!";
    """
    expr: Expr
    
    def eval(self, ctx: Ctx):
        value = self.expr.eval(ctx)
        print(value)


@dataclass
class Return(Stmt):
    """
    Representa uma instrução de retorno.

    Ex.: return x;
    """


@dataclass
class VarDef(Stmt):
    """
    Representa uma declaração de variável.

    Ex.: var x = 42;
    """
    name: str
    value: Expr

    def eval(self, ctx: Ctx):
        initial_value = self.value.eval(ctx)
        ctx.var_def(self.name, initial_value)
        return initial_value


@dataclass
class If(Stmt):
    """
    Representa uma instrução condicional.

    Ex.: if (x > 0) { ... } else { ... }
    """
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt

    def eval(self, ctx: Ctx):
        cond_value = self.condition.eval(ctx)

        is_truthy = bool(cond_value) and cond_value is not None

        if is_truthy:
            self.then_branch.eval(ctx)
        else:
            self.else_branch.eval(ctx)
        
        return None


@dataclass
class For(Stmt):
    """
    Representa um laço de repetição.

    Ex.: for (var i = 0; i < 10; i++) { ... }
    """


@dataclass
class While(Stmt):
    """
    Representa um laço de repetição.

    Ex.: while (x > 0) { ... }
    """


@dataclass
class Block(Node):
    """
    Representa bloco de comandos.

    Ex.: { var x = 42; print x;  }
    """
    declarations: list[Stmt] 

    def eval(self, ctx: Ctx):
        for declaration in self.declarations:
            declaration.eval(ctx)
        return None


@dataclass
class Function(Stmt):
    """
    Representa uma função.

    Ex.: fun f(x, y) { ... }
    """


@dataclass
class Class(Stmt):
    """
    Representa uma classe.

    Ex.: class B < A { ... }
    """