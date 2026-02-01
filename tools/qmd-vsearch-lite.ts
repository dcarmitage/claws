#!/usr/bin/env bun
// Lightweight vector search - uses only the 300M embedding model, no query expansion
// Usage: bun qmd-vsearch-lite.ts <query> [-n count] [-c collection]

import { Database } from "bun:sqlite";
import { existsSync } from "fs";
import { homedir } from "os";
import { join } from "path";

const QMD_DIR = "/home/clawd/tools/qmd";

// Parse args
const args = process.argv.slice(2);
let query = "";
let limit = 5;
let collection: string | undefined;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "-n" && args[i + 1]) { limit = parseInt(args[i + 1]); i++; }
  else if (args[i] === "-c" && args[i + 1]) { collection = args[i + 1]; i++; }
  else if (!query) { query = args[i]; }
}

if (!query) {
  console.error("Usage: bun qmd-vsearch-lite.ts <query> [-n count] [-c collection]");
  process.exit(1);
}

// Step 1: Find the QMD database
const dbPath = join(homedir(), ".cache", "qmd", "index.sqlite");
if (!existsSync(dbPath)) {
  console.error("QMD index not found. Run 'qmd collection add' first.");
  process.exit(1);
}

// Step 2: Load QMD's modules for embedding
process.chdir(QMD_DIR);
const { getDefaultLlamaCpp, formatQueryForEmbedding } = await import(join(QMD_DIR, "src", "llm.ts"));

const llm = getDefaultLlamaCpp();

// Step 3: Embed the query using the formatted query string (only loads 300M model)
const startTime = Date.now();
const formattedQuery = formatQueryForEmbedding(query);
const result = await llm.embed(formattedQuery, { model: "embeddinggemma", isQuery: true });

if (!result || !result.embedding || result.embedding.length === 0) {
  console.error("Failed to generate embedding for query");
  process.exit(1);
}
const embedding = result.embedding;

const embedTime = Date.now() - startTime;

// Step 4: Query sqlite-vec directly
// Load sqlite-vec extension
const db = new Database(dbPath, { readonly: true });

// Load sqlite-vec extension
try {
  const vecSoPath = join(QMD_DIR, "node_modules", "sqlite-vec-linux-arm64", "vec0");
  db.loadExtension(vecSoPath);
} catch (e: any) {
  console.error("Failed to load sqlite-vec:", e.message);
  process.exit(1);
}

// Vector search
const vecResults = db.prepare(`
  SELECT hash_seq, distance
  FROM vectors_vec
  WHERE embedding MATCH ? AND k = ?
`).all(new Float32Array(embedding), limit * 3) as { hash_seq: string; distance: number }[];

if (vecResults.length === 0) {
  console.log("No results found.");
  process.exit(0);
}

// Get document info
const hashSeqs = vecResults.map(r => r.hash_seq);
const distanceMap = new Map(vecResults.map(r => [r.hash_seq, r.distance]));
const placeholders = hashSeqs.map(() => "?").join(",");

let sql = `
  SELECT
    cv.hash || '_' || cv.seq as hash_seq,
    cv.hash,
    cv.pos,
    'qmd://' || d.collection || '/' || d.path as filepath,
    d.title,
    content.doc as body
  FROM content_vectors cv
  JOIN documents d ON d.hash = cv.hash AND d.active = 1
  JOIN content ON content.hash = d.hash
  WHERE cv.hash || '_' || cv.seq IN (${placeholders})
`;
const params: any[] = [...hashSeqs];

if (collection) {
  sql += ` AND d.collection = ?`;
  params.push(collection);
}

const docs = db.prepare(sql).all(...params) as any[];

// Score and deduplicate by file
const seen = new Set<string>();
const results: any[] = [];

for (const doc of docs) {
  const distance = distanceMap.get(doc.hash_seq) || 1;
  const score = 1 / (1 + distance);
  if (!seen.has(doc.filepath)) {
    seen.add(doc.filepath);
    results.push({ ...doc, score });
  }
}

// Sort by score descending
results.sort((a, b) => b.score - a.score);

// Format output (similar to QMD's format)
const queryTime = Date.now() - startTime;
const shown = results.slice(0, limit);

for (const r of shown) {
  const pct = Math.round(r.score * 100);
  const pos = r.pos || 1;
  console.log(`${r.filepath}:${pos} #${r.hash.slice(0, 6)}`);
  console.log(`Title: ${r.title}`);
  console.log(`Score: ${pct}%`);
  
  // Show snippet around the matched chunk position
  if (r.body) {
    const lines = r.body.split("\n");
    const start = Math.max(0, pos - 2);
    const end = Math.min(lines.length, pos + 3);
    console.log(`\n@@ -${pos},4 @@ (${start} before, ${lines.length - end} after)`);
    for (let i = start; i < end; i++) {
      console.log(lines[i]);
    }
  }
  console.log();
}

console.error(`\n(${shown.length} results in ${queryTime}ms, embed: ${embedTime}ms)`);
db.close();
