import boto3
import csv
from io import StringIO

def descargar_csv(bucket, key):
    s3_client = boto3.client('s3')
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response['Body'].read().decode('utf-8')
    except Exception as e:
        print(f"Error downloading CSV: {e}")
        raise

def extraer_columnas(csv_data):
    try:
        reader = csv.DictReader(StringIO(csv_data))
        return list(reader)
    except Exception as e:
        print(f"Error parsing CSV: {e}")
        raise

def buscar_datos(datos, columna, valor):
    try:
        return [fila for fila in datos if fila.get(columna) == valor]
    except Exception as e:
        print(f"Error searching data: {e}")
        raise

def imprimir_resultados(resultados):
    try:
        if resultados:
            for resultado in resultados:
                print({"run_id": resultado.get("run_id"), "total_attempts": resultado.get("total_attempts")})
        else:
            print("No se encontraron resultados")
    except Exception as e:
        print(f"Error printing results: {e}")
        raise

def main():
    try:
        bucket = "devops-figue-practice"
        key = "02_retry_classification.csv"

        csv_data = descargar_csv(bucket, key)
        datos = extraer_columnas(csv_data)
        resultados = buscar_datos(datos, "run_number", "12047")
        imprimir_resultados(resultados)
    except Exception as e:
        print(f"Fatal error in main: {e}")
        raise

if __name__ == "__main__":
    main()
