"""Atributos sobre árbol aceptado; ninguna acción sobre nodos recuperados."""
from analizador.predictivo import hojas

ASPECTOS = ("TRANSFERENCIA", "ATENCION", "CLARIDAD")


def descendiente(arbol, simbolo):
    pendientes = [arbol]
    while pendientes:
        n = pendientes.pop()
        if n["simbolo"] == simbolo:
            return n
        pendientes.extend(reversed(n["hijos"]))
    return None


def contexto_monetario(sujeto, complemento):
    """Admite la elipsis del dominio, pero no sujetos u objetos incompatibles."""
    if sujeto is not None:
        if sujeto["categoria"] not in ("TRANSFERENCIA", "DESTINATARIO", "REF"):
            return False
        if sujeto["categoria"] == "REF" and not sujeto["normalizado"].startswith("TR-"):
            return False
    if any(c in ("ATENCION", "CLARIDAD", "RECLAMO", "REVERSION") for c, _ in complemento):
        return False
    # RC identifica un reclamo, no el dinero recibido. Puede acompañar un
    # objeto monetario explícito, pero no sustituirlo por sí solo.
    tiene_reclamo = any(c == "REF" and t["normalizado"].startswith("RC-") for c, t in complemento)
    tiene_dinero = any(c in ("OBJETO", "TRANSFERENCIA", "MONTO") or
                      (c == "REF" and t["normalizado"].startswith("TR-")) for c, t in complemento)
    sujeto_monetario = sujeto is not None and sujeto["categoria"] in ("TRANSFERENCIA", "REF")
    return not tiene_reclamo or tiene_dinero or sujeto_monetario


def evaluar(arbol):
    sujeto_n = descendiente(arbol, "<nucleo>")
    sujeto = hojas(sujeto_n)[0][1] if sujeto_n else None
    pred = descendiente(arbol, "<predicado>")
    negada = any(c == "NO" for c, _ in hojas(descendiente(pred, "<prefijo>")))
    cuerpo_h = hojas(descendiente(pred, "<cuerpo>"))
    tipo = cuerpo_h[0][0]
    complemento = hojas(descendiente(pred, "<complementos>"))
    intensidad = "MUY" if any(c == "MUY" for c, _ in cuerpo_h) else "NORMAL"
    juicio = next((c for c, _ in cuerpo_h if c in ("POSITIVO", "NEGATIVO")), None)
    regla, aspecto, valoracion, evento = None, None, None, None
    motivo = None
    if tipo in ("RECEPCION", "DEVOLUCION", "CONTINUA") and not contexto_monetario(sujeto, complemento):
        return None, "La recepción, devolución o falta de llegada no tiene un contexto monetario compatible"
    if tipo in ("COPULA", "MUY", "POSITIVO", "NEGATIVO"):
        if sujeto is None or sujeto["categoria"] not in (*ASPECTOS, "AGENTE"):
            motivo = "Una opinión requiere sujeto de aspecto o agente"
        elif tipo != "COPULA" and sujeto["categoria"] not in ASPECTOS:
            motivo = "Una opinión sin cópula requiere un aspecto explícito"
        else:
            regla = "S_OPINION"
            aspecto = "ATENCION" if sujeto["categoria"] == "AGENTE" else sujeto["categoria"]
            valoracion = "POSITIVA" if juicio == "POSITIVO" else "NEGATIVA"
    elif tipo == "ATENDER":
        regla, aspecto = "S_ATENCION", "ATENCION"
        valoracion = "POSITIVA" if juicio == "POSITIVO" else "NEGATIVA"
    elif tipo == "ENTENDER":
        regla, aspecto, valoracion = "S_CLARIDAD", "CLARIDAD", "POSITIVA"
    elif tipo == "ENVIO":
        regla, aspecto, valoracion = "S_ENVIO", "TRANSFERENCIA", "NEUTRA"
    elif tipo == "RECEPCION":
        regla, aspecto, valoracion, evento = "S_RECEPCION", "TRANSFERENCIA", "POSITIVA", "ACREDITADA"
    elif tipo == "DEVOLUCION":
        regla, aspecto, valoracion, evento = "S_DEVOLUCION", "TRANSFERENCIA", "POSITIVA", "REVERTIDA"
    elif tipo == "CONTINUA":
        if negada:
            motivo = "Negación de sigue sin llegar fuera del alcance acotado"
        else:
            regla, aspecto, valoracion, evento = "S_SIN_LLEGAR", "TRANSFERENCIA", "NEGATIVA", "NO_ACREDITADA"
    elif tipo in ("SEGUIMIENTO", "SOLICITUD"):
        if tipo == "SOLICITUD" and not any(c == "REVERSION" for c, _ in complemento):
            motivo = "Una solicitud sin reversión explícita no determina seguimiento"
        else:
            regla, evento = "S_SEGUIMIENTO", "PENDIENTE"
    elif tipo in ("AGRADECIMIENTO", "PAGO"):
        regla = "S_CORTESIA" if tipo == "AGRADECIMIENTO" else "S_MENCION_PAGO"
    if motivo:
        return None, motivo
    if negada:
        if valoracion in ("POSITIVA", "NEGATIVA"):
            valoracion = "NEGATIVA" if valoracion == "POSITIVA" else "POSITIVA"
        if evento == "ACREDITADA":
            evento = "NO_ACREDITADA"
        elif evento in ("REVERTIDA", "PENDIENTE"):
            evento = None
    atributos = dict(produccion=regla, sujeto=sujeto,
        verbo=cuerpo_h[0][1]["normalizado"] if tipo not in ("MUY", "POSITIVO", "NEGATIVO") else None,
        negada=negada, intensidad=intensidad, aspecto=aspecto,
        valoracion=valoracion, evento=evento)
    arbol["atributos"] = atributos.copy()
    return atributos, None




def resumir(evidencias):
    salida = {}
    for aspecto in ASPECTOS:
        evs = [e for e in evidencias if e["aspecto"] == aspecto]
        valores = {e["valoracion"] for e in evs}
        valor = ("MIXTA" if {"POSITIVA", "NEGATIVA"} <= valores else
                 "POSITIVA" if "POSITIVA" in valores else
                 "NEGATIVA" if "NEGATIVA" in valores else
                 "NEUTRA" if "NEUTRA" in valores else "SIN_EVIDENCIA")
        salida[aspecto] = dict(valoracion=valor, evidencias=[e["id"] for e in evs])
    return salida



def inferir_estado(evidencias):
    """Ultima declaracion del CLIENTE; en su ausencia, seguimiento no negado."""
    declaraciones = [e for e in evidencias if e['actor'] == 'CLIENTE' and
                     e['evento'] in ('ACREDITADA','NO_ACREDITADA','REVERTIDA')]
    promesas = [e for e in evidencias if e['evento'] == 'PENDIENTE']
    fuente = declaraciones[-1] if declaraciones else promesas[-1] if promesas else None
    return (fuente['evento'], fuente['id']) if fuente else ('NO_CONFIRMADA',None)
