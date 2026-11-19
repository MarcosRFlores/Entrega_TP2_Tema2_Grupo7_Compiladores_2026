"""Analizador LL(1) genérico: tabla M + pila, sin retroceso."""
from dataclasses import asdict, is_dataclass
from .gramatica import EPS, calcular


class ErrorSintactico(ValueError):
    pass


def serializar_token(t):
    return asdict(t) if is_dataclass(t) else t


class Predictivo:
    def __init__(self, reglas):
        self.reglas = reglas
        self.info = calcular(reglas)
        if not self.info["es_ll1"]:
            raise ValueError("La gramática no es LL(1)")
        self.m = self.info["tabla_m"]

    def parsear(self, entrada, recuperar=False):
        """Entrada: pares (categoría, dato). No sintetiza semántica de nodos dañados.

        La recuperación aplica sinc=SGTE a casillas vacías, omisión de token
        si no hay entrada/sinc y omisión de terminal esperado en match fallido.
        Toda recuperación invalida el árbol para decisiones de dominio.
        """
        datos = list(entrada) + [("$", None)]
        raiz = dict(simbolo=self.info["simbolo_inicial"], hijos=[])
        pila = [("$", None), (raiz["simbolo"], raiz)]
        ip, pasos, errores = 0, [], []
        while pila:
            x, nodo = pila[-1]
            a, dato = datos[ip]
            base = dict(indice=ip, preanalisis=a, pila=[s for s, _ in pila])
            if x not in self.reglas:
                if x == a:
                    pila.pop()
                    if nodo is not None:
                        nodo["token"] = serializar_token(dato)
                    pasos.append(dict(**base, accion="ACEPTAR" if x == "$" else "MATCH", simbolo=x))
                    if x != "$":
                        ip += 1
                    continue
                motivo = dict(**base, accion="ERROR_MATCH", esperado=x)
                errores.append(motivo)
                pasos.append(motivo)
                if not recuperar:
                    break
                if x == "$":
                    # La pila terminó pero sobra entrada: consumirla hasta $.
                    ip += 1
                else:
                    pila.pop()
                continue
            celda = self.m.get(x, {}).get(a)
            if celda:
                prod = celda[0]
                rhs = [s for s in prod["cuerpo"] if s != EPS]
                pila.pop()
                nodo["produccion"] = f'{x} ::= ' + " ".join(rhs or [EPS])
                nodo["hijos"] = [dict(simbolo=s, hijos=[]) for s in rhs]
                pasos.append(dict(**base, accion="EXPANDIR", produccion=nodo["produccion"]))
                pila.extend(reversed(list(zip(rhs, nodo["hijos"]))))
                continue
            sync = a in self.info["siguiente"][x] or a == "$"
            motivo = dict(**base, accion="SINC" if sync else "OMITIR_TOKEN", no_terminal=x,
                          esperados=sorted(self.m.get(x, {})))
            errores.append(motivo)
            pasos.append(motivo)
            if not recuperar:
                break
            if sync:
                pila.pop()
            else:
                ip += 1
        aceptada = not errores and not pila and datos[ip][0] == "$"
        return dict(aceptada=aceptada, arbol=raiz, pasos=pasos, errores=errores)


def hojas(nodo):
    """Recorrido iterativo: evita profundidad proporcional a los turnos."""
    pendientes, resultado = [nodo], []
    while pendientes:
        n = pendientes.pop()
        if "token" in n:
            resultado.append((n["simbolo"], n["token"]))
        pendientes.extend(reversed(n["hijos"]))
    return resultado
