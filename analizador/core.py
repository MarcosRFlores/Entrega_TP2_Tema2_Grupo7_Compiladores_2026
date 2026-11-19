"""Coordinacion del lote; las fases se implementan en modulos separados."""
from __future__ import annotations
import re
from dataclasses import asdict
from pathlib import Path
from analizador_lexico import lexear
from tabla_simbolos import TablaSimbolos, TablaLexica
from analizador_sintactico import PARSER_TEXTO, ParserClausula, clausulas
from analizador_semantico import resumir, inferir_estado
from .formato import analizar_formato
ROOT = Path(__file__).resolve().parent.parent


def analizar(texto, consultar=None):
    sesiones, errores_lote = [], []
    tabla_lexica = TablaLexica()
    formato_lineas, formato_lote = analizar_formato(texto)
    actual = None
    tabla = None
    esperada = 1
    ids = set()

    def error(codigo, linea, detalle, **extra):
        e = dict(codigo=codigo, linea=linea, detalle=detalle, **extra)
        (actual["errores"] if actual is not None else errores_lote).append(e)
        if actual is not None:
            actual["analisis"] = "PARCIAL"

    def cerrar():
        if actual is None:
            return
        if not actual["turnos"]:
            error("SESION_VACIA", actual["linea"], "No hay turnos válidos")
        evs = actual["evidencias"]
        actual["resumen_por_aspecto"] = resumir(evs)
        actual["resumen_cliente"] = resumir([e for e in evs if e["actor"] == "CLIENTE"])
        actual["resumen_agente"] = resumir([e for e in evs if e["actor"] == "AGENTE"])
        actual["estado"], actual["evidencia_estado"] = inferir_estado(evs)
        actual["entidades"] = list(tabla.entradas.values())
        actual["tabla_operaciones"] = tabla.operaciones
        sesiones.append(actual)

    for linea, raw in enumerate(texto.splitlines(), 1):
        cab = re.fullmatch(r"SESION (S[0-9]{2})", raw)
        if cab:
            if actual is not None:
                error("FALTA_FIN", linea, "Se recupera en la siguiente cabecera")
                cerrar()
            sid = cab[1]
            actual = dict(id=sid, linea=linea, analisis="COMPLETO", turnos=[],
                          evidencias=[], correcciones=[], errores=[])
            tabla, esperada = TablaSimbolos(sid), 1
            if sid in ids:
                error("SESION_DUPLICADA", linea, sid)
            ids.add(sid)
            continue
        if raw == "FIN":
            if actual is None:
                error("FIN_SIN_SESION", linea, raw)
            else:
                cerrar()
                actual = None
            continue
        if actual is None:
            error("FUERA_SESION", linea, raw)
            continue
        m = re.fullmatch(r"([0-9]+) ([A-Z]+): (.+)", raw)
        if not m or not m[3].strip():
            error("FORMATO_TURNO", linea, raw, rechazado=True)
            continue
        numero, rol, contenido = int(m[1]), m[2], m[3]
        if numero != esperada or rol not in ("CLIENTE", "AGENTE"):
            error("ROL_INVALIDO" if rol not in ("CLIENTE", "AGENTE") else "ORDEN_INVALIDO",
                  linea, raw, rechazado=True, esperado=esperada)
            # La línea numerada rechazada ocupa su lugar físico si avanza.
            # Un duplicado o retroceso no mueve el contador hacia atrás.
            esperada = max(esperada, numero + 1)
            continue
        esperada = numero + 1
        inicio_ops = len(tabla.operaciones)
        tabla.insertar("PARTICIPANTE", rol, numero, 0, rol)
        inicio_lexico = len(tabla_lexica.operaciones)
        tokens, correcciones = lexear(contenido, actual["id"], numero, tabla_lexica, consultar)
        actual["correcciones"].extend(correcciones)
        for t in tokens:
            if t.categoria in ("REF", "MONTO"):
                tabla.insertar(t.categoria, t.normalizado, numero, t.inicio, t.original)
        turno = dict(numero=numero, rol=rol, texto=contenido,
                     tokens=[asdict(t) for t in tokens], clausulas=[],
                     no_interpretados=[], evidencias=[],
                     formato=formato_lineas[linea])
        entrada_texto = [("FIN_FRASE" if t.categoria == "PUNT" and t.original in "." else t.categoria, t)
                         for t in tokens if not (t.categoria == "PUNT" and t.original == ",")]
        sintaxis_texto = PARSER_TEXTO.parsear(entrada_texto, recuperar=True)
        turno["sintaxis_texto"] = {k: sintaxis_texto[k] for k in ("aceptada", "pasos", "errores")}
        if not sintaxis_texto["aceptada"]:
            actual["analisis"] = "PARCIAL"
        for enlace, ts in clausulas(tokens):
            parser = ParserClausula(ts)
            arbol = parser.parsear()
            fragmento = contenido[ts[0].inicio:ts[-1].fin]
            if arbol is None:
                turno["no_interpretados"].append(dict(texto=fragmento, inicio=ts[0].inicio,
                                                       fin=ts[-1].fin, marca="NO_INTERPRETADOS",
                    parser=parser.detalle, error_semantico=parser.error_semantico))
                actual["analisis"] = "PARCIAL"
                continue
            turno["clausulas"].append(dict(enlace=enlace, inicio=ts[0].inicio,
                                           fin=ts[-1].fin, texto=fragmento, estructura=arbol))
            eid = f'{actual["id"]}:D{len(actual["evidencias"]) + 1}'
            ev = dict(id=eid, turno=numero, actor=rol, texto=fragmento,
                      inicio=ts[0].inicio, fin=ts[-1].fin, regla=arbol["produccion"],
                      producciones_sintacticas=[p["produccion"] for p in arbol["derivacion"] if p["accion"] == "EXPANDIR"],
                      aspecto=arbol["aspecto"], valoracion=arbol["valoracion"],
                      evento=arbol["evento"], negada=arbol["negada"],
                      intensidad=arbol["intensidad"])
            actual["evidencias"].append(ev)
            turno["evidencias"].append(eid)
        if not sintaxis_texto["aceptada"] and not turno["no_interpretados"]:
            turno["no_interpretados"].append(dict(texto=contenido, inicio=0,
                fin=len(contenido), marca="NO_INTERPRETADOS",
                motivo="Estructura del texto incompleta; las cláusulas válidas se conservan"))
            actual["analisis"] = "PARCIAL"
        turno["valoraciones"] = resumir([e for e in actual["evidencias"] if e["turno"] == numero])
        turno["tabla_operaciones"] = tabla.operaciones[inicio_ops:]
        turno["tabla_lexica_operaciones"] = tabla_lexica.operaciones[inicio_lexico:]
        actual["turnos"].append(turno)
    if actual is not None:
        error("FALTA_FIN", len(texto.splitlines()) + 1, "Fin de archivo")
        cerrar()
    return dict(version="2.1", sesiones=sesiones, errores=errores_lote, formato=formato_lote,
                tabla_lexica=dict(entradas=tabla_lexica.entradas, operaciones=tabla_lexica.operaciones),
                advertencia="Estados inferidos de la conversación; no son confirmaciones bancarias.")
