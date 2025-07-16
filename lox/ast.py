from abc import ABC
from dataclasses import dataclass, field
from typing import Callable
from .runtime import LoxFunction, LoxReturn, LoxClass, LoxInstance, LoxError, print as lox_print

from .ctx import Ctx

# Importações para a validação semântica
from .node import Node, Cursor
from .errors import SemanticError

# Palavras reservadas da linguagem Lox
RESERVED_WORDS = {
    "and", "class", "else", "false", "for", "fun", "if", "nil",
    "or", "print", "return", "this", "true", "var", "while"
}

# TIPOS BÁSICOS

Value = bool | str | float | None


class Expr(Node, ABC):
    """Classe base para expressões."""

class Stmt(Node, ABC):
    """Classe base para comandos."""

@dataclass
class Program(Node):
    """Representa um programa."""
    stmts: list[Stmt]

    def eval(self, ctx: Ctx):
        for stmt in self.stmts:
            stmt.eval(ctx)

# EXPRESSÕES

@dataclass
class BinOp(Expr):
    """Uma operação infixa com dois operandos."""
    left: Expr
    right: Expr
    op: Callable[[Value, Value], Value]

    def eval(self, ctx: Ctx):
        left_value = self.left.eval(ctx)
        right_value = self.right.eval(ctx)
        return self.op(left_value, right_value)

@dataclass
class Var(Expr):
    """Uma variável no código."""
    name: str

    def eval(self, ctx: Ctx):
        try:
            return ctx[self.name]
        except KeyError:
            raise NameError(f"variável {self.name} não existe!")

    def validate_self(self, cursor: Cursor):
        """Verifica se o nome da variável não é uma palavra reservada."""
        if self.name in RESERVED_WORDS:
            raise SemanticError(
                f"Não é possível usar a palavra reservada '{self.name}' como nome de variável.",
                token=self.name
            )

@dataclass
class Literal(Expr):
    """Representa valores literais no código."""
    value: Value

    def eval(self, ctx: Ctx):
        return self.value

@dataclass
class ExprStmt(Stmt):
    expr: Expr
    def eval(self, ctx: Ctx):
        self.expr.eval(ctx)

@dataclass
class And(Expr):
    """Uma operação 'and'."""
    left: Expr
    right: Expr
    def eval(self, ctx: Ctx):
        left_val = self.left.eval(ctx)
        if left_val is False or left_val is None:
            return left_val
        return self.right.eval(ctx)

@dataclass
class Or(Expr):
    """Uma operação 'or'."""
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
    """Uma operação prefixa com um operando."""
    operand: Expr
    op: Callable[[Value], Value]

    def eval(self, ctx: Ctx):
        value = self.operand.eval(ctx)
        return self.op(value)

@dataclass
class Call(Expr):
    """Uma chamada de função."""
    callee: Expr
    params: list[Expr]
    
    def eval(self, ctx: Ctx):
        func = self.callee.eval(ctx)
        args = [param.eval(ctx) for param in self.params if param is not None]
        if callable(func):
            return func(*args)
        raise TypeError(f"'{func}' não é uma função!")

@dataclass
class This(Expr):
    """Acesso ao `this`."""
    # Campo vazio para evitar problemas com dataclasses sem campos
    _dummy: str = field(default="", init=False, repr=False)
    
    def eval(self, ctx: Ctx):
        try:
            return ctx["this"]
        except KeyError:
            raise NameError("variável this não existe!")

    def validate_self(self, cursor: Cursor):
        """Verifica se this está dentro de uma classe."""
        # Itera pelos pais para encontrar uma Class
        for parent_cursor in cursor.parents():
            if isinstance(parent_cursor.node, Class):
                return
        # Se chegou aqui, não encontrou Class nos pais
        raise SemanticError(
            "Não é possível usar 'this' fora de uma classe.",
            token="this"
        )

