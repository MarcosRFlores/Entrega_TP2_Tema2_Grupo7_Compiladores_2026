import argparse
import json
from pathlib import Path
from analizador.core import analizar


def consultar_token(lexema, categorias):
    print(f"Lexema sin clasificar: {lexema!r}.")
    print("Tokens del lenguaje: " + ", ".join(categorias))
    while True:
        try:
            respuesta = input("Token correspondiente (Enter para NO_INTERPRETADOS): ").strip().upper()
        except EOFError:
            return None
        if not respuesta:
            return None
        if respuesta in categorias:
            return respuesta
        print("Ingrese uno de los tokens indicados.")


def main():
    p = argparse.ArgumentParser(description="Analizador determinista de reclamos (UTF-8)")
    p.add_argument("entrada", type=Path)
    p.add_argument("--salida", type=Path, default=Path("salida.json"))
    p.add_argument("--traza", help="ID de sesión cuya traza se imprimirá")
    p.add_argument("--no-interactivo", action="store_true",
                   help="No consultar lexemas desconocidos; conservar NO_INTERPRETADOS")
    args = p.parse_args()
    try:
        lote = analizar(args.entrada.read_text(encoding="utf-8-sig"),
                        consultar=None if args.no_interactivo else consultar_token)
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(json.dumps(lote, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        p.exit(2, f"Error de archivo: {exc}\n")
    for s in lote["sesiones"]:
        print(f'{s["id"]}: {s["analisis"]} | {s["estado"]}')
        print("  " + " | ".join(f'{a}: {v["valoracion"]}' for a, v in s["resumen_por_aspecto"].items()))
        print(f'  Errores: {len(s["errores"])}; correcciones/empates: {len(s["correcciones"])}')
        for t in s["turnos"]:
            print(f'  Turno {t["numero"]} ({t["rol"]}): ' + ", ".join(
                f'{a}={v["valoracion"]}' for a, v in t["valoraciones"].items()))
            for ni in t["no_interpretados"]:
                print(f'    NO_INTERPRETADOS: {ni["texto"]}')
        if args.traza == s["id"]:
            print("  TRAZA: original -> tokens -> estructura -> tabla -> semántica -> resultado")
            for t in s["turnos"]:
                print(json.dumps(dict(original=t["texto"], tokens=t["tokens"],
                    estructura=t["clausulas"], tabla=t["tabla_operaciones"],
                    tabla_lexica=t["tabla_lexica_operaciones"],
                    acciones=[e for e in s["evidencias"] if e["turno"] == t["numero"]],
                    resultado=t["valoraciones"]), ensure_ascii=False, indent=2))
    for e in lote["errores"]:
        print(f'Error de lote: {e}')
    print(f"JSON: {args.salida}")


if __name__ == "__main__":
    main()
