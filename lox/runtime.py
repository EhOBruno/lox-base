import builtins
from dataclasses import dataclass
from types import BuiltinFunctionType, FunctionType
from typing import TYPE_CHECKING

from .ctx import Ctx

if TYPE_CHECKING:
    from .ast import Block, Value

class LoxError(Exception):
    """Exceção para erros de execução Lox."""

class LoxReturn(Exception):
    """Exceção usada para implementar o comando 'return' do Lox."""
    def __init__(self, value: "Value"):
        super().__init__()
        self.value = value

@dataclass
class LoxClass:
    """Representa uma classe Lox em tempo de execução."""
    name: str
    methods: dict[str, "LoxFunction"] = None
    base: "LoxClass" = None

    def __post_init__(self):
        if self.methods is None:
            self.methods = {}

    def __call__(self, *args):
        # "Chamar" uma classe em Lox cria uma nova instância dela.
        instance = LoxInstance(klass=self)
        
        # Se a classe tem um método init, executa automaticamente
        try:
            init_method = self.get_method("init")
            bound_init = init_method.bind(instance)
            bound_init(*args)
        except LoxError:
            # Se não tem método init, mas foram passados argumentos, é um erro
            if args:
                raise TypeError(f"Expected 0 arguments but got {len(args)}.")
        
        return instance

    def get_method(self, name: str) -> "LoxFunction":
        """
        Procura o método na classe atual.
        Se não encontrar, procura nas bases.
        Se não existir em nenhum dos dois lugares, levanta uma exceção LoxError.
        """
        # Procure o método na classe atual
        if name in self.methods:
            return self.methods[name]
        
        # Se não encontrar, procure nas bases
        if self.base is not None:
            return self.base.get_method(name)
        
        # Se não existir em nenhum dos dois lugares, levante uma exceção
        raise LoxError(f"Undefined property '{name}'.")

    def __str__(self) -> str:
        return self.name

@dataclass
class LoxInstance:
    """Representa uma instância de uma classe Lox."""
    klass: LoxClass

    def __getattr__(self, name: str):
        """
        Busca um método na classe da instância (incluindo superclasses).
        """
        try:
            method = self.klass.get_method(name)
            # Importante: associamos o método à instância antes de retorná-lo
            return method.bind(self)
        except LoxError:
            raise AttributeError(f"'{self.klass.name}' object has no attribute '{name}'")

    def init(self, *args):
        """
        Método especial para lidar com o comportamento único do init.
        Executa o método init da classe e retorna a própria instância.
        """
        try:
            init_method = self.klass.get_method("init")
            bound_init = init_method.bind(self)
            bound_init(*args)
            return self  # Retornamos a instância e não o resultado de init
        except LoxError:
            raise AttributeError(f"'{self.klass.name}' object has no method 'init'")

    def __str__(self) -> str:
        return f"{self.klass.name} instance"

@dataclass
class LoxFunction:
    """Representa uma função Lox em tempo de execução."""
    name: str
    params: list[str]
    body: "Block"
    ctx: Ctx

    def __str__(self) -> str:
        if self.name:
            return f"<fn {self.name}>"
        return "<fn>"

    def call(self, args: list["Value"]):
        if len(args) != len(self.params):
            raise TypeError(f"'{self.name}' esperava {len(self.params)} argumentos, mas recebeu {len(args)}.")
        
        local_env = dict(zip(self.params, args))
        call_ctx = self.ctx.push(local_env)

        try:
            self.body.eval(call_ctx)
        except LoxReturn as ex:
            return ex.value
        
        return None

    def __call__(self, *args):
        return self.call(list(args))

    def bind(self, obj: "Value") -> "LoxFunction":
        """Associa essa função a um this específico."""
        return LoxFunction(
            self.name,
            self.params,
            self.body,
            self.ctx.push({"this": obj})
        )

    def __eq__(self, other):
        """Bound methods have identity equality."""
        # LoxFunction equality is based on identity, not content
        return self is other

    def __hash__(self):
        """Allow LoxFunction to be used in sets and as dict keys."""
        return id(self)

