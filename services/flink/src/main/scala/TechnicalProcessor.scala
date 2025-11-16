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
import scala.collection.immutable.Queue
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


    def updateMinMax(currentMin: Double, currentMax: Double, high: Double, low: Double): (Double, Double, Boolean) = {
      if (high > currentMax) (currentMin, high, true)
      else if (low < currentMin) (low, currentMax, true)
      else (currentMin, currentMax, false)
    }

    def trimQueue(queue: Queue[Double], maxSize: Int = 50): Queue[Double] =
      if (queue.size > maxSize) queue.drop(queue.size - maxSize) else queue

    def calculateSMA(queue: Queue[Double], n: Int): Option[Double] =
      if (queue.size >= n) Some(queue.takeRight(n).sum / n) else None

    def detectCross(prev20: Option[Double], prev50: Option[Double], sma20: Option[Double], sma50: Option[Double]): Option[String] =
      (prev20, prev50, sma20, sma50) match {
        case (Some(p20), Some(p50), Some(s20), Some(s50)) =>
          if (p20 <= p50 && s20 > s50) Some("golden_cross")
          else if (p20 >= p50 && s20 < s50) Some("death_cross")
          else None
        case _ => None
      }

    def detectVolSpike(close: Double, sma20: Option[Double]): Option[(String, Double)] =
      sma20.flatMap { s20 =>
        val dev = math.abs(close - s20) / s20
        if (dev >= 0.02) Some(("volatility_spike", dev)) else None
      }

    def makeEvent(eventType: String,
                  details: String,
                  value: Tick,
                  minPrice: Double,
                  maxPrice: Double,
                  sma20: Option[Double],
                  sma50: Option[Double]): SignalEvent =
      SignalEvent(
        symbol = value.symbol,
        timestamp = value.datetime.replace(" ", "T") + "Z",
        eventType = eventType,
        details = details,
        currentPrice = value.close,
        minPrice = minPrice,
        maxPrice = maxPrice,
        sma20 = sma20,
        sma50 = sma50
      )


    val currentMax: Double = Option(maxState.value()).filterNot(_.isNaN).getOrElse(Double.MinValue)
    val currentMin: Double = Option(minState.value()).filterNot(_.isNaN).getOrElse(Double.MaxValue)
    val prevSma20: Option[Double] = Option(prevSma20State.value()).filterNot(_.isNaN)
    val prevSma50: Option[Double] = Option(prevSma50State.value()).filterNot(_.isNaN)
    val closesIter: List[Double] = Option(closesState.get()).map(_.iterator().asScala.toList).getOrElse(Nil)
    val closesQueue: Queue[Double] = Queue(closesIter: _*).enqueue(value.close)
    val trimmedQueue: Queue[Double] = trimQueue(closesQueue)


    val (newMin, newMax, updated) = updateMinMax(currentMin, currentMax, value.high, value.low)
    val sum20 = trimmedQueue.takeRight(20).sum
    val sum50 = trimmedQueue.sum
    val sma20Opt = calculateSMA(trimmedQueue, 20)
    val sma50Opt = calculateSMA(trimmedQueue, 50)
    val crossOpt = detectCross(prevSma20, prevSma50, sma20Opt, sma50Opt)
    val volSpikeOpt = detectVolSpike(value.close, sma20Opt)


    maxState.update(newMax)
    minState.update(newMin)
    sum20State.update(sum20)
    sum50State.update(sum50)
    sma20Opt.foreach(prevSma20State.update)
    sma50Opt.foreach(prevSma50State.update)
    closesState.update(trimmedQueue.asJava)


    if (updated) {
      val ev = makeEvent("new_min_or_max", s"newMin=$newMin, newMax=$newMax", value, newMin, newMax, sma20Opt, sma50Opt)
      out.collect(Json.toJson(ev).toString())
    }

    crossOpt.foreach { c =>
      val ev = makeEvent(c, s"cross detected: $c", value, newMin, newMax, sma20Opt, sma50Opt)
      out.collect(Json.toJson(ev).toString())
    }

    volSpikeOpt.foreach { case (label, dev) =>
      val ev = makeEvent(label, f"dev=$dev%.4f", value, newMin, newMax, sma20Opt, sma50Opt)
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
