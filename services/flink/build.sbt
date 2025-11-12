name := "flink-rag-pipeline"
version := "0.1"
scalaVersion := "2.12.15"

val flinkVersion = "1.19.0"
val kafkaConnectorVersion = "3.2.0-1.19"

resolvers ++= Seq(
  "Apache Snapshots" at "https://repository.apache.org/content/repositories/snapshots/",
  "Confluent" at "https://packages.confluent.io/maven/",
  Resolver.mavenCentral
)


libraryDependencies ++= Seq(
  "org.apache.flink" %% "flink-scala" % "1.19.0" % "provided",
  "org.apache.flink" %% "flink-streaming-scala" % "1.19.0" % "provided",
  "org.apache.flink" % "flink-clients" % "1.19.0" % "provided",
  "org.apache.flink" % "flink-connector-kafka" % "3.2.0-1.19",
  "org.apache.flink" % "flink-connector-base" % "1.19.0" % "provided",
  "com.lihaoyi" %% "requests" % "0.8.0",
  "com.typesafe.play" %% "play-json" % "2.9.4"
)

mainClass in assembly := Some("TechnicalProcessor")

assembly / assemblyMergeStrategy := {
  case PathList("META-INF", "services", xs @ _*) => MergeStrategy.filterDistinctLines
  case PathList("reference.conf", xs @ _*)       => MergeStrategy.concat
  case PathList("application.conf", xs @ _*)     => MergeStrategy.concat

  // Excluir archivos de firma
  case PathList("META-INF", xs @ _*) if xs.contains("LICENSE") || xs.contains("NOTICE") => MergeStrategy.discard
  case PathList("META-INF", xs @ _*) if xs.endsWith(".SF") || xs.endsWith(".RSA") || xs.endsWith(".DSA") => MergeStrategy.discard
  case PathList("META-INF", "maven", xs @ _*)    => MergeStrategy.discard
  case "module-info.class"                       => MergeStrategy.discard
  case x => MergeStrategy.first
}