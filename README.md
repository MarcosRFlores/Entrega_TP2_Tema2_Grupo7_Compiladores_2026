# TP2 · Diseño de Compiladores · Tema 2 · Grupo 7

Anahi Talavera y Marcos Flores · FPUNA · 2026/2.

Análisis de reclamos por transferencias no acreditadas. Python 3.10 o posterior; exclusivamente biblioteca estándar, sin instalar paquetes.

## Ejecutar

Abrir una terminal en esta carpeta. Para reproducir los casos sin preguntas:

```bash
python3 -B -X utf8 main.py casos/casos.txt --no-interactivo --salida resultados/salida.json
python3 -B -X utf8 verificar.py
python3 -B -X utf8 main.py casos/casos.txt --no-interactivo --salida resultados/salida.json --traza S05
```

En Linux y macOS se usa `python3`. En Windows se puede usar `py -3` o `python` en lugar de `python3`. Entrada y salida son relativas a la terminal; el diccionario, la tabla inicial y las BNF se resuelven respecto del código.

Para el modo interactivo:

```bash
python3 -B -X utf8 main.py mi_entrada.txt --salida resultados/mi_salida.json
```

Ante un lexema sin clasificación se muestran las categorías lingüísticas existentes y se solicita una. Enter o EOF conserva el desconocido. La elección agrega una relación léxica; el parser sigue exigiendo la BNF. No se crean tokens ni construcciones nuevas. El empate `pag` entre `paga/pago` se conserva sin corregir ni preguntar, conforme al PDF. Cifras, montos, referencias y referencias inválidas tampoco se reclasifican mediante preguntas.

## Vocabulario y símbolos

- `diccionario.json`: vocabulario canónico y sinónimos, independiente de las tablas.
- `tabla_lexica_inicial.json`: relación lexema → token definida manualmente y cargada al iniciar cada lote.
- `TablaLexica`, en `tabla_simbolos.py`: consulta y aprendizaje durante el lote. Incorpora lexemas reconocidos por patrones y clasificaciones del usuario; conserva contenido final y operaciones en el JSON de salida. No sobrescribe el JSON inicial ni persiste entre ejecuciones: los apuntes no lo exigen.
- `TablaSimbolos`: entidades por sesión (SESION, PARTICIPANTE, REF, MONTO) con ID y apariciones. Una referencia repetida conserva una sola entrada en su sesión.

El modo sin interacción mantiene la carga, consulta y enriquecimiento automático de la tabla; omite las preguntas.

## Lenguaje y límites

Sesiones `SESION Sxx` / `FIN`, sin líneas vacías; turnos consecutivos desde 1, rol CLIENTE o AGENTE, dos puntos y texto no vacío. Se admiten sesiones solo con CLIENTE. Montos `G. 250000` o `G. 250.000`; referencias TR-/RC- con 3 a 6 cifras. El vocabulario y las cuatro BNF delimitan las construcciones. Lo ajeno queda NO_INTERPRETADOS y la sesión pasa a PARCIAL.

El parser predictivo LL(1) utiliza una tabla M y una pila explícita. La evaluación semántica se realiza sobre las cláusulas aceptadas sin reparaciones. `NL` pertenece al formato externo; `$` indica el fin de entrada de cada parser.

Los estados son inferencias del diálogo. Enviar o debitar no acredita; solicitar reversión no confirma devolución. Las opiniones del agente conservan autoría; el estado efectivo requiere declaración del cliente. No se validan datos bancarios. La interacción no agrega producciones ni modifica reglas semánticas.

Limitación de esta versión: `S_ENVIO` no comprueba la compatibilidad monetaria del complemento; «Envié la explicación» y «Envié el reclamo» producen TRANSFERENCIA NEUTRA. Recepción, devolución y falta de llegada sí comprueban ese contexto.

## Pruebas y documentos

`verificar.py` comprueba 12 sesiones (8 guía y 4 propias), 14 controles semánticos, envío/débito, las cuatro BNF LL(1) y 26 controles adicionales de requerimientos. Regenera:

- `resultados/salida.json`: ejemplo del lote completo.
- `resultados/comparacion.json`: esperado, obtenido, explicación y controles por caso.
- `resultados/traza_S05.txt`: original → tokens → estructura → tablas → semántica → resultado.
- `resultados/verificacion_requerimientos.json`: controles adicionales y sus resultados.

`resultados/regresion_semantica.json` conserva las capturas históricas recibidas y actualiza la verificación actual. Se compara el contrato completo de la salida original excluyendo únicamente los nuevos campos léxicos y el número de versión; el JSON nuevo contiene más datos y no es idéntico byte a byte al anterior.

[INFORME_TP2_Flores_Talavera.pdf](INFORME_TP2_Flores_Talavera.pdf) contiene el informe técnico final, con las tablas M ajustadas a las BNF ejecutables, las reglas semánticas, las pruebas, la declaración de uso de IA y las contribuciones de los integrantes. [ANEXO_TECNICO_LL1.pdf](ANEXO_TECNICO_LL1.pdf) presenta el resumen de las cuatro BNF y los conjuntos PRIMERO, SIGUIENTE y la tabla M de `texto.bnf`, con el mismo estilo del informe. 

Se utilizó Codex, de OpenAI, para generar el código y asistir en la revisión, la documentación y las verificaciones. El análisis de las sesiones se ejecuta mediante algoritmos deterministas, sin consultas a IA ni a servicios externos.
