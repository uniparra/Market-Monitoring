FROM flink:1.19-scala_2.12

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app

COPY target/scala-2.12/flink-rag-pipeline-assembly-0.1.jar /opt/app/job.jar

COPY wait-for-jobmanager.sh /opt/app/wait-for-jobmanager.sh
RUN chmod +x /opt/app/wait-for-jobmanager.sh

CMD ["/opt/app/wait-for-jobmanager.sh"]