"""Léxico de líneas y validación LL(1) del protocolo externo."""
import re
from pathlib import Path
from .gramatica import leer_bnf
from .predictivo import Predictivo

ROOT = Path(__file__).resolve().parent.parent
PARSER_LINEA = Predictivo(leer_bnf((ROOT / "gramaticas/linea.bnf").read_text(encoding="utf-8")))
PARSER_LOTE = Predictivo(leer_bnf((ROOT / "gramaticas/formato.bnf").read_text(encoding="utf-8")))


def tokens_linea(raw, linea):
    def token(cat, texto, inicio=0):
        return cat, dict(categoria=cat, original=texto, linea=linea,
                         inicio=inicio, fin=inicio + len(texto))
    m = re.fullmatch(r"SESION (S[0-9]{2})", raw)
    if m:
        return [token("SESION", "SESION"), token("ID", m[1], 7)]
    if raw == "FIN":
        return [token("FIN", raw)]
    m = re.fullmatch(r"([0-9]+) ([A-Z]+): (.+)", raw)
    if m and m[3].strip():
        return [token("NUM", m[1]), token(m[2], m[2], m.start(2)),
                token("DOSPUNTOS", ":", m.end(2)), token("TEXTO", m[3], m.start(3))]
    return [token("LINEA_INVALIDA", raw)]


def analizar_formato(texto):
    entrada, por_linea = [], {}
    for numero, raw in enumerate(texto.splitlines(), 1):
        ts = tokens_linea(raw, numero)
        por_linea[numero] = PARSER_LINEA.parsear(ts)
        entrada.extend(ts)
        entrada.append(("NL", dict(linea=numero, original="\n")))
    global_ = PARSER_LOTE.parsear(entrada, recuperar=True)
    # Las acciones de dominio se aplican solo a líneas válidas del protocolo;
    # la recuperación global no autoriza nodos reparados a generar evidencias.
    return por_linea, dict(aceptada=global_["aceptada"], pasos=global_["pasos"],
                           errores=global_["errores"])
