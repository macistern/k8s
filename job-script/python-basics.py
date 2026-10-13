import argparse
import csv
from pathlib import Path


def cargar_csv(csv_path):
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        columnas_requeridas = {"run_number", "run_id", "total_attempts"}
        columnas_faltantes = columnas_requeridas - set(reader.fieldnames or [])
        if columnas_faltantes:
            raise ValueError(
                f"Faltan columnas requeridas en {csv_path}: "
                f"{', '.join(sorted(columnas_faltantes))}"
            )
        return list(reader)


def buscar_datos(datos, columna, valor):
    return [fila for fila in datos if fila.get(columna) == valor]


def imprimir_resultados(resultados):
    if resultados:
        for resultado in resultados:
            print(
                {
                    "run_id": resultado.get("run_id"),
                    "total_attempts": resultado.get("total_attempts"),
                }
            )
    else:
        print("No se encontraron resultados")


def main():
    parser = argparse.ArgumentParser(
        description="Busca un run_number en un CSV local."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).with_name("02_retry_classification.csv"),
        help="Ruta al CSV (por defecto: 02_retry_classification.csv junto al script).",
    )
    parser.add_argument("--run-number", default="12047", help="Run number a buscar.")
    args = parser.parse_args()

    datos = cargar_csv(args.csv)
    resultados = buscar_datos(datos, "run_number", args.run_number)
    imprimir_resultados(resultados)


if __name__ == "__main__":
    main()
