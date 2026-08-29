package antichess.reference

import chess.*
import chess.format.{ Fen, FullFen, Uci }
import chess.variant.Antichess
import java.nio.charset.StandardCharsets
import java.util.Base64

/** Deterministic probe for the exact scalachess revision in AUTHORITY.lock.json.
  *
  * This source is compiled against an external, pinned scalachess checkout. It
  * is not linked to the candidate engine and does not import candidate output.
  */
object ScalachessProbe:

  private def field(value: Any): String =
    value.toString.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")

  private def render(position: Position, canonicalFen: String): Unit =
    val values = List(
      "canonical_fen" -> canonicalFen,
      "legal_moves" -> position.legalMoves.map(_.toUci.uci).sorted.mkString(","),
      "legal_san" -> position.legalMoves
        .map(move => s"${move.toUci.uci}=${move.toSanStr.value}")
        .sorted
        .mkString(","),
      "end" -> position.end,
      "auto_draw" -> position.autoDraw,
      "threefold" -> position.history.threefoldRepetition,
      "fivefold" -> position.history.fivefoldRepetition,
      "variant_end" -> position.variantEnd,
      "status" -> position.status.fold("-")(_.toString),
      "winner" -> position.winner.fold("-")(_.toString),
      "check" -> position.check.toString,
      "player_insufficient" -> position.playerHasInsufficientMaterial,
      "opponent_insufficient" -> position.opponentHasInsufficientMaterial,
      "halfmove_clock" -> position.history.halfMoveClock.value,
      "ep_square" -> position.enPassantSquare.fold("-")(_.key)
    )
    println(values.map((key, value) => s"$key\t${field(value)}").mkString("\n"))

  private def fromFen(fen: String): Unit =
    Fen.readWithMoveNumber(Antichess, FullFen(fen)) match
      case Some(parsed) => render(parsed.position, Fen.write(parsed).value)
      case None =>
        System.err.println("FEN_REJECTED")
        sys.exit(2)

  private def fromMoves(initialFen: Option[String], moves: List[String]): Unit =
    val initial = initialFen match
      case None => Right(Game(Antichess))
      case Some(fen) =>
        Fen
          .readWithMoveNumber(Antichess, FullFen(fen))
          .toRight("FEN_REJECTED")
          .map(_.toGame)
    val played = moves.foldLeft[Either[String, Game]](initial):
      case (Right(game), uciText) =>
        Uci.Move(uciText)
          .toRight(s"INVALID_UCI:$uciText")
          .flatMap(uci => game(uci).left.map(_.toString).map(_._1))
      case (failure, _) => failure
    played match
      case Right(game) => render(game.position, Fen.write(game).value)
      case Left(error) =>
        System.err.println(error)
        sys.exit(3)

  def main(args: Array[String]): Unit =
    args.toList match
      case "--fen" :: fen :: Nil => fromFen(fen)
      case "--fen64" :: encoded :: Nil =>
        fromFen(String(Base64.getDecoder.decode(encoded), StandardCharsets.UTF_8))
      case "--fens64" :: encodedFens =>
        println("batch_kind\tpositions")
        encodedFens.zipWithIndex.foreach: (encoded, index) =>
          println(s"fixture_index\t$index")
          fromFen(String(Base64.getDecoder.decode(encoded), StandardCharsets.UTF_8))
          println("fixture_end\ttrue")
      case "--plays64" :: encodedCases =>
        println("batch_kind\thistories")
        encodedCases.zipWithIndex.foreach: (encoded, index) =>
          val lines = String(Base64.getDecoder.decode(encoded), StandardCharsets.UTF_8).split("\n").toList
          println(s"fixture_index\t$index")
          lines match
            case fen :: moves => fromMoves(Some(fen), moves.filter(_.nonEmpty))
            case Nil =>
              System.err.println("EMPTY_PLAY_CASE")
              sys.exit(65)
          println("fixture_end\ttrue")
      case "--moves" :: moves => fromMoves(None, moves)
      case "--play64" :: encoded :: moves =>
        fromMoves(Some(String(Base64.getDecoder.decode(encoded), StandardCharsets.UTF_8)), moves)
      case _ =>
        System.err.println("usage: ScalachessProbe --fen64 <base64-fen> | --fens64 <base64-fen>... | --moves <uci>... | --play64 <base64-fen> <uci>... | --plays64 <base64-fen-and-moves>...")
        sys.exit(64)