# --- Funções de Semântica do Lox ---

def show(value: "Value") -> str:
    """Converte um valor Lox para sua representação em string."""
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        # Dica: str(42.0) -> "42.0", removesuffix -> "42"
        return str(value).removesuffix('.0')
    if isinstance(value, (BuiltinFunctionType, FunctionType)):
        return "<native fn>"
    # Para LoxFunction, LoxClass, LoxInstance e str, o __str__ já faz o trabalho.
    return str(value)

def print(value: "Value"):
    """Imprime um valor Lox usando a representação correta."""
    builtins.print(show(value))

def truthy(value: "Value") -> bool:
    """
    Avalia o valor de acordo com as regras de veracidade do Lox.
    Apenas 'nil' e 'false' são considerados falsos.
    """
    if value is None or value is False:
        return False
    return True

def not_(value: "Value") -> bool:
    """Operador de negação Lox (!)."""
    return not truthy(value)

def neg(value: "Value") -> float:
    """Operador de negação aritmética Lox (-)."""
    if not isinstance(value, float):
        raise LoxError("Operand must be a number.")
    return -value

def eq(a: "Value", b: "Value") -> bool:
    """Operador de igualdade Lox (==)."""
    # Em Lox, tipos diferentes nunca são iguais.
    if type(a) is not type(b):
        return False
    
    # Handle NaN specially - NaN is never equal to anything, including itself
    if isinstance(a, float) and isinstance(b, float):
        import math
        if math.isnan(a) or math.isnan(b):
            return False
    
    return a == b

def ne(a: "Value", b: "Value") -> bool:
    """Operador de desigualdade Lox (!=)."""
    return not eq(a, b)

def _check_numbers(*operands):
    """Função auxiliar para garantir que todos os operandos são números."""
    for op in operands:
        if not isinstance(op, float):
            raise LoxError("Operands must be numbers.")

def add(a: "Value", b: "Value") -> "Value":
    """Operador de adição Lox (+)."""
    if isinstance(a, float) and isinstance(b, float):
        return a + b
    if isinstance(a, str) and isinstance(b, str):
        return a + b
    raise LoxError("Operands must be two numbers or two strings.")

def sub(a: float, b: float) -> float:
    """Operador de subtração Lox (-)."""
    _check_numbers(a, b)
    return a - b

def mul(a: float, b: float) -> float:
    """Operador de multiplicação Lox (*)."""
    _check_numbers(a, b)
    return a * b

def truediv(a: float, b: float) -> float:
    """Operador de divisão Lox (/)."""
    _check_numbers(a, b)
    if b == 0:
        if a == 0:
            # 0/0 should return NaN
            return float('nan')
        else:
            # Non-zero / 0 should return infinity
            return float('inf') if a > 0 else float('-inf')
    return a / b

def lt(a: float, b: float) -> bool:
    """Operador 'menor que' Lox (<)."""
    _check_numbers(a, b)
    return a < b

def le(a: float, b: float) -> bool:
    """Operador 'menor ou igual' Lox (<=)."""
    _check_numbers(a, b)
    return a <= b       

def gt(a: float, b: float) -> bool:
    """Operador 'maior que' Lox (>)."""
    _check_numbers(a, b)
    return a > b

def ge(a: float, b: float) -> bool:
    """Operador 'maior ou igual' Lox (>=)."""
    _check_numbers(a, b)
    return a >= b

# Lista de nomes a serem exportados para o transformer
__all__ = [
    "add", "sub", "mul", "truediv",
    "eq", "ne", "lt", "le", "gt", "ge",
    "neg", "not_",
    "truthy", "show", "print", "LoxError",
    "LoxClass", "LoxInstance", "LoxFunction", "LoxReturn"
]