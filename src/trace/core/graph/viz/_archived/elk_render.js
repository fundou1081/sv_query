#!/usr/bin/env node
/**
 * elk_render.js — ELK.js 布局 + elkjs-svg 渲染
 *
 * Python 端产出完整 ELK JSON → 本脚本做 layout + SVG 渲染。
 *
 * 用法:
 *   echo '{"id":"root",...}' | node elk_render.js > output.svg
 *
 * Python 端只需要生成 ELK JSON，不参与任何坐标计算或渲染。
 */

const elkjsSvg = require('elkjs-svg');

async function main() {
  // 从 stdin 读取 ELK JSON
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const graph = JSON.parse(Buffer.concat(chunks).toString('utf8'));

  // elkjs-svg.Renderer 自动做 layout + SVG 渲染
  const renderer = new elkjsSvg.Renderer();
  const result = await renderer.toSvg(graph);

  process.stdout.write(result);
}

main().catch(err => {
  console.error('ELK render error:', err.message);
  process.exit(1);
});