@dataclass
class Super(Expr):
    """Acesso a método ou atributo da superclasse."""
    method: str
    
    def eval(self, ctx: Ctx):
        method_name = self.method
        super_class = ctx["super"]
        this = ctx["this"]
        method = super_class.get_method(method_name)
        return method.bind(this)

    def validate_self(self, cursor: Cursor):
        """Verifica se super está dentro de uma classe que herda de outra."""
        # Itera pelos pais para encontrar uma Class com superclasse
        for parent_cursor in cursor.parents():
            if isinstance(parent_cursor.node, Class):
                if parent_cursor.node.superclass is not None:
                    return
                else:
                    # Encontrou uma classe, mas sem superclasse
                    raise SemanticError(
                        "Não é possível usar 'super' em uma classe sem superclasse.",
                        token="super"
                    )
        # Se chegou aqui, não encontrou Class nos pais
        raise SemanticError(
            "Não é possível usar 'super' fora de uma classe.",
            token="super"
        )

@dataclass
class Assign(Expr):
    """Atribuição de variável."""
    name: str
    value: Expr

    def eval(self, ctx: Ctx):
        result = self.value.eval(ctx)
        ctx.assign(self.name, result)
        return result

@dataclass
class Getattr(Expr):
    """Acesso a atributo de um objeto."""
    obj: Expr
    name: str

    def eval(self, ctx: Ctx):
        obj_value = self.obj.eval(ctx)
        
        # Use getattr normal para todos os objetos (incluindo LoxInstance)
        # A lógica específica para LoxInstance está no __getattr__ da classe
        try:
            return getattr(obj_value, self.name)
        except AttributeError:
            raise AttributeError(f"O objeto {obj_value} não possui o atributo '{self.name}'")

@dataclass
class Setattr(Expr):
    """Atribuição de atributo de um objeto."""
    obj: Expr
    name: str
    value: Expr

    def eval(self, ctx: Ctx):
        obj_val = self.obj.eval(ctx)
        val = self.value.eval(ctx)
        
        # Verificar se estamos tentando definir um campo numa classe ou função
        if isinstance(obj_val, (LoxClass, LoxFunction)):
            raise LoxError("Apenas instâncias podem ter campos.")
        
        setattr(obj_val, self.name, val)
        return val

# COMANDOS

@dataclass
class Print(Stmt):
    """Representa uma instrução de impressão."""
    expr: Expr

    def eval(self, ctx: Ctx):
        value = self.expr.eval(ctx)
        lox_print(value)

@dataclass
class Return(Stmt):
    """Representa uma instrução de retorno."""
    value: Expr | None

    def eval(self, ctx: Ctx):
        return_value = self.value.eval(ctx) if self.value else None
        raise LoxReturn(return_value)

    def validate_self(self, cursor: Cursor):
        """Verifica se return está dentro de uma função."""
        # Itera pelos pais para encontrar uma Function ou Method
        for parent_cursor in cursor.parents():
            if isinstance(parent_cursor.node, (Function, Method)):
                # Check if it's a return with value inside an init method
                if isinstance(parent_cursor.node, Method) and parent_cursor.node.name == "init" and self.value is not None:
                    raise SemanticError(
                        "Can't return a value from an initializer.",
                        token="return"
                    )
                return
        # Se chegou aqui, não encontrou Function nem Method nos pais
        raise SemanticError(
            "Não é possível usar 'return' no nível superior do código.",
            token="return"
        )

@dataclass
class VarDef(Stmt):
    """Representa uma declaração de variável."""
    name: str
    initializer: Expr

    def eval(self, ctx: Ctx):
        value = self.initializer.eval(ctx)
        ctx.var_def(self.name, value)

    # Validação Semântica para VarDef
    def validate_self(self, cursor: Cursor):
        """Verifica se o nome da variável não é uma palavra reservada e se não usa variável local em sua própria inicialização."""
        if self.name in RESERVED_WORDS:
            raise SemanticError(
                f"Não é possível usar a palavra reservada '{self.name}' como nome de variável.",
                token=self.name
            )
        
        # Check if the initializer uses the variable being declared
        # Only check this if we're in a block (local scope)
        parent = cursor.parent_cursor
        if parent and isinstance(parent.node, Block):
            def check_self_reference(node):
                if isinstance(node, Var) and node.name == self.name:
                    raise SemanticError(
                        "Can't read local variable in its own initializer.",
                        token=self.name
                    )
            
            # Visit the initializer to check for self-references
            if self.initializer:
                self.initializer.visit({Var: check_self_reference})

