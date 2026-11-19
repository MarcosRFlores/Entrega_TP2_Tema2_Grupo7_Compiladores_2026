"""Parser de clausulas: BNF ejecutable, tabla M, pila y recuperacion local."""
from pathlib import Path
from analizador.gramatica import leer_bnf
from analizador.predictivo import Predictivo
from analizador_semantico import evaluar
ROOT = Path(__file__).resolve().parent

REGLAS_CLAUSULA = leer_bnf((ROOT / "gramaticas/clausulas.bnf").read_text(encoding="utf-8"))
PARSER_CLAUSULA = Predictivo(REGLAS_CLAUSULA)
PARSER_TEXTO = Predictivo(leer_bnf((ROOT / "gramaticas/texto.bnf").read_text(encoding="utf-8")))


class ParserClausula:
    """Adaptador de tabla M+pila a atributos de dominio, sin retroceso."""
    def __init__(self, tokens):
        self.ts = tokens
        self.detalle = None
        self.error_semantico = None

    def parsear(self):
        self.detalle = PARSER_CLAUSULA.parsear(
            [(t.categoria, t) for t in self.ts], recuperar=True)
        if not self.detalle["aceptada"]:
            return None
        atributos, self.error_semantico = evaluar(self.detalle["arbol"])
        if atributos is None:
            return None
        return dict(**atributos, arbol=self.detalle["arbol"],
                    derivacion=self.detalle["pasos"])


def clausulas(tokens):
    actual = []
    enlace = "INICIO"
    for t in tokens:
        if t.categoria == "PERO" or (t.categoria == "PUNT" and t.original in "."):
            if actual:
                yield enlace, actual
                actual = []
            enlace = "PERO" if t.categoria == "PERO" else "SECUENCIA"
        elif t.categoria != "PUNT" or t.original != ",":
            actual.append(t)
    if actual:
        yield enlace, actual

