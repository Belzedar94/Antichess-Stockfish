/*
  Antichess-Stockfish, a Stockfish derivative for Lichess Antichess
  Copyright (C) 2026 The Antichess-Stockfish contributors

  Antichess-Stockfish is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

#include "legacy_network.h"

#include <algorithm>
#include <cstring>
#include <fstream>
#include <limits>
#include <memory>
#include <type_traits>

#include "../bitboard.h"
#include "../position.h"

namespace Stockfish::Antichess {
namespace {

constexpr std::uint32_t FileVersion             = 0x7AF32F20u;
constexpr std::uint32_t ArchitectureHash        = 0x3C103E72u;
constexpr std::uint32_t TransformerHash         = 0x5F2348B8u;
constexpr std::uint32_t LayerStackHash          = 0x633376CAu;
constexpr usize         FixedPayloadBytes       = 953168;
constexpr usize         MaximumDescriptionBytes = 4096;
constexpr int           OutputScale             = 16;
constexpr int           WeightScaleBits         = 6;

template<typename T>
bool read_little_endian(std::istream& stream, T* output, usize count) {

    static_assert(std::is_integral_v<T>);
    using Unsigned = std::make_unsigned_t<T>;

    std::vector<unsigned char> bytes(count * sizeof(T));
    stream.read(reinterpret_cast<char*>(bytes.data()), std::streamsize(bytes.size()));
    if (!stream)
        return false;

    for (usize i = 0; i < count; ++i)
    {
        Unsigned value = 0;
        for (usize byte = 0; byte < sizeof(T); ++byte)
            value |= Unsigned(bytes[i * sizeof(T) + byte]) << (8 * byte);
        std::memcpy(&output[i], &value, sizeof(T));
    }

    return true;
}

template<typename T>
bool read_little_endian(std::istream& stream, T& output) {
    return read_little_endian(stream, &output, 1);
}

int feature_index(Color perspective, Square square, Piece piece) {

    const int pieceTypeIndex = int(type_of(piece)) - int(PAWN);
    assert(pieceTypeIndex >= 0 && pieceTypeIndex < 6);

    const int relativeColor = color_of(piece) == perspective ? 0 : 1;
    return (2 * pieceTypeIndex + relativeColor) * 64 + int(relative_square(perspective, square));
}

std::uint8_t clipped_relu(std::int32_t value) {
    if (value <= 0)
        return 0;
    return std::uint8_t(std::min<std::int32_t>(127, value >> WeightScaleBits));
}

}  // namespace

LegacyNetwork::LoadResult LegacyNetwork::load(const std::filesystem::path& path) {

    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream)
        return {false, "Unable to open Antichess legacy network: " + path.u8string()};

    const std::streampos end = stream.tellg();
    if (end < 0 || std::uintmax_t(end) > std::numeric_limits<usize>::max())
        return {false, "Unable to determine Antichess legacy network size"};

    const usize fileSize = usize(end);
    stream.seekg(0);

    auto        candidate = std::make_unique<LegacyNetwork>();
    std::string error;
    if (!candidate->read(stream, fileSize, error))
        return {false, std::move(error)};

    candidate->sourcePath = path;
    *this                 = std::move(*candidate);
    return {true, "Loaded Antichess legacy-v1 network: " + path.u8string()};
}

void LegacyNetwork::clear() {
    sourcePath.clear();
    networkDescription.clear();
    transformerWeights.clear();
    psqtWeights.clear();
}

bool LegacyNetwork::loaded() const {
    return transformerWeights.size() == FeatureDimensions * TransformerDimensions
        && psqtWeights.size() == FeatureDimensions * LayerStacks;
}

const std::filesystem::path& LegacyNetwork::source_path() const { return sourcePath; }

const std::string& LegacyNetwork::description() const { return networkDescription; }

bool LegacyNetwork::read(std::istream& stream, usize fileSize, std::string& error) {

    std::uint32_t version, architecture, descriptionSize;
    if (!read_little_endian(stream, version) || !read_little_endian(stream, architecture)
        || !read_little_endian(stream, descriptionSize))
    {
        error = "Truncated Antichess legacy network header";
        return false;
    }

    if (version != FileVersion)
    {
        error = "Unsupported Antichess legacy network version";
        return false;
    }
    if (architecture != ArchitectureHash)
    {
        error = "Incompatible Antichess legacy network architecture";
        return false;
    }
    if (descriptionSize > MaximumDescriptionBytes
        || fileSize != FixedPayloadBytes + usize(descriptionSize))
    {
        error = "Invalid Antichess legacy network framing";
        return false;
    }

    networkDescription.resize(descriptionSize);
    stream.read(networkDescription.data(), std::streamsize(descriptionSize));
    if (!stream)
    {
        error = "Truncated Antichess legacy network description";
        return false;
    }

    std::uint32_t transformerHash;
    if (!read_little_endian(stream, transformerHash) || transformerHash != TransformerHash)
    {
        error = "Incompatible Antichess legacy feature transformer";
        return false;
    }

    transformerWeights.resize(FeatureDimensions * TransformerDimensions);
    psqtWeights.resize(FeatureDimensions * LayerStacks);
    if (!read_little_endian(stream, transformerBiases.data(), transformerBiases.size())
        || !read_little_endian(stream, transformerWeights.data(), transformerWeights.size())
        || !read_little_endian(stream, psqtWeights.data(), psqtWeights.size()))
    {
        error = "Truncated Antichess legacy feature transformer";
        return false;
    }

    for (LayerStack& layer : layers)
    {
        std::uint32_t layerHash;
        if (!read_little_endian(stream, layerHash) || layerHash != LayerStackHash)
        {
            error = "Incompatible Antichess legacy layer stack";
            return false;
        }

        if (!read_little_endian(stream, layer.l1Biases.data(), layer.l1Biases.size())
            || !read_little_endian(stream, layer.l1Weights.data(), layer.l1Weights.size())
            || !read_little_endian(stream, layer.l2Biases.data(), layer.l2Biases.size())
            || !read_little_endian(stream, layer.l2Weights.data(), layer.l2Weights.size())
            || !read_little_endian(stream, layer.outputBias.data(), layer.outputBias.size())
            || !read_little_endian(stream, layer.outputWeights.data(), layer.outputWeights.size()))
        {
            error = "Truncated Antichess legacy layer stack";
            return false;
        }
    }

    if (stream.peek() != std::istream::traits_type::eof())
    {
        error = "Trailing bytes in Antichess legacy network";
        return false;
    }

    return true;
}

Value LegacyNetwork::evaluate(const Position& pos) const {

    assert(loaded());
    assert(pos.is_antichess());

    const int pieceCount = popcount(pos.pieces());
    const int bucket =
      pieceCount ? std::min((pieceCount - 1) * int(LayerStacks) / 32, int(LayerStacks) - 1) : 0;

    std::array<std::uint8_t, 2 * TransformerDimensions> transformed{};
    std::array<std::int32_t, 2>                         psqt{};

    for (int p = 0; p < 2; ++p)
    {
        const Color perspective = p == 0 ? pos.side_to_move() : ~pos.side_to_move();
        std::array<std::int32_t, TransformerDimensions> accumulator;
        std::copy(transformerBiases.begin(), transformerBiases.end(), accumulator.begin());

        Bitboard occupied = pos.pieces();
        while (occupied)
        {
            const Square square  = pop_lsb(occupied);
            const int    feature = feature_index(perspective, square, pos.piece_on(square));
            assert(feature >= 0 && feature < int(FeatureDimensions));

            const usize transformerOffset = usize(feature) * TransformerDimensions;
            for (usize i = 0; i < TransformerDimensions; ++i)
                accumulator[i] += transformerWeights[transformerOffset + i];
            psqt[p] += psqtWeights[usize(feature) * LayerStacks + usize(bucket)];
        }

        for (usize i = 0; i < TransformerDimensions; ++i)
            transformed[usize(p) * TransformerDimensions + i] =
              std::uint8_t(std::clamp<std::int32_t>(accumulator[i], 0, 127));
    }

    const LayerStack& layer = layers[usize(bucket)];

    std::array<std::uint8_t, 16> l1{};
    for (usize output = 0; output < l1.size(); ++output)
    {
        std::int32_t sum    = layer.l1Biases[output];
        const usize  offset = output * transformed.size();
        for (usize input = 0; input < transformed.size(); ++input)
            sum += std::int32_t(layer.l1Weights[offset + input]) * transformed[input];
        l1[output] = clipped_relu(sum);
    }

    std::array<std::uint8_t, 32> l2{};
    for (usize output = 0; output < l2.size(); ++output)
    {
        std::int32_t sum    = layer.l2Biases[output];
        const usize  offset = output * 32;
        for (usize input = 0; input < l1.size(); ++input)
            sum += std::int32_t(layer.l2Weights[offset + input]) * l1[input];
        l2[output] = clipped_relu(sum);
    }

    std::int32_t positional = layer.outputBias[0];
    for (usize input = 0; input < l2.size(); ++input)
        positional += std::int32_t(layer.outputWeights[input]) * l2[input];

    const std::int32_t material = (psqt[0] - psqt[1]) / 2;
    return Value((material + positional) / OutputScale);
}

}  // namespace Stockfish::Antichess