@dataclass
class If(Stmt):
    """Representa uma instrução condicional."""
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt

    def eval(self, ctx: Ctx):
        condition_val = self.condition.eval(ctx)
        if condition_val is not False and condition_val is not None:
            self.then_branch.eval(ctx)
        else:
            self.else_branch.eval(ctx)

@dataclass
class While(Stmt):
    """Representa um laço de repetição."""
    condition: Expr
    body: Stmt

    def eval(self, ctx: Ctx):
        while True:
            condition_val = self.condition.eval(ctx)
            if condition_val is False or condition_val is None:
                break
            self.body.eval(ctx)

@dataclass
class Block(Node):
    """Representa um bloco de comandos."""
    stmts: list[Stmt]

    def eval(self, ctx: Ctx):
        new_ctx = ctx.push({})
        for stmt in self.stmts:
            stmt.eval(new_ctx)

    # Validação Semântica para Block
    def validate_self(self, cursor: Cursor):
        """Verifica se não há duas variáveis com o mesmo nome no mesmo bloco."""
        seen = set()
        for stmt in self.stmts:
            if isinstance(stmt, VarDef):
                if stmt.name in seen:
                    raise SemanticError(
                        f"Variável '{stmt.name}' já foi declarada neste bloco.",
                        token=stmt.name
                    )
                seen.add(stmt.name)

@dataclass
class Function(Stmt):
    """Representa uma declaração de função."""
    name: str
    params: list[Var]
    body: Block

    def eval(self, ctx: Ctx):
        param_names = [p.name for p in self.params if p is not None]
        function = LoxFunction(self.name, param_names, self.body, ctx)
        ctx.var_def(self.name, function)
        return None

    def validate_self(self, cursor: Cursor):
        """
        Valida a declaração da função para:
        0. Nomes de parâmetros que são palavras reservadas. (NOVA VERIFICAÇÃO)
        1. Parâmetros com nomes duplicados.
        2. Variáveis no corpo que sombreiam parâmetros.
        """
        for param in self.params:
            if param is not None and param.name in RESERVED_WORDS:
                raise SemanticError(
                    f"Não é possível usar a palavra reservada '{param.name}' como nome de parâmetro.",
                    token=param.name
                )
        
        param_names = set()
        for param in self.params:
            if param is not None:
                if param.name in param_names:
                    raise SemanticError(
                        f"Nome de parâmetro duplicado '{param.name}' na declaração de função.",
                        token=param.name
                    )
                param_names.add(param.name)

        for stmt in self.body.stmts:
            if isinstance(stmt, VarDef):
                if stmt.name in param_names:
                    raise SemanticError(
                        f"Variável '{stmt.name}' oculta um parâmetro da função.",
                        token=stmt.name
                    )

@dataclass
class Method(Node):
    """Representa um método de classe."""
    name: str
    params: list[Var]
    body: Block

    def eval(self, ctx: Ctx):
        pass

@dataclass
class Class(Stmt):
    """Representa uma declaração de classe."""
    name: str
    methods: list[Method]
    superclass: str | None = None

    def eval(self, ctx: Ctx):
        # Carrega a superclasse, caso exista
        superclass = None
        if self.superclass:
            superclass_value = ctx[self.superclass]
            if not isinstance(superclass_value, LoxClass):
                raise RuntimeError(f"Superclass must be a class.")
            superclass = superclass_value

        # Criamos um escopo para os métodos possivelmente diferente do escopo 
        # onde a classe está declarada
        if superclass is None:
            method_ctx = ctx
        else:
            method_ctx = ctx.push({"super": superclass})

        # Avaliamos cada método
        methods = {}
        for method in self.methods:
            method_name = method.name
            method_body = method.body
            method_args = [param.name for param in method.params if param is not None]
            method_impl = LoxFunction(method_name, method_args, method_body, method_ctx)
            methods[method_name] = method_impl

        lox_class = LoxClass(self.name, methods, superclass)
        ctx.var_def(self.name, lox_class)
        return None

    def validate_self(self, cursor: Cursor):
        """Verifica se a classe não herda de si mesma."""
        if self.superclass is not None and self.superclass == self.name:
            raise SemanticError(
                "A class can't inherit from itself.",
                token=self.superclass
            )