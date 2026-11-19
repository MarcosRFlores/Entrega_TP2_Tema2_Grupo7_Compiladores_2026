"""Thompson completo, subconjuntos y minimización de referencias."""
from collections import deque

ALFABETO = ("-", "C", "D", "R", "T")


def simbolo(c):
    return "D" if c in "0123456789" else c.upper()


class Thompson:
    def __init__(self):
        self.transiciones = {}
        self.siguiente = 0

    def nuevo(self):
        n = self.siguiente
        self.siguiente += 1
        self.transiciones[n] = {}
        return n

    def arco(self, a, etiqueta, b):
        self.transiciones[a].setdefault(etiqueta, set()).add(b)

    def construir(self, expresion):
        op, *args = expresion
        if op in ("lit", "eps"):
            s, f = self.nuevo(), self.nuevo()
            self.arco(s, args[0] if op == "lit" else "ε", f)
            return s, f
        if op == "concat":
            primero, ultimo = self.construir(args[0])
            for parte in args[1:]:
                s, f = self.construir(parte)
                self.arco(ultimo, "ε", s)
                ultimo = f
            return primero, ultimo
        if op == "alt":
            s, f = self.nuevo(), self.nuevo()
            for parte in args:
                a, b = self.construir(parte)
                self.arco(s, "ε", a)
                self.arco(b, "ε", f)
            return s, f
        raise ValueError(op)

    def cerradura(self, estados):
        salida = set(estados)
        pendientes = list(estados)
        while pendientes:
            s = pendientes.pop()
            for t in self.transiciones[s].get("ε", set()) - salida:
                salida.add(t)
                pendientes.append(t)
        return frozenset(salida)

    def mover(self, estados, a):
        return {t for s in estados for t in self.transiciones[s].get(a, set())}


def determinizar(afn, inicio, final, alfabeto=ALFABETO):
    inicial = afn.cerradura({inicio})
    nombres = {inicial: "q0"}
    pendientes = deque([inicial])
    trans, finales, subconjuntos = {}, set(), {}
    while pendientes:
        grupo = pendientes.popleft()
        q = nombres[grupo]
        subconjuntos[q] = sorted(grupo)
        trans[q] = {}
        if final in grupo:
            finales.add(q)
        for a in alfabeto:
            destino = afn.cerradura(afn.mover(grupo, a))
            if destino not in nombres:
                nombres[destino] = f"q{len(nombres)}"
                pendientes.append(destino)
            trans[q][a] = nombres[destino]
    return dict(inicio="q0", finales=sorted(finales), transiciones=trans,
                subconjuntos=subconjuntos)


def minimizar(afd, alfabeto=ALFABETO):
    finales = set(afd["finales"])
    estados = set(afd["transiciones"])
    grupos = [g for g in (finales, estados - finales) if g]
    historial = []
    while True:
        historial.append([sorted(g) for g in grupos])
        indice = {s: i for i, g in enumerate(grupos) for s in g}
        nuevos = []
        for g in grupos:
            firmas = {}
            for s in sorted(g):
                firma = tuple(indice[afd["transiciones"][s][a]] for a in alfabeto)
                firmas.setdefault(firma, set()).add(s)
            nuevos.extend(firmas.values())
        if {frozenset(g) for g in nuevos} == {frozenset(g) for g in grupos}:
            break
        grupos = nuevos
    indice = {s: i for i, g in enumerate(grupos) for s in g}
    inicial = indice[afd["inicio"]]
    nombres, pendientes = {inicial: "m0"}, deque([inicial])
    trans, finales_min, equivalencias = {}, [], {}
    while pendientes:
        g = pendientes.popleft()
        nombre = nombres[g]
        representante = sorted(grupos[g])[0]
        equivalencias[nombre] = sorted(grupos[g])
        if grupos[g] & finales:
            finales_min.append(nombre)
        trans[nombre] = {}
        for a in alfabeto:
            destino = indice[afd["transiciones"][representante][a]]
            if destino not in nombres:
                nombres[destino] = f"m{len(nombres)}"
                pendientes.append(destino)
            trans[nombre][a] = nombres[destino]
    return dict(inicio="m0", finales=finales_min, transiciones=trans,
                equivalencias=equivalencias, particiones=historial)


def construir_referencia():
    lit = lambda x: ("lit", x)
    opcional = lambda: ("alt", ("eps",), lit("D"))
    er = ("concat", ("alt", ("concat", lit("T"), lit("R")),
                      ("concat", lit("R"), lit("C"))), lit("-"),
          lit("D"), lit("D"), lit("D"), opcional(), opcional(), opcional())
    afn = Thompson()
    inicio, final = afn.construir(er)
    afd = determinizar(afn, inicio, final)
    registro = dict(er="(TR|RC)-DDD(ε|D)(ε|D)(ε|D)", alfabeto=list(ALFABETO),
        thompson=dict(inicio=inicio, final=final, estados=afn.siguiente,
            transiciones=[dict(origen=s, simbolo=a, destino=t)
                for s, fila in afn.transiciones.items()
                for a, destinos in sorted(fila.items()) for t in sorted(destinos)]),
        afd=afd, minimo=minimizar(afd))
    return afn, inicio, final, registro


AFN_REF, INICIO_REF, FINAL_REF, AUTOMATA_REF = construir_referencia()


def reconocer_referencia(texto):
    afd = AUTOMATA_REF["minimo"]
    estado = afd["inicio"]
    recorrido = [estado]
    for c in texto:
        estado = afd["transiciones"].get(estado, {}).get(simbolo(c), "ERROR")
        recorrido.append(estado)
    return estado in afd["finales"], recorrido
