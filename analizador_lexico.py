"""Tokens, normalizacion y correccion del vocabulario acotado."""
from __future__ import annotations
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from analizador.automatas import reconocer_referencia
from tabla_simbolos import TablaLexica
ROOT = Path(__file__).resolve().parent
VOCAB = json.loads((ROOT / 'diccionario.json').read_text(encoding='utf-8'))
CATEGORIAS_USUARIO = sorted({v["categoria"] for v in VOCAB.values()})


def normalizar(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def levenshtein(a, b):
    """Programación dinámica; sin bibliotecas de coincidencia aproximada."""
    fila = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        nueva = [i]
        for j, cb in enumerate(b, 1):
            nueva.append(min(nueva[-1] + 1, fila[j] + 1,
                             fila[j - 1] + (ca != cb)))
        fila = nueva
    return fila[-1]


@dataclass
class Token:
    categoria: str
    original: str
    normalizado: str
    sesion: str
    turno: int
    inicio: int
    fin: int
    recorrido_afd: list | None = None



# Prioridad de izquierda a derecha. Un identificador mal formado se conserva
# como unidad desconocida para impedir corregir partes de TR-/RC-.
LEX = re.compile(
    r"(?P<REFERENCIA>(?<!\w)(?:TR|RC)-[\w-]*)"
    r"|(?P<MONTO>(?<!\w)G\.[ \t]*(?:[0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+)(?!\w|\.[0-9]))"
    r"|(?P<CIFRA>[0-9]+(?:[.,][0-9]+)*)"
    r"|(?P<PALABRA>[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]+)"
    r"|(?P<PUNT>[.,])|(?P<OTRO>\S)", re.UNICODE | re.IGNORECASE)


def lexear(texto, sesion, turno, tabla=None, consultar=None):
    """Consulta → patrones/AFD → Levenshtein → consulta humana si queda sin token.

    consultar(original, categorias) devuelve una categoría existente o None.
    Los empates y las entidades protegidas nunca se reclasifican por interacción.
    """
    if tabla is None:
        tabla = TablaLexica()
    tokens, correcciones = [], []
    for m in LEX.finditer(texto):
        cat, original = m.lastgroup, m.group()
        norm = normalizar(original)
        clave = norm
        posicion = dict(sesion=sesion, turno=turno, inicio=m.start(), fin=m.end())
        conocido = tabla.buscar(clave, **posicion)
        recorrido = None
        empate = False
        if cat == "REFERENCIA":
            valida, recorrido = reconocer_referencia(original)
            cat = "REF" if valida else "REF_INVALIDA"
            norm = original.upper()
        elif cat == "MONTO":
            norm = re.sub(r"\D", "", original)
        elif cat == "PALABRA":
            if conocido is None and norm not in VOCAB and norm != "no":
                candidatos = sorted(w for w in tabla.entradas
                                    if re.fullmatch(r"[a-zñü]+", w)
                                    and abs(len(w) - len(norm)) <= 1
                                    and levenshtein(norm, w) == 1)
                if candidatos:
                    unico = len(candidatos) == 1
                    empate = not unico
                    correcciones.append(dict(turno=turno, inicio=m.start(),
                        original=original, candidatos=candidatos,
                        accion="CORREGIDA" if unico else "EMPATE",
                        resultado=candidatos[0] if unico else norm))
                    if unico:
                        norm = candidatos[0]
                        # La sugerencia debe volver a consultarse en la tabla.
                        conocido = tabla.buscar(norm, **posicion)
                        clave = norm
            cat = conocido or VOCAB.get(norm, {}).get("categoria", "DESCONOCIDA")
            norm = VOCAB.get(norm, {}).get("canonico", norm)
        elif cat == "OTRO":
            # Los caracteres ajenos se consultan, sin convertir cifras ni referencias.
            cat = conocido or "DESCONOCIDA"
        if cat == "DESCONOCIDA" and not empate and consultar is not None:
            tabla.operaciones.append(dict(operacion="CONSULTAR_USUARIO", lexema=clave, **posicion))
            respuesta = consultar(original, CATEGORIAS_USUARIO)
            if respuesta is not None:
                if respuesta not in CATEGORIAS_USUARIO:
                    raise ValueError("El token indicado no pertenece al vocabulario del TP")
                cat = respuesta
        if cat not in ("DESCONOCIDA", "REF_INVALIDA"):
            tabla.insertar(clave, cat, **posicion)
        tokens.append(Token(cat, original, norm, sesion, turno, m.start(), m.end(), recorrido))
    return tokens, correcciones
