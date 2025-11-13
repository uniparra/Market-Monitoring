import org.apache.flink.api.common.eventtime.WatermarkStrategy
import org.apache.flink.api.common.serialization.SimpleStringSchema
import org.apache.flink.streaming.api.scala._
import org.apache.flink.connector.kafka.source.KafkaSource
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer
import org.apache.flink.connector.kafka.sink.KafkaSink
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema
import org.apache.flink.api.common.state._
import org.apache.flink.streaming.api.functions.KeyedProcessFunction
import org.apache.flink.util.Collector
import play.api.libs.json._

import scala.collection.JavaConverters._
import scala.util.{Failure, Success, Try}

case class OHLCV(datetime: String, open: Double, high: Double, low: Double, close: Double, volume: Long)
object OHLCV {
  implicit val reads: Reads[OHLCV] = new Reads[OHLCV] {
    def reads(js: JsValue): JsSuccess[OHLCV] = {
      val dt = (js \ "datetime").as[String]

      def d(key: String): Double = (js \ key).as[String].toDouble

      val vol = (js \ "volume").as[String].toLong
      JsSuccess(OHLCV(dt, d("open"), d("high"), d("low"), d("close"), vol))
    }
  }
}

case class Tick(symbol: String, datetime: String, open: Double, high: Double, low: Double, close: Double, volume: Long)
object Tick {
  implicit val writes: OWrites[Tick] = Json.writes[Tick]
}

case class SignalEvent(symbol: String, timestamp: String, eventType: String, details: String, currentPrice: Double, minPrice: Double, maxPrice: Double, sma20: Option[Double], sma50: Option[Double])
object SignalEvent {
  implicit val writes: OWrites[SignalEvent] = Json.writes[SignalEvent]
}

class TechnicalKeyedProcessor extends KeyedProcessFunction[String, Tick, String] {

  lazy val maxState: ValueState[Double] =
    getRuntimeContext.getState(new ValueStateDescriptor[Double]("maxPrice", classOf[Double]))
  lazy val minState: ValueState[Double] =
    getRuntimeContext.getState(new ValueStateDescriptor[Double]("minPrice", classOf[Double]))

  lazy val closesState: ListState[Double] =
    getRuntimeContext.getListState(new ListStateDescriptor[Double]("closes", classOf[Double]))

  lazy val sum20State: ValueState[Double] =
    getRuntimeContext.getState(new ValueStateDescriptor[Double]("sum20", classOf[Double]))
  lazy val sum50State: ValueState[Double] =
    getRuntimeContext.getState(new ValueStateDescriptor[Double]("sum50", classOf[Double]))

  lazy val prevSma20State: ValueState[Double] =
    getRuntimeContext.getState(new ValueStateDescriptor[Double]("prevSma20", classOf[Double]))
  lazy val prevSma50State: ValueState[Double] =
    getRuntimeContext.getState(new ValueStateDescriptor[Double]("prevSma50", classOf[Double]))

