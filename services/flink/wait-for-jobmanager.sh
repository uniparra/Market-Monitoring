#!/bin/sh

# Espera a que el JobManager esté listo
echo "Esperando a que Flink JobManager esté disponible en ${JOBMANAGER_ADDRESS}:8081..."

# Bucle hasta que el endpoint 'overview' de la API de Flink devuelva algo (y no un error)
until curl -s "http://${JOBMANAGER_ADDRESS}:8081/overview" | grep -q "flink-version"; do
  echo "JobManager no está listo... reintentando en 2 segundos."
  sleep 2
done

echo "¡JobManager listo! Enviando el trabajo (job)..."

# Una vez que el JobManager responde, ejecuta el comando original
flink run -c TechnicalProcessor -m ${JOBMANAGER_ADDRESS}:8081 /opt/app/job.jar