#!/usr/bin/env node
/**
 * elk_layout.js — ELK.js 布局引擎桥接
 *
 * 从 stdin 读取 JSON (ELK graph)，输出布局后的 JSON (含 x/y/width/height/bendPoints)。
 *
 * 用法:
 *   echo '{"id":"root",...}' | node elk_layout.js > layout.json
 */

const ELK = require('elkjs');
const elk = new ELK();

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const input = JSON.parse(Buffer.concat(chunks).toString('utf8'));

  const layout = await elk.layout(input);

  process.stdout.write(JSON.stringify(layout));
}

main().catch(err => {
  console.error('ELK layout error:', err.message);
  process.exit(1);
});