  override def processElement(value: Tick,
                              ctx: KeyedProcessFunction[String, Tick, String]#Context,
                              out: Collector[String]): Unit = {

    val symbol = value.symbol
    val currentMax = Option(maxState.value()).filterNot(_.isNaN).getOrElse(Double.MinValue)
    val currentMin = Option(minState.value()).filterNot(_.isNaN).getOrElse(Double.MaxValue)
    var updated = false

    if (value.high > currentMax) {
      maxState.update(value.high)
      updated = true
    }
    if (value.low < currentMin) {
      minState.update(value.low)
      updated = true
    }

    val closesIter = Option(closesState.get()).map(_.iterator().asScala.toList).getOrElse(Nil)
    val closes = scala.collection.mutable.Queue[Double]()
    closes ++= closesIter
    closes.enqueue(value.close)

    while (closes.size > 50) closes.dequeue()

    closesState.update(closes.asJava)

    val sum20 = closes.takeRight(20).sum
    val sum50 = closes.sum

    sum20State.update(sum20)
    sum50State.update(sum50)

    val sma20Opt = if (closes.size >= 20) Some(sum20 / 20.0) else None
    val sma50Opt = if (closes.size >= 50) Some(sum50 / 50.0) else None

    val prevSma20 = Option(prevSma20State.value()).filterNot(_.isNaN)
    val prevSma50 = Option(prevSma50State.value()).filterNot(_.isNaN)

    sma20Opt.foreach(s => prevSma20State.update(s))
    sma50Opt.foreach(s => prevSma50State.update(s))

    val crossed = (prevSma20, prevSma50, sma20Opt, sma50Opt) match {
      case (Some(p20), Some(p50), Some(s20), Some(s50)) =>
        if (p20 <= p50 && s20 > s50) Some("golden_cross")
        else if (p20 >= p50 && s20 < s50) Some("death_cross")
        else None
      case _ => None
    }

    val volSpike = sma20Opt match {
      case Some(s20) =>
        val dev = math.abs(value.close - s20) / s20
        if (dev >= 0.02) Some(("volatility_spike", dev)) else None
      case _ => None
    }

    if (updated) {
      val ev = SignalEvent(
        symbol = symbol,
        timestamp = value.datetime.replace(" ", "T") + "Z",
        eventType = "new_min_or_max",
        details = s"newMin=${minState.value()}, newMax=${maxState.value()}",
        currentPrice = value.close,
        minPrice = minState.value(),
        maxPrice = maxState.value(),
        sma20 = sma20Opt,
        sma50 = sma50Opt
      )
      out.collect(Json.toJson(ev).toString())
    }

    crossed.foreach { c =>
      val ev = SignalEvent(
        symbol = symbol,
        timestamp = value.datetime.replace(" ", "T") + "Z",
        eventType = c,
        details = s"cross detected: $c",
        currentPrice = value.close,
        minPrice = minState.value(),
        maxPrice = maxState.value(),
        sma20 = sma20Opt,
        sma50 = sma50Opt
      )
      out.collect(Json.toJson(ev).toString())
    }

    volSpike.foreach { case (label, dev) =>
      val ev = SignalEvent(
        symbol = symbol,
        timestamp = value.datetime.replace(" ", "T") + "Z",
        eventType = label,
        details = f"dev=${dev}%.4f",
        currentPrice = value.close,
        minPrice = minState.value(),
        maxPrice = maxState.value(),
        sma20 = sma20Opt,
        sma50 = sma50Opt
      )
      out.collect(Json.toJson(ev).toString())
    }
  }
}

object TechnicalProcessor {
  def main(args: Array[String]): Unit = {
    val env = StreamExecutionEnvironment.getExecutionEnvironment
    env.setParallelism(1)

    val source = KafkaSource.builder[String]()
      .setBootstrapServers(sys.env.getOrElse("KAFKA_BOOTSTRAP_SERVER", "localhost:9092"))
      .setTopics("raw_market_data_technical")
      .setGroupId("technical-processor")
      .setStartingOffsets(OffsetsInitializer.earliest())
      .setValueOnlyDeserializer(new SimpleStringSchema())
      .build()

    val raw = env.fromSource(source, WatermarkStrategy.noWatermarks(), "KafkaTechnicalSource")

    val ticks: DataStream[Tick] = raw.flatMap { msg =>
      Try(Json.parse(msg)) match {
        case Success(js) =>
          val symbol = (js \ "meta" \ "symbol").asOpt[String].getOrElse("UNKNOWN")
          val values = (js \ "values").asOpt[JsArray].map(_.value).getOrElse(Seq.empty)
          values.flatMap { v =>
            Try(v.as[OHLCV]) match {
              case Success(o) =>
                Some(Tick(symbol, o.datetime, o.open, o.high, o.low, o.close, o.volume))
              case Failure(_) => None
            }
          }
        case Failure(_) => Seq.empty
      }
    }

    val processed = ticks
      .keyBy(_.symbol)
      .process(new TechnicalKeyedProcessor)

    val kafkaSink = KafkaSink.builder[String]()
      .setBootstrapServers(sys.env.getOrElse("KAFKA_BOOTSTRAP_SERVER", "localhost:9092"))
      .setRecordSerializer(
        KafkaRecordSerializationSchema.builder[String]()
          .setTopic("processed_market_signals")
          .setValueSerializationSchema(new SimpleStringSchema())
          .build()
      ).build()

    processed.sinkTo(kafkaSink)

    env.execute("Technical Processor - MinMax & Signals")
  }
}
