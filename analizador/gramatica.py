"""BNF, PRIMERO/SIGUIENTE, tabla M y ciclos de esquina izquierda."""
import re
EPS = "ε"

def leer_bnf(texto):
    bloque = re.search(r"```bnf\s*\n(.*?)```", texto, re.S)
    contenido = bloque[1] if bloque else texto
    reglas = {}
    actual = None
    for linea in contenido.splitlines():
        if not linea.strip():
            continue
        if "::=" in linea:
            actual, cuerpo = linea.split("::=", 1)
            actual = actual.strip()
            if actual in reglas:
                raise ValueError("Encabezado repetido: " + actual)
            reglas[actual] = []
        else:
            cuerpo = linea.strip()
            if not cuerpo.startswith("|") or actual is None:
                raise ValueError("Continuación inválida: " + linea)
            cuerpo = cuerpo[1:]
        tokens = re.findall(r'"[^"\n]*"|<[^>\n]+>|[A-Z][A-Z0-9_]*|ε|\|', cuerpo)
        opciones = [[]]
        for token in tokens:
            if token == "|":
                opciones.append([])
            elif token != EPS:
                opciones[-1].append(token)
        reglas[actual].extend(opciones)
    indefinidos = {s for rs in reglas.values() for r in rs for s in r
                   if s.startswith("<") and s not in reglas}
    if indefinidos:
        raise ValueError(f"No terminales sin producción: {indefinidos}")
    return reglas


def calcular(reglas):
    primero = {nt: set() for nt in reglas}

    def prim_secuencia(secuencia):
        result = set()
        for s in secuencia:
            ps = primero[s] if s in reglas else {s}
            result.update(ps - {EPS})
            if EPS not in ps:
                return result
        result.add(EPS)
        return result

    cambio = True
    while cambio:
        cambio = False
        for nt, opciones in reglas.items():
            antes = len(primero[nt])
            for rhs in opciones:
                primero[nt].update(prim_secuencia(rhs))
            cambio |= len(primero[nt]) != antes
    siguiente = {nt: set() for nt in reglas}
    siguiente[next(iter(reglas))].add("$")
    cambio = True
    while cambio:
        cambio = False
        for nt, opciones in reglas.items():
            for rhs in opciones:
                for i, s in enumerate(rhs):
                    if s not in reglas:
                        continue
                    antes = len(siguiente[s])
                    cola = prim_secuencia(rhs[i + 1:])
                    siguiente[s].update(cola - {EPS})
                    if EPS in cola:
                        siguiente[s].update(siguiente[nt])
                    cambio |= len(siguiente[s]) != antes
    assert all(EPS not in ss for ss in siguiente.values())
    tabla = {}
    for nt, opciones in reglas.items():
        for numero, rhs in enumerate(opciones, 1):
            ps = prim_secuencia(rhs)
            seleccion = ps - {EPS}
            if EPS in ps:
                seleccion |= siguiente[nt]
            for terminal in sorted(seleccion):
                tabla.setdefault(nt, {}).setdefault(terminal, []).append(
                    dict(alternativa=numero, cuerpo=rhs or [EPS]))
    conflictos = [dict(no_terminal=nt, preanalisis=t, producciones=prods)
                  for nt, fila in tabla.items() for t, prods in fila.items()
                  if len(prods) > 1]
    # Grafo de esquina izquierda incluyendo prefijos anulables.
    arcos = {nt: set() for nt in reglas}
    for nt, opciones in reglas.items():
        for rhs in opciones:
            for s in rhs:
                if s not in reglas:
                    break
                arcos[nt].add(s)
                if EPS not in primero[s]:
                    break
    recursivos = []
    for nt in reglas:
        pendientes = list(arcos[nt])
        visitados = set()
        while pendientes:
            s = pendientes.pop()
            if s in visitados:
                continue
            visitados.add(s)
            pendientes.extend(arcos[s] - visitados)
        if nt in visitados:
            recursivos.append(nt)
    return dict(simbolo_inicial=next(iter(reglas)),
                primero={k: sorted(v) for k, v in primero.items()},
                siguiente={k: sorted(v) for k, v in siguiente.items()},
                tabla_m=tabla, conflictos=conflictos,
                recursion_izquierda=recursivos,
                es_ll1=not conflictos and not recursivos)

