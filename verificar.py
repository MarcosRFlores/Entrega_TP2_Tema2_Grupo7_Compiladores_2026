"""Reproduce los 12 casos, sus comprobaciones y las regresiones semánticas."""
import hashlib
import json
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from analizador.core import analizar
from analizador.gramatica import leer_bnf, calcular
from analizador_lexico import lexear
from tabla_simbolos import TablaLexica
from analizador.automatas import reconocer_referencia

ROOT=Path(__file__).resolve().parent


def guardar(nombre,dato):
    (ROOT/'resultados'/nombre).write_text(json.dumps(dato,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def regresion_semantica(lote):
    # Expectativas independientes: una recepción ajena al dinero no confirma
    # la transferencia, y una cláusula inválida no borra otra válida.
    casos=[
        ('R01','El agente recibió el reclamo.','NO_CONFIRMADA','SIN_EVIDENCIA','PARCIAL','SIN_EVIDENCIA'),
        ('R02','Recibió la explicación.','NO_CONFIRMADA','SIN_EVIDENCIA','PARCIAL','SIN_EVIDENCIA'),
        ('R03','Me devolvieron el reclamo.','NO_CONFIRMADA','SIN_EVIDENCIA','PARCIAL','SIN_EVIDENCIA'),
        ('R04','No recibió el reclamo.','NO_CONFIRMADA','SIN_EVIDENCIA','PARCIAL','SIN_EVIDENCIA'),
        ('R05','La explicación llegó.','NO_CONFIRMADA','SIN_EVIDENCIA','PARCIAL','SIN_EVIDENCIA'),
        ('R06','La explicación sigue sin llegar.','NO_CONFIRMADA','SIN_EVIDENCIA','PARCIAL','SIN_EVIDENCIA'),
        ('R07','RC-206 recibió el dinero.','NO_CONFIRMADA','SIN_EVIDENCIA','PARCIAL','SIN_EVIDENCIA'),
        ('R08','Recibió RC-206.','NO_CONFIRMADA','SIN_EVIDENCIA','PARCIAL','SIN_EVIDENCIA'),
        ('R09','Me devolvieron.','REVERTIDA','POSITIVA','COMPLETO','SIN_EVIDENCIA'),
        ('R10','El destinatario recibió el dinero.','ACREDITADA','POSITIVA','COMPLETO','SIN_EVIDENCIA'),
        ('R11','No me devolvieron el importe.','NO_CONFIRMADA','NEGATIVA','COMPLETO','SIN_EVIDENCIA'),
        ('R12','Recibió el dinero RC-206.','ACREDITADA','POSITIVA','COMPLETO','SIN_EVIDENCIA'),
        ('R13','SESION S01\n1 CLIENTE: No llegó.\n2 CLIENTE: Recibió el reclamo.\nFIN',
         'NO_ACREDITADA','NEGATIVA','PARCIAL','SIN_EVIDENCIA'),
        ('R14','Recibió la explicación, pero el agente fue amable.',
         'NO_CONFIRMADA','SIN_EVIDENCIA','PARCIAL','POSITIVA'),
    ]
    pruebas=[]
    for sid,texto,estado,transferencia,analisis,atencion in casos:
        entrada=texto if texto.startswith('SESION') else f'SESION S01\n1 CLIENTE: {texto}\nFIN'
        s=analizar(entrada)['sesiones'][0]
        esperado=dict(estado=estado,analisis=analisis,
            resumen=dict(TRANSFERENCIA=transferencia,ATENCION=atencion,CLARIDAD='SIN_EVIDENCIA'))
        obtenido=dict(estado=s['estado'],analisis=s['analisis'],
            resumen={a:v['valoracion'] for a,v in s['resumen_por_aspecto'].items()})
        sintaxis_valida=all(t['sintaxis_texto']['aceptada'] for t in s['turnos'])
        abstenciones=[n for t in s['turnos'] for n in t['no_interpretados']]
        rechazo_semantico=(all(n.get('error_semantico') for n in abstenciones) and bool(abstenciones)
                           if analisis=='PARCIAL' else not abstenciones)
        coincide=(esperado==obtenido and sintaxis_valida and not s['correcciones'] and rechazo_semantico)
        pruebas.append(dict(id=sid,entrada=entrada,esperado=esperado,obtenido=obtenido,
            sintaxis_valida=sintaxis_valida,rechazo_semantico=bool(rechazo_semantico),coincide=coincide))
    evidencia=json.loads((ROOT/'resultados/regresion_semantica.json').read_text(encoding='utf-8'))
    # La versión 2.1 agrega la tabla léxica y su traza. Se compara todo el
    # contrato anterior, excluyendo únicamente esos campos nuevos y la versión.
    anterior=deepcopy(lote)
    anterior['version']='2.0'
    anterior.pop('tabla_lexica')
    for sesion in anterior['sesiones']:
        for turno in sesion['turnos']:
            turno.pop('tabla_lexica_operaciones')
    corpus_sha=hashlib.sha256(json.dumps(anterior,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()
    sin_cambios=corpus_sha==evidencia['antes']['sha256_salida_corpus']
    evidencia['verificacion_actual']=dict(
        sha256_analizador_semantico=hashlib.sha256((ROOT/'analizador_semantico.py').read_bytes()).hexdigest(),
        corpus_original_sin_cambios=sin_cambios,casos_semanticos=pruebas,
        criterio_corpus='Contrato 2.0 completo; se excluyen tabla_lexica, tabla_lexica_operaciones y cambio de versión',
        coinciden=sum(p['coincide'] for p in pruebas),total=len(pruebas))
    guardar('regresion_semantica.json',evidencia)
    if not sin_cambios or not all(p['coincide'] for p in pruebas):
        raise SystemExit('FALLO: regresión semántica; consultar resultados/regresion_semantica.json.')
    return len(pruebas)


def verificar_requerimientos():
    """Pruebas funcionales de aprendizaje, protección e interacción real del lexer."""
    pruebas=[]

    def comprobar(nombre, esperado, obtenido):
        pruebas.append(dict(prueba=nombre, esperado=esperado, obtenido=obtenido,
                            coincide=esperado == obtenido))

    ruta=ROOT/'tabla_lexica_inicial.json'
    inicial=ruta.read_bytes()
    tabla=TablaLexica()
    comprobar('JSON precargado conocido', 'TRANSFERENCIA', tabla.buscar('transferencia'))
    tokens,_=lexear('TR-123 G. 250.000 123', 'S01', 1, tabla)
    comprobar('Aprender referencia, monto y cifra por patrones',
              ['REF','MONTO','CIFRA'], [t.categoria for t in tokens])
    comprobar('Insertar lexemas reconocidos', ['REF','MONTO','CIFRA'],
              [tabla.entradas.get(k) for k in ('tr-123','g. 250.000','123')])
    consultas=[]

    def consultar(original, categorias):
        consultas.append(original)
        return 'SEGUIMIENTO'

    entrada='SESION S01\n1 AGENTE: gestionaremos RC-123.\n2 AGENTE: gestionaremos RC-123.\nFIN\nSESION S02\n1 AGENTE: gestionaremos.\nFIN'
    lote=analizar(entrada,consultar)
    comprobar('Consulta única y aprendizaje entre turnos y sesiones', ['gestionaremos'], consultas)
    comprobar('Clasificación interactiva y parser', ['PENDIENTE','PENDIENTE'],
              [s['estado'] for s in lote['sesiones']])
    comprobar('Aprendizaje visible en salida', 'SEGUIMIENTO',
              lote['tabla_lexica']['entradas'].get('gestionaremos'))
    comprobar('Consulta y registro de nuevo lexema trazables',
              ['BUSCAR','CONSULTAR_USUARIO','INSERTAR'],
              [o['operacion'] for o in lote['tabla_lexica']['operaciones'] if o['lexema']=='gestionaremos'][:3])
    aprendida=TablaLexica()
    lexear('gestionaremos','S01',1,aprendida,consultar)
    tokens,corr=lexear('gestionaremo','S01',2,aprendida)
    comprobar('Levenshtein incluye palabras aprendidas', ['SEGUIMIENTO','gestionaremos'],
              [tokens[0].categoria,corr[0]['resultado']])
    comprobar('Diccionario canónico independiente', False,
              'gestionaremos' in json.loads((ROOT/'diccionario.json').read_text(encoding='utf-8')))
    sin_aprender=analizar('SESION S01\n1 CLIENTE: gestionaremos.\nFIN')['sesiones'][0]
    comprobar('Aprendizaje limitado al lote; abstención sin consulta',
              ['PARCIAL','NO_CONFIRMADA'], [sin_aprender['analisis'],sin_aprender['estado']])
    consultas.clear()
    tokens,corr=lexear('pag no TR-204 RC-205 TR-20 G. 250.000 123','S01',1,consultar=consultar)
    comprobar('No consultar empate ni entidades protegidas', [], consultas)
    comprobar('Empate obligatorio sin reclasificación', ['pag','DESCONOCIDA','EMPATE'],
              [tokens[0].normalizado,tokens[0].categoria,corr[0]['accion']])
    comprobar('NO protegido', ['NO','no'], [tokens[1].categoria,tokens[1].normalizado])
    tabla=TablaLexica()
    tokens,corr=lexear('tranferencia', 'S01', 1, tabla)
    comprobar('Reconsulta tras corrección única', ['tranferencia','transferencia'],
              [o['lexema'] for o in tabla.operaciones if o['operacion']=='BUSCAR'])
    comprobar('Texto y posición originales conservados', ['tranferencia',0,12,'TRANSFERENCIA'],
              [tokens[0].original,tokens[0].inicio,tokens[0].fin,tokens[0].categoria])
    for referencia,valida in [('TR-123',True),('RC-123456',True),('TR-12',False),('RC-1234567',False)]:
        comprobar('Límite AFD '+referencia,valida,reconocer_referencia(referencia)[0])
    s=analizar('SESION S01\n1 CLIENTE: gestionaremos.\nFIN',lambda *_:None)['sesiones'][0]
    comprobar('Usuario se abstiene; no se inventa opinión', ['PARCIAL','SIN_EVIDENCIA'],
              [s['analisis'],s['resumen_por_aspecto']['TRANSFERENCIA']['valoracion']])
    recuperado=analizar('SESION S01\n1 CLIENTE: No llegó.\n3 CLIENTE: Ya recibió.\n4 CLIENTE: Me devolvieron.\nFIN\nSESION S02\n1 CLIENTE: Gracias.\nFIN')['sesiones']
    comprobar('Rechazar orden inconsistente y continuar siguiente línea y sesión',
              [[1,4],'REVERTIDA','S02'],
              [[t['numero'] for t in recuperado[0]['turnos']],recuperado[0]['estado'],recuperado[1]['id']])
    comprobar('JSON inicial sin sobrescritura',True,ruta.read_bytes()==inicial)
    comunes=leer_bnf((ROOT/'gramaticas/clausulas.bnf').read_text(encoding='utf-8'))
    texto=leer_bnf((ROOT/'gramaticas/texto.bnf').read_text(encoding='utf-8'))
    comprobar('BNF de cláusula coherente con la de texto',True,
              all(texto.get(nt)==rs for nt,rs in comunes.items()))
    # CLI completa, incluyendo validación y lectura real de stdin, fuera del cwd
    # de la entrega para comprobar rutas internas y no modificar casos originales.
    with tempfile.TemporaryDirectory(prefix='tp2_') as temporal:
        entrada=Path(temporal)/'entrada.txt'
        salida=Path(temporal)/'salida.json'
        entrada.write_text('SESION S01\n1 AGENTE: gestionaremos.\n2 AGENTE: gestionaremos.\nFIN\n',encoding='utf-8')
        comando=[sys.executable,'-B','-X','utf8',str(ROOT/'main.py'),str(entrada),'--salida',str(salida)]
        cli=subprocess.run(comando,input='TOKEN_INEXISTENTE\nSEGUIMIENTO\n',text=True,
                           encoding='utf-8',capture_output=True,cwd=temporal,timeout=30)
        comprobar('CLI interacción, validación de categoría y consulta única',
                  [0,1,True,'PENDIENTE'],
                  [cli.returncode,cli.stdout.count('Lexema sin clasificar:'),
                   'Ingrese uno de los tokens indicados.' in cli.stdout,
                   json.loads(salida.read_text(encoding='utf-8'))['sesiones'][0]['estado']])
        cli=subprocess.run(comando+['--no-interactivo'],input='',text=True,
                           encoding='utf-8',capture_output=True,cwd=temporal,timeout=30)
        comprobar('CLI reproducible sin preguntas', [0,False,'PARCIAL'],
                  [cli.returncode,'Lexema sin clasificar:' in cli.stdout,
                   json.loads(salida.read_text(encoding='utf-8'))['sesiones'][0]['analisis']])
        cli=subprocess.run(comando,input='',text=True,encoding='utf-8',capture_output=True,
                           cwd=temporal,timeout=30)
        comprobar('CLI EOF conserva desconocidos y termina', [0,'NO_CONFIRMADA'],
                  [cli.returncode,json.loads(salida.read_text(encoding='utf-8'))['sesiones'][0]['estado']])
    guardar('verificacion_requerimientos.json',pruebas)
    if not all(p['coincide'] for p in pruebas):
        raise SystemExit('FALLO: consultar resultados/verificacion_requerimientos.json')
    return len(pruebas)


def main():
    esperados=json.loads((ROOT/'casos/esperados.json').read_text(encoding='utf-8'))
    lote=analizar((ROOT/'casos/casos.txt').read_text(encoding='utf-8'))
    if len(lote['sesiones'])!=len(esperados):
        raise SystemExit('FALLO: cantidad de sesiones distinta de la esperada.')
    sesiones={s['id']:s for s in lote['sesiones']}
    resultados=[]
    for exp,s in zip(esperados,lote['sesiones']):
        obtenido=dict(id=s['id'],estado=s['estado'],analisis=s['analisis'],
                      resumen={a:v['valoracion'] for a,v in s['resumen_por_aspecto'].items()})
        esperado={k:exp[k] for k in obtenido}
        resultados.append(dict(id=exp['id'],esperado=esperado,obtenido=obtenido,
                               coincide=esperado==obtenido,explicacion=exp['explicacion']))
    controles={sid:{} for sid in sesiones}
    tokens,correcciones=lexear('no TR-204 RC-205 G. 250.000 123','S05',1)
    controles['S05']['no_referencias_cifras_y_montos_protegidos']=(
        not correcciones and [t.normalizado for t in tokens]==['no','TR-204','RC-205','250000','123'])
    controles['S05']['correccion_unica']=any(c['original']=='tranferencia' and c['accion']=='CORREGIDA'
        and c['resultado']=='transferencia' for c in sesiones['S05']['correcciones'])
    controles['S07']['rechaza_rol_y_continua']=(
        [t['numero'] for t in sesiones['S07']['turnos']]==[1,3] and
        any(e['codigo']=='ROL_INVALIDO' and e.get('rechazado') for e in sesiones['S07']['errores']) and
        sesiones['S08']['id']=='S08')
    controles['S08']['empate_sin_correccion']=any(c['original']=='pag' and c['accion']=='EMPATE'
        and c['resultado']=='pag' and c['candidatos']==['paga','pago'] for c in sesiones['S08']['correcciones'])
    referencias=[e for e in sesiones['S11']['entidades'] if e['tipo']=='REF']
    controles['S11']['referencia_repetida_unica']=(len(referencias)==1 and len(referencias[0]['apariciones'])==2)
    controles['S12']['fragmento_desconocido_sin_opinion_inventada']=(
        len(sesiones['S12']['evidencias'])==1 and bool(sesiones['S12']['turnos'][0]['no_interpretados']))
    for verbo in ('Envié','Me debitaron'):
        s=analizar(f'SESION S01\n1 CLIENTE: {verbo} G. 250000.\nFIN')['sesiones'][0]
        controles['S10']['regresion_'+verbo]=(s['estado']=='NO_CONFIRMADA' and
            s['resumen_cliente']['TRANSFERENCIA']['valoracion']=='NEUTRA')
    for p in (ROOT/'gramaticas').glob('*.bnf'):
        info=calcular(leer_bnf(p.read_text(encoding='utf-8')))
        if not info['es_ll1']: raise SystemExit('FALLO LL(1): '+p.name)
    for r in resultados:
        r['comprobaciones']=controles[r['id']]
        r['coincide']=r['coincide'] and all(r['comprobaciones'].values())
        print(r['id']+(': OK' if r['coincide'] else ': FALLO'))
    out=ROOT/'resultados';out.mkdir(exist_ok=True)
    guardar('salida.json',lote)
    guardar('comparacion.json',resultados)
    s=sesiones['S05']
    traza=['TRAZA S05: original -> tokens -> estructura -> simbolos -> semantica -> resultado']
    for t in s['turnos']:
        etapas={'ORIGINAL':t['texto'],'TOKENS':t['tokens'],'ESTRUCTURA Y DERIVACION':t['clausulas'],
                'TABLA LEXICA (JSON / CONSULTA / APRENDIZAJE)':t['tabla_lexica_operaciones'],
                'CONSULTA / INSERCION / ACTUALIZACION':t['tabla_operaciones'],
                'ACCION SEMANTICA':[e for e in s['evidencias'] if e['turno']==t['numero']],
                'RESULTADO':dict(valoraciones=t['valoraciones'],estado=s['estado'])}
        for nombre,valor in etapas.items():
            traza.extend(['',nombre,json.dumps(valor,ensure_ascii=False,indent=2)])
    (out/'traza_S05.txt').write_text('\n'.join(traza)+'\n',encoding='utf-8')
    cantidad_semantica=regresion_semantica(lote)
    cantidad_requerimientos=verificar_requerimientos()
    if not all(r['coincide'] for r in resultados): raise SystemExit(1)
    print(f'{len(resultados)}/{len(resultados)} casos coinciden. Regresion envio/debito: OK. '
          f'Regresion semantica: {cantidad_semantica}/{cantidad_semantica}. '
          f'Requerimientos: {cantidad_requerimientos}/{cantidad_requerimientos}. '
          'Contrato anterior del corpus sin cambios. BNF LL(1): OK.')


if __name__=='__main__': main()
