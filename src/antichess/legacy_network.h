/*
  Antichess-Stockfish, a Stockfish derivative for Lichess Antichess
  Copyright (C) 2026 The Antichess-Stockfish contributors

  Antichess-Stockfish is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

#ifndef ANTICHESS_LEGACY_NETWORK_H_INCLUDED
#define ANTICHESS_LEGACY_NETWORK_H_INCLUDED

#include <array>
#include <cstdint>
#include <filesystem>
#include <iosfwd>
#include <string>
#include <vector>

#include "../types.h"

namespace Stockfish {

class Position;

namespace Antichess {

class LegacyNetwork {
   public:
    struct LoadResult {
        bool        ok;
        std::string message;
    };

    LoadResult load(const std::filesystem::path& path);
    void       clear();

    bool                         loaded() const;
    Value                        evaluate(const Position& pos) const;
    const std::filesystem::path& source_path() const;
    const std::string&           description() const;

   private:
    static constexpr usize FeatureDimensions     = 768;
    static constexpr usize TransformerDimensions = 512;
    static constexpr usize LayerStacks           = 8;

    struct LayerStack {
        std::array<std::int32_t, 16>       l1Biases{};
        std::array<std::int8_t, 16 * 1024> l1Weights{};
        std::array<std::int32_t, 32>       l2Biases{};
        std::array<std::int8_t, 32 * 32>   l2Weights{};
        std::array<std::int32_t, 1>        outputBias{};
        std::array<std::int8_t, 32>        outputWeights{};
    };

    bool read(std::istream& stream, usize fileSize, std::string& error);

    std::filesystem::path sourcePath;
    std::string           networkDescription;

    std::array<std::int16_t, TransformerDimensions> transformerBiases{};
    std::vector<std::int16_t>                       transformerWeights;
    std::vector<std::int32_t>                       psqtWeights;
    std::array<LayerStack, LayerStacks>             layers{};
};

}  // namespace Antichess
}  // namespace Stockfish

#endif  // ANTICHESS_LEGACY_NETWORK_H_INCLUDED
