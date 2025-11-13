FROM eclipse-temurin:17-jdk as builder

RUN apt-get update && \
    apt-get install -y curl gnupg && \
    echo "deb https://repo.scala-sbt.org/scalasbt/debian all main" | tee /etc/apt/sources.list.d/sbt.list && \
    echo "deb https://repo.scala-sbt.org/scalasbt/debian /" | tee /etc/apt/sources.list.d/sbt_old.list && \
    curl -sL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x2EE0EA64E40A89B84B2DF73499E82A75642AC823" | apt-key add && \
    apt-get update && \
    apt-get install -y sbt=1.9.7 && \
    rm -rf /var/lib/apt/lists/*

RUN java -version && sbt --version

WORKDIR /build

COPY build.sbt .
COPY project ./project

RUN sbt update

COPY . .

RUN sbt clean assembly

FROM flink:1.19-scala_2.12

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app

COPY --from=builder /build/target/scala-2.12/*-assembly-*.jar /opt/app/job.jar

COPY wait-for-jobmanager.sh /opt/app/wait-for-jobmanager.sh
RUN chmod +x /opt/app/wait-for-jobmanager.sh

CMD ["/opt/app/wait-for-jobmanager.sh"]