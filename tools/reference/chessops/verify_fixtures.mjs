#!/usr/bin/env node

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const EXPECTED_CHESSOPS_COMMIT = '736c40ced7130d453d85e7979c360b797474c9a7';
const PROMOTION_ROLES = ['queen', 'rook', 'bishop', 'knight', 'king'];

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const values = new Map();
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    const value = argv[i + 1];
    if (!key?.startsWith('--') || value === undefined) fail(`invalid argument near ${key ?? '<end>'}`);
    values.set(key, value);
  }
  const chessopsRoot = values.get('--chessops-root');
  const fixtures = values.get('--fixtures');
  if (!chessopsRoot || !fixtures || values.size !== 2) {
    fail('usage: verify_fixtures.mjs --chessops-root <pinned-checkout> --fixtures <core-v1.json>');
  }
  return { chessopsRoot: resolve(chessopsRoot), fixtures: resolve(fixtures) };
}

function assertEqual(actual, expected, context) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    fail(`${context}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function outcomeWinner(outcome) {
  return outcome?.winner ?? null;
}

const { chessopsRoot, fixtures: fixturePath } = parseArgs(process.argv.slice(2));
const checkoutCommit = execFileSync('git', ['-C', chessopsRoot, 'rev-parse', 'HEAD'], {
  encoding: 'utf8',
}).trim();
assertEqual(checkoutCommit, EXPECTED_CHESSOPS_COMMIT, 'chessops checkout identity');

const dist = resolve(chessopsRoot, 'dist', 'esm');
const { parseFen, makeFen } = await import(pathToFileURL(resolve(dist, 'fen.js')));
const { setupPosition } = await import(pathToFileURL(resolve(dist, 'variant.js')));
const { makeUci, parseUci } = await import(pathToFileURL(resolve(dist, 'util.js')));
const fixtureDocument = JSON.parse(readFileSync(fixturePath, 'utf8'));

function load(fen) {
  const setup = parseFen(fen).unwrap();
  return setupPosition('antichess', setup).unwrap();
}

function legalMoves(position) {
  const context = position.ctx();
  const result = [];
  for (const from of position.board[position.turn]) {
    const role = position.board.getRole(from);
    for (const to of position.dests(from, context)) {
      const promotes = role === 'pawn' && (to < 8 || to >= 56);
      if (promotes) {
        for (const promotion of PROMOTION_ROLES) result.push(makeUci({ from, to, promotion }));
      } else {
        result.push(makeUci({ from, to }));
      }
    }
  }
  return result.sort();
}

function verifyCommon(position, expected, id) {
  assertEqual(makeFen(position.toSetup()), expected.canonical_fen, `${id} canonical FEN`);
  assertEqual(legalMoves(position), expected.legal_moves, `${id} complete legal moves`);
  assertEqual(position.isCheck(), expected.check, `${id} check state`);
}

let positionChecks = 0;
for (const fixture of fixtureDocument.position_fixtures) {
  const position = load(fixture.fen);
  const expected = fixture.expected;
  verifyCommon(position, expected, fixture.id);

  const context = position.ctx();
  const outcome = position.variantOutcome(context);
  if (expected.variant_end) {
    assertEqual(outcomeWinner(outcome), expected.winner, `${fixture.id} variant outcome winner`);
  } else if (expected.status !== 'draw') {
    assertEqual(outcome ?? null, null, `${fixture.id} unexpected variant outcome`);
  }

  if (fixture.family !== 'fifty_move') {
    assertEqual(position.isEnd(context), expected.end, `${fixture.id} end state`);
  }
  if (fixture.family === 'insufficient_material') {
    assertEqual(position.isInsufficientMaterial(), expected.automatic_draw, `${fixture.id} automatic insufficient material`);
  }
  if (fixture.family === 'one_sided_cannot_win') {
    const other = position.turn === 'white' ? 'black' : 'white';
    assertEqual(position.hasInsufficientMaterial(position.turn), expected.player_insufficient, `${fixture.id} player insufficient`);
    assertEqual(position.hasInsufficientMaterial(other), expected.opponent_insufficient, `${fixture.id} opponent insufficient`);
  }
  positionChecks += 1;
}

let historyChecks = 0;
for (const fixture of fixtureDocument.history_fixtures) {
  const position = load(fixture.initial_fen);
  for (const text of fixture.moves) {
    const move = parseUci(text);
    if (!move || !position.isLegal(move)) fail(`${fixture.id}: illegal fixture move ${text}`);
    position.play(move);
  }
  verifyCommon(position, fixture.expected, fixture.id);
  if (fixture.family !== 'repetition') {
    const outcome = position.variantOutcome(position.ctx());
    assertEqual(outcomeWinner(outcome), fixture.expected.winner, `${fixture.id} transition winner`);
    assertEqual(position.isEnd(position.ctx()), fixture.expected.end, `${fixture.id} transition end state`);
  }
  historyChecks += 1;
}

let rejectionChecks = 0;
for (const fixture of fixtureDocument.move_rejection_fixtures) {
  const position = load(fixture.fen);
  const move = parseUci(fixture.move);
  if (!move) fail(`${fixture.id}: rejection fixture is not syntactically UCI`);
  assertEqual(position.isLegal(move), false, `${fixture.id} rejected move`);
  rejectionChecks += 1;
}

let parserChecks = 0;
for (const fixture of fixtureDocument.parser_fixtures) {
  let accepted = true;
  try {
    load(fixture.fen);
  } catch {
    accepted = false;
  }
  assertEqual(accepted, fixture.project_policy === 'accept', `${fixture.id} parser policy`);
  parserChecks += 1;
}

console.log(
  `chessops ${checkoutCommit}: verified ${positionChecks} positions, ${historyChecks} transitions, `
    + `${rejectionChecks} rejected moves, and ${parserChecks} parser boundary case(s)`,
);
