"""Tabla léxica del lote y tabla de entidades por sesión, independientes."""
import json
from pathlib import Path


class TablaLexica:
    """Relación lexema-token precargada; aprende en memoria durante el lote."""
    def __init__(self, archivo=None):
        archivo = archivo or Path(__file__).resolve().parent / "tabla_lexica_inicial.json"
        self.entradas = json.loads(Path(archivo).read_text(encoding="utf-8"))
        if not isinstance(self.entradas, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in self.entradas.items()):
            raise ValueError("La tabla léxica debe ser un objeto JSON lexema: token")
        self.operaciones = []

    def buscar(self, lexema, **posicion):
        token = self.entradas.get(lexema)
        self.operaciones.append(dict(operacion="BUSCAR", lexema=lexema,
                                     token=token, encontrada=token is not None, **posicion))
        return token

    def insertar(self, lexema, token, **posicion):
        anterior = self.entradas.get(lexema)
        if anterior is not None and anterior != token:
            raise ValueError(f"Clasificación incompatible para {lexema!r}")
        self.entradas[lexema] = token
        self.operaciones.append(dict(operacion="INSERTAR" if anterior is None else "ACTUALIZAR",
                                     lexema=lexema, token=token, **posicion))


class TablaSimbolos:
    def __init__(self, sesion):
        self.sesion = sesion
        self.entradas = {}
        self.operaciones = []
        self.insertar("SESION", sesion, 0, 0, sesion)

    def buscar(self, tipo, valor):
        clave = (tipo, valor)
        existe = clave in self.entradas
        self.operaciones.append(dict(operacion="BUSCAR", tipo=tipo,
                                     valor=valor, encontrada=existe))
        return self.entradas.get(clave)

    def insertar(self, tipo, valor, turno, inicio, original):
        entrada = self.buscar(tipo, valor)
        if entrada is None:
            entrada = dict(id=f"{self.sesion}:E{len(self.entradas) + 1}",
                           tipo=tipo, valor=valor, ambito=self.sesion,
                           apariciones=[])
            self.entradas[(tipo, valor)] = entrada
            accion = "INSERTAR"
        else:
            accion = "ACTUALIZAR"
        aparicion = dict(turno=turno, inicio=inicio, original=original)
        if aparicion not in entrada["apariciones"]:
            entrada["apariciones"].append(aparicion)
        self.operaciones.append(dict(operacion=accion, id=entrada["id"],
                                     turno=turno, inicio=inicio))
        return entrada["id"]

