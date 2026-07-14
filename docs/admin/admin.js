// 猴子明細後台：照 twstock-wordcloud admin 的 PAT 模式，經 GitHub API 讀取 data/admin_monkeys.json
// （該檔在 repo 但不在 docs/、不上 Pages、公開頁無連結）。唯讀展示：預測中每週全 10 隻猴子個股，依個股績效排序。
const REPO = "w2xg2022/twstock-signal";
const DATA_PATH = "data/admin_monkeys.json";
const TOKEN_KEY = "twstock_signal_admin_token";

function log(msg) {
  const box = document.getElementById("log");
  box.textContent = `[${new Date().toLocaleTimeString()}] ${msg}\n` + box.textContent;
}

function getToken() {
  const input = document.getElementById("tok");
  const t = input.value.trim() || localStorage.getItem(TOKEN_KEY) || "";
  if (input.value.trim()) localStorage.setItem(TOKEN_KEY, input.value.trim());
  return t;
}

// GitHub contents API 回傳 base64(Latin1)，中文需先轉回 UTF-8
function base64ToUtf8(b64) {
  const bin = atob(b64.replace(/\n/g, ""));
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

async function ghGetJson(path) {
  const token = getToken();
  if (!token) throw new Error("請先貼上 GitHub Token");
  const res = await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`, {
    headers: { Authorization: `token ${token}`, Accept: "application/vnd.github+json" },
    cache: "no-store",
  });
  if (res.status === 401) throw new Error("Token 無效或已過期 (401)");
  if (res.status === 404) throw new Error(`找不到 ${path} (404)：Token 可能沒有本 repo 的讀取權限`);
  if (!res.ok) throw new Error(`讀取失敗 (${res.status})`);
  const data = await res.json();
  return JSON.parse(base64ToUtf8(data.content));
}

const f = (v) => (v == null ? "—" : `<span class="${v >= 0 ? "pos" : "neg"}">${v >= 0 ? "+" : ""}${v.toFixed(2)}%</span>`);

// 一週的全猴子個股表：stocks 已由後端依 rc(收盤報酬) 由高到低排好
function weekTable(g) {
  const rows = (g.stocks || []).map((s, i) => `
    <tr>
      <td>${i + 1}</td>
      <td class="l">${s.code}</td>
      <td class="l">${s.name}</td>
      <td>${s.market === "TWSE" ? "上市" : "上櫃"}</td>
      <td>#${s.monkey_id}</td>
      <td>${s.entry}</td>
      <td>${s.cur}<br><span class="hd">${s.exited ? "第" + s.hold + "天出" : "持有" + s.hold + "天"}</span></td>
      <td>${s.hi}</td>
      <td>${f(s.rc)}</td>
      <td>${f(s.rm)}</td>
    </tr>`).join("");
  return `<div class="grphead">入選日 ${g.date} ／ 進場日 ${g.entry_date}　<span class="d">距今 ${g.days} 交易日｜全 ${new Set((g.stocks || []).map(s => s.monkey_id)).size} 隻猴子共 ${(g.stocks || []).length} 檔</span></div>
    <div style="overflow-x:auto"><table>
    <thead><tr><th>績效<br>名次</th><th class="l">代號</th><th class="l">簡稱</th><th>市場</th><th>猴子</th><th>買入價</th><th>當前價</th><th>最高價</th><th>收盤%</th><th>最高%</th></tr></thead>
    <tbody>${rows || '<tr><td class="l" colspan="10">（本週無資料）</td></tr>'}</tbody></table></div>`;
}

let WEEKS = [];
function renderTab(i) {
  document.getElementById("body").innerHTML = weekTable(WEEKS[i]);
  document.querySelectorAll("#tabs .qbtn").forEach((b, k) => b.classList.toggle("active", k === i));
}

async function load() {
  try {
    log("讀取 admin_monkeys.json ...");
    const d = await ghGetJson(DATA_PATH);
    WEEKS = (d.weeks || []).slice().sort((a, b) => (a.date < b.date ? 1 : -1)); // 入選日新→舊
    const tabs = document.getElementById("tabs");
    if (!WEEKS.length) {
      tabs.innerHTML = ""; document.getElementById("body").innerHTML = '<p class="sub">目前沒有預測中的週次。</p>';
      log("載入完成，但沒有預測中週次"); return;
    }
    tabs.innerHTML = WEEKS.map((g, i) => `<button class="qbtn${i ? "" : " active"}" data-i="${i}">${g.date}</button>`).join("");
    tabs.querySelectorAll(".qbtn").forEach((b) => b.onclick = () => renderTab(+b.dataset.i));
    renderTab(0);
    log(`載入完成：${WEEKS.length} 個預測中週次（資料更新於 ${d.latest_date}）`);
  } catch (e) {
    log("錯誤：" + e.message);
    document.getElementById("body").innerHTML = `<p class="sub" style="color:#c62828">${e.message}</p>`;
  }
}

document.getElementById("loadbtn").addEventListener("click", load);

// 已存過 token 就自動載入
if (localStorage.getItem(TOKEN_KEY)) {
  document.getElementById("tok").value = localStorage.getItem(TOKEN_KEY);
  load();
}
