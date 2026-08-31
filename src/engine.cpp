/*
  Stockfish, a UCI chess playing engine derived from Glaurung 2.1
  Copyright (C) 2004-2026 The Stockfish developers (see AUTHORS file)

  Stockfish is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  Stockfish is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#include "engine.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <filesystem>
#include <deque>
#include <iosfwd>
#include <memory>
#include <ostream>
#include <sstream>
#include <string_view>
#include <utility>
#include <vector>

#include "evaluate.h"
#include "misc.h"
#include "movegen.h"
#include "nnue/network.h"
#include "nnue/nnue_common.h"
#include "numa.h"
#include "perft.h"
#include "position.h"
#include "search.h"
#include "shm.h"
#include "syzygy/tbprobe.h"
#include "types.h"
#include "uci.h"
#include "ucioption.h"

namespace Stockfish {

namespace NN = Eval::NNUE;

namespace {

constexpr Value antichess_claim_value(Value value, bool claimable) {
    return claimable ? std::max(VALUE_DRAW, value) : value;
}

static_assert(antichess_claim_value(-1, true) == VALUE_DRAW);
static_assert(antichess_claim_value(1, true) == 1);
static_assert(antichess_claim_value(-1, false) == -1);

}

int MaxThreads = 1;

// The default configuration will attempt to group L3 domains up to 32 threads.
// This size was found to be a good balance between the Elo gain of increased
// history sharing and the speed loss from more cross-cache accesses (see
// PR#6526). The user can always explicitly override this behavior.
constexpr NumaAutoPolicy DefaultNumaPolicy = BundledL3Policy{32};

Engine::Engine(std::optional<std::filesystem::path> path) :
    binaryDirectory(path ? CommandLine::get_binary_directory(*path) : std::filesystem::path{}),
    numaContext(NumaConfig::from_system(DefaultNumaPolicy)),
    states(new std::deque<StateInfo>(1)),
    threads(),
    networkFile{std::nullopt, ""},
    network(numaContext, get_default_network()) {

    pos.set(StartFEN, RuleProfile::LICHESS_ANTICHESS_V1, false, &states->back());

    options.add(  //
      "Debug Log File", Option("", [](const Option& o) {
          start_logger(path_from_utf8(std::string(o)));
          return std::nullopt;
      }));

    options.add(  //
      "NumaPolicy", Option("auto", [this](const Option& o) {
          if (!set_numa_config_from_option(o))
              return "NumaPolicy: invalid value '" + std::string(o) + "', keeping previous config.";
          return numa_config_information_as_string() + "\n"
               + thread_allocation_information_as_string();
      }));

    options.add(  //
      "Threads", Option(1, 1, 1, [this](const Option&) {
          resize_threads();
          return thread_allocation_information_as_string();
      }));

    options.add(  //
      "Hash", Option(1, 1, 1, [this](const Option& o) {
          set_tt_size(o);
          return std::nullopt;
      }));

    options.add(  //
      "Clear Hash", Option([this](const Option&) {
          search_clear();
          return std::nullopt;
      }));

    options.add("UCI_Variant", Option("antichess var antichess", "antichess"));

    options.add(
      "Antichess_Evaluator",
      Option("engineering-neutral var engineering-neutral var legacy-v1", "engineering-neutral"));

    options.add("Antichess_Search",
                Option("exhaustive-v1 var exhaustive-v1 var alpha-beta-v1", "exhaustive-v1"));

    options.add("EvalFile", Option("", [this](const Option& o) {
                    return load_legacy_network(path_from_utf8(std::string(o)));
                }));

    threads.clear();
    threads.ensure_network_replicated();
    resize_threads();
}

std::variant<u64, PositionSetError>
Engine::perft(const std::string& fen, Depth depth, bool isChess960) {
    return Benchmark::perft(fen, depth, isChess960);
}

void Engine::go(Search::LimitsType& limits) {
    assert(limits.perft == 0);

    if (pos.is_antichess())
    {
        if (updateContext.onStart)
            updateContext.onStart();

        const bool useLegacyNetwork = options["Antichess_Evaluator"] == "legacy-v1";
        const bool useAlphaBeta     = options["Antichess_Search"] == "alpha-beta-v1";
        if (useLegacyNetwork && !legacyNetwork.loaded())
        {
            if (onVerifyNetwork)
                onVerifyNetwork("Antichess legacy-v1 evaluator is not ready; search refused");
            if (updateContext.onBestmove)
                updateContext.onBestmove(UCIEngine::move(Move::none()), "");
            return;
        }

        const int depth = std::clamp(limits.depth ? limits.depth : 4, 1, 8);
        std::array<StateInfo, MAX_PLY + 1> searchStates;
        u64                                nodes = 0;

        const auto orderedMoves = [](const Position& position) {
            MoveList<LEGAL>   legal(position);
            std::vector<Move> moves(legal.begin(), legal.end());
            std::sort(moves.begin(), moves.end(), [](Move left, Move right) {
                return UCIEngine::move(left, false) < UCIEngine::move(right, false);
            });
            return moves;
        };

        std::function<Value(int, int, Value, Value)> search =
          [&](int remaining, int ply, Value alpha, Value beta) -> Value {
            ++nodes;

            if (pos.antichess_variant_end())
            {
                const int reportDistance = ply + (ply & 1);
                return mate_in(reportDistance);
            }

            if (pos.antichess_automatic_draw())
                return VALUE_DRAW;

            const bool claimable = pos.antichess_threefold();
            if (remaining == 0)
            {
                const Value leaf =
                  useLegacyNetwork ? legacyNetwork.evaluate(pos) : VALUE_DRAW;
                return antichess_claim_value(leaf, claimable);
            }

            Value best = claimable ? VALUE_DRAW : -VALUE_INFINITE;
            if (useAlphaBeta)
            {
                alpha = std::max(alpha, best);
                if (alpha >= beta)
                    return best;
            }

            for (Move move : orderedMoves(pos))
            {
                pos.do_move(move, searchStates[ply]);
                const Value score =
                  useAlphaBeta ? -search(remaining - 1, ply + 1, -beta, -alpha)
                               : -search(remaining - 1, ply + 1, -VALUE_INFINITE, VALUE_INFINITE);
                pos.undo_move(move);
                best = std::max(best, score);

                if (useAlphaBeta)
                {
                    alpha = std::max(alpha, best);
                    if (alpha >= beta)
                        break;
                }
            }
            return best;
        };

        std::vector<Move> rootMoves = orderedMoves(pos);
        if (!limits.searchmoves.empty())
            rootMoves.erase(std::remove_if(rootMoves.begin(), rootMoves.end(),
                                           [&](Move move) {
                                               const std::string uci = UCIEngine::move(move, false);
                                               return std::find(limits.searchmoves.begin(),
                                                                limits.searchmoves.end(), uci)
                                                   == limits.searchmoves.end();
                                           }),
                            rootMoves.end());

        if (rootMoves.empty())
        {
            if (updateContext.onUpdateNoMoves)
                updateContext.onUpdateNoMoves({0, Score(mate_in(0), pos)});
            if (updateContext.onBestmove)
                updateContext.onBestmove(UCIEngine::move(Move::none()), "");
            return;
        }

        if (pos.antichess_automatic_draw())
        {
            const std::string fallback = UCIEngine::move(rootMoves.front(), false);
            if (updateContext.onUpdateFull)
            {
                Search::InfoFull info{};
                info.depth    = 0;
                info.selDepth = 0;
                info.multiPV  = 1;
                info.score    = Score(VALUE_DRAW, pos);
                info.timeMs   = std::max<usize>(1, now() - limits.startTime);
                info.nodes    = 0;
                info.nps      = 0;
                info.pv       = fallback;
                info.hashfull = 0;
                updateContext.onUpdateFull(info);
            }
            if (updateContext.onBestmove)
                updateContext.onBestmove(fallback, "");
            return;
        }

        const bool claimable = pos.antichess_threefold();
        Value      bestScore = claimable ? VALUE_DRAW : -VALUE_INFINITE;
        Move       bestMove  = rootMoves.front();

        for (Move move : rootMoves)
        {
            pos.do_move(move, searchStates[0]);
            Value score = -search(depth - 1, 1, -VALUE_INFINITE, VALUE_INFINITE);
            pos.undo_move(move);
            if (score > bestScore || (score == bestScore && is_win(score)))
            {
                bestScore = score;
                bestMove  = move;
            }
        }

        std::string pv = UCIEngine::move(bestMove, false);
        if (updateContext.onUpdateFull)
        {
            Search::InfoFull info{};
            info.depth    = depth;
            info.selDepth = depth;
            info.multiPV  = 1;
            info.score    = Score(bestScore, pos);
            info.timeMs   = std::max<usize>(1, now() - limits.startTime);
            info.nodes    = nodes;
            info.nps      = 1000 * nodes / info.timeMs;
            info.pv       = pv;
            info.hashfull = 0;
            updateContext.onUpdateFull(info);
        }
        if (updateContext.onBestmove)
            updateContext.onBestmove(pv, "");
        return;
    }

    verify_network();

    threads.start_thinking(options, pos, states, limits);
}
void Engine::stop() { threads.stop = true; }

void Engine::search_clear() {
    wait_for_search_finished();

    tt.clear(threads);
    threads.clear();

    // TODO: does not work with multiple instances
    // The exact Antichess profile has no certified tablebase backend.
}

void Engine::set_on_update_no_moves(std::function<void(const Engine::InfoShort&)>&& f) {
    updateContext.onUpdateNoMoves = std::move(f);
}

void Engine::set_on_update_full(std::function<void(const Engine::InfoFull&)>&& f) {
    updateContext.onUpdateFull = std::move(f);
}

void Engine::set_on_iter(std::function<void(const Engine::InfoIter&)>&& f) {
    updateContext.onIter = std::move(f);
}

void Engine::set_on_bestmove(std::function<void(std::string_view, std::string_view)>&& f) {
    updateContext.onBestmove = std::move(f);
}

void Engine::set_on_start(std::function<void()>&& f) { updateContext.onStart = std::move(f); }

void Engine::set_on_verify_network(std::function<void(std::string_view)>&& f) {
    onVerifyNetwork = std::move(f);
}

void Engine::wait_for_search_finished() { threads.main_thread()->wait_for_search_finished(); }

std::optional<PositionSetError> Engine::set_position(const std::string&              fen,
                                                     const std::vector<std::string>& moves) {
    // Drop the old state and create a new one
    states   = StateListPtr(new std::deque<StateInfo>(1));
    auto err = pos.set(fen, RuleProfile::LICHESS_ANTICHESS_V1, false, &states->back());
    if (err.has_value())
        return err;

    for (const auto& move : moves)
    {
        auto m = UCIEngine::to_move(pos, move);

        if (m == Move::none())
            return PositionSetError("Illegal move: " + move);

        states->emplace_back();
        pos.do_move(m, states->back());
    }

    return std::nullopt;
}

std::string Engine::antichess_info() const {

    std::vector<std::string> moves;
    for (Move move : MoveList<LEGAL>(pos))
        moves.push_back(UCIEngine::move(move, false));
    std::sort(moves.begin(), moves.end());

    const bool variantEnd = pos.antichess_variant_end();
    const bool automatic  = pos.antichess_automatic_draw();

    std::ostringstream ss;
    ss << "antichess-info profile=LICHESS_ANTICHESS_V1"
       << "|fen=" << pos.fen() << "|legal=";
    for (usize i = 0; i < moves.size(); ++i)
        ss << (i ? "," : "") << moves[i];

    ss << "|end=" << (variantEnd || automatic) << "|variant_end=" << variantEnd
       << "|automatic_draw=" << automatic << "|threefold=" << pos.antichess_threefold()
       << "|fivefold=" << pos.antichess_fivefold() << "|status="
       << (variantEnd  ? "variant_end"
           : automatic ? "draw"
                       : "none")
       << "|winner=" << (variantEnd ? pos.side_to_move() == WHITE ? "white" : "black" : "none")
       << "|check=0"
       << "|player_insufficient=" << pos.antichess_player_has_insufficient_material()
       << "|opponent_insufficient=" << pos.antichess_opponent_has_insufficient_material()
       << "|halfmove_clock=" << pos.rule50_count()
       << "|uci_variant=" << options["UCI_Variant"].currentValue
       << "|evaluator=" << options["Antichess_Evaluator"].currentValue
       << "|search=" << options["Antichess_Search"].currentValue
       << "|threads=" << int(options["Threads"]) << "|hash_mb=" << int(options["Hash"])
       << "|network_loaded=" << legacyNetwork.loaded()
       << "|network_format=" << (legacyNetwork.loaded() ? "legacy-v1" : "none") << "|network_file="
       << (legacyNetwork.loaded() ? legacyNetwork.source_path().filename().u8string() : "none")
       << "|network_description_bytes="
       << (legacyNetwork.loaded() ? legacyNetwork.description().size() : 0);

    return ss.str();
}

// modifiers

bool Engine::set_numa_config_from_option(const std::string& o) {
    if (o == "auto" || o == "system")
    {
        numaContext.set_numa_config(NumaConfig::from_system(DefaultNumaPolicy));
    }
    else if (o == "hardware")
    {
        // Don't respect affinity set in the system.
        numaContext.set_numa_config(NumaConfig::from_system(DefaultNumaPolicy, false));
    }
    else if (o == "none")
    {
        numaContext.set_numa_config(NumaConfig{});
    }
    else
    {
        auto parsed = NumaConfig::from_string(o);
        if (!parsed.has_value())
            return false;
        numaContext.set_numa_config(std::move(*parsed));
    }

    // Force reallocation of threads in case affinities need to change.
    resize_threads();
    threads.ensure_network_replicated();
    return true;
}

void Engine::resize_threads() {
    threads.wait_for_search_finished();
    threads.set(numaContext.get_numa_config(), {options, threads, tt, sharedHists, network},
                updateContext);

    // Reallocate the hash with the new threadpool size
    set_tt_size(options["Hash"]);
    threads.ensure_network_replicated();
}

void Engine::set_tt_size(usize mb) {
    wait_for_search_finished();
    tt.resize(mb, threads);
}

void Engine::set_ponderhit(bool b) { threads.main_manager()->ponder = b; }

// network related

void Engine::verify_network() const {
    if (!onVerifyNetwork)
        return;

    if (options["Antichess_Evaluator"] == "legacy-v1")
        onVerifyNetwork(
          legacyNetwork.loaded()
            ? "Antichess evaluator: legacy-v1 network loaded"
            : "Antichess evaluator: legacy-v1 selected but no compatible network loaded");
    else
        onVerifyNetwork("Antichess evaluator: engineering-neutral");
}

std::optional<std::string> Engine::load_legacy_network(const std::filesystem::path& file) {

    if (file.empty())
    {
        legacyNetwork.clear();
        return "Antichess legacy network cleared";
    }

    auto result = legacyNetwork.load(file);
    if (!result.ok)
        legacyNetwork.clear();
    return result.message;
}

std::unique_ptr<Eval::NNUE::Network> Engine::get_default_network() {
    return std::make_unique<NN::Network>();
}

void Engine::load_network(const std::filesystem::path& file) {
    network.modify_and_replicate(
      [this, &file](NN::Network& network_) { network_.load(binaryDirectory, file, networkFile); });
    threads.clear();
    threads.ensure_network_replicated();
}

void Engine::save_network(const std::optional<std::filesystem::path>& file) {
    network.modify_and_replicate(
      [&file, this](NN::Network& network_) { network_.save(networkFile, file); });
}

// utility functions

void Engine::trace_eval() const {
    if (options["Antichess_Evaluator"] == "legacy-v1" && legacyNetwork.loaded())
        sync_cout << "info string Antichess legacy-v1 raw value "
                  << int(legacyNetwork.evaluate(pos)) << sync_endl;
    else if (options["Antichess_Evaluator"] == "legacy-v1")
        sync_cout << "info string Antichess legacy-v1 evaluator is not ready" << sync_endl;
    else
        sync_cout << "info string Antichess evaluator: engineering-neutral" << sync_endl;
}

const OptionsMap& Engine::get_options() const { return options; }
OptionsMap&       Engine::get_options() { return options; }

std::string Engine::fen() const { return pos.fen(); }

std::optional<PositionSetError> Engine::flip() { return pos.flip(); }

std::string Engine::visualize() const {
    std::stringstream ss;
    ss << pos;
    return ss.str();
}

int Engine::get_hashfull(int maxAge) const { return tt.hashfull(maxAge); }

std::vector<std::pair<usize, usize>> Engine::get_bound_thread_count_by_numa_node() const {
    auto                                 counts = threads.get_bound_thread_count_by_numa_node();
    const NumaConfig&                    cfg    = numaContext.get_numa_config();
    std::vector<std::pair<usize, usize>> ratios;
    NumaIndex                            n = 0;
    for (; n < counts.size(); ++n)
        ratios.emplace_back(counts[n], cfg.num_cpus_in_numa_node(n));
    if (!counts.empty())
        for (; n < cfg.num_numa_nodes(); ++n)
            ratios.emplace_back(0, cfg.num_cpus_in_numa_node(n));
    return ratios;
}

std::string Engine::get_numa_config_as_string() const {
    return numaContext.get_numa_config().to_string();
}

std::string Engine::numa_config_information_as_string() const {
    auto cfgStr = get_numa_config_as_string();
    return "Available processors: " + cfgStr;
}

std::string Engine::thread_binding_information_as_string() const {
    auto              boundThreadsByNode = get_bound_thread_count_by_numa_node();
    std::stringstream ss;
    if (boundThreadsByNode.empty())
        return ss.str();

    bool isFirst = true;

    for (auto&& [current, total] : boundThreadsByNode)
    {
        if (!isFirst)
            ss << ":";
        ss << current << "/" << total;
        isFirst = false;
    }

    return ss.str();
}

std::string Engine::thread_allocation_information_as_string() const {
    std::stringstream ss;

    usize threadsSize = threads.size();
    ss << "Using " << threadsSize << (threadsSize > 1 ? " threads" : " thread");

    auto boundThreadsByNodeStr = thread_binding_information_as_string();
    if (boundThreadsByNodeStr.empty())
        return ss.str();

    ss << " with NUMA node thread binding: ";
    ss << boundThreadsByNodeStr;

    return ss.str();
}
}
