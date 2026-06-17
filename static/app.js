const state = {
  drugCache: new Map(),   // 한번 조회된 약물 정보 보관 (kd_code -> drug)
  searchResults: [],      // 현재 검색 결과
  totalCount: 0,          // 마스터 전체 약물 수
  existing: new Set(),    // 선택된 기존 약물 KD코드
  newCodes: new Set(),    // 선택된 신규 약물 KD코드
  externalResults: [],    // 외부 검색(e약은요) 결과
};

const $ = (id) => document.getElementById(id);


// ============================================================
// 초기화
// ============================================================
async function loadInitial() {
  const [countRes, listRes] = await Promise.all([
    fetch("/api/drugs/count"),
    fetch("/api/drugs?limit=50"),
  ]);
  const countData = await countRes.json();
  const listData  = await listRes.json();

  state.totalCount = countData.total;
  $("cnt-master").textContent = `(${state.totalCount.toLocaleString()}건)`;

  applySearchResults(listData);
}


function applySearchResults(data) {
  state.searchResults = data.drugs;
  data.drugs.forEach(d => state.drugCache.set(d.kd_code, d));
  renderResults(data);
}


// ============================================================
// 검색
// ============================================================
let searchTimer = null;
function scheduleSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(doSearch, 300);
}


async function doSearch() {
  const q = $("search").value.trim();
  const url = q
    ? `/api/drugs?q=${encodeURIComponent(q)}&limit=50`
    : `/api/drugs?limit=50`;
  const res = await fetch(url);
  const data = await res.json();
  applySearchResults(data);
}


function renderResults(data) {
  const list = $("drug-list");
  if (data.drugs.length === 0) {
    list.innerHTML = `<p class="text-slate-400 text-sm text-center py-8">검색 결과 없음.<br>"🌐 식약처에서 검색"으로 외부에서 찾아보세요.</p>`;
    return;
  }

  const hint = data.total > data.drugs.length
    ? `<p class="text-xs text-slate-400 px-2 py-1">전체 ${data.total.toLocaleString()}건 중 ${data.drugs.length}건 표시 — 검색어를 더 입력하세요</p>`
    : "";

  list.innerHTML = hint + data.drugs.map(d => {
    const tag = d.category === "warning"
      ? `<span class="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded ml-1">주의:${d.risk_keyword}</span>`
      : `<span class="text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded ml-1">${d.indication || "기타"}</span>`;
    const subInfo = [];
    if (d.english_name)    subInfo.push(`<span class="text-slate-500">${d.english_name}</span>`);
    if (d.ingredient_code) subInfo.push(`<code class="text-slate-400">${d.ingredient_code}</code>`);
    return `
      <div class="flex items-center justify-between p-2 hover:bg-slate-50 rounded">
        <div class="flex-1 min-w-0">
          <span class="font-medium">${d.short_name}</span>
          ${tag}
          ${subInfo.length ? `<div class="text-xs mt-0.5">${subInfo.join(" · ")}</div>` : ""}
        </div>
        <div class="flex gap-1 shrink-0">
          <button onclick="addDrug('${d.kd_code}', 'existing')"
                  class="text-xs bg-slate-200 hover:bg-slate-300 px-2 py-1 rounded">+ 기존</button>
          <button onclick="addDrug('${d.kd_code}', 'new')"
                  class="text-xs bg-amber-200 hover:bg-amber-300 px-2 py-1 rounded">+ 신규</button>
        </div>
      </div>
    `;
  }).join("");
}


// ============================================================
// 약물 선택
// ============================================================
function addDrug(code, target) {
  if (target === "existing") {
    state.newCodes.delete(code);
    state.existing.add(code);
  } else {
    state.existing.delete(code);
    state.newCodes.add(code);
  }
  renderSelected();
  schedulePreview();
}


function removeDrug(code, target) {
  if (target === "existing") state.existing.delete(code);
  else state.newCodes.delete(code);
  renderSelected();
  schedulePreview();
}


function renderSelected() {
  const render = (set, target) => {
    if (set.size === 0) return '<li class="text-xs text-slate-400 p-1">없음</li>';
    return [...set].map(code => {
      const d = state.drugCache.get(code);
      if (!d) return `<li class="text-xs text-slate-400 p-1">${code}</li>`;
      const tag = d.category === "warning"
        ? `<span class="text-xs text-red-600">⚠ ${d.risk_keyword}</span>`
        : `<span class="text-xs text-slate-500">${d.indication}</span>`;
      return `
        <li class="flex items-center justify-between p-1 hover:bg-white rounded">
          <span class="truncate min-w-0">${d.short_name} ${tag}</span>
          <button onclick="removeDrug('${code}', '${target}')"
                  class="text-red-500 hover:text-red-700 font-bold shrink-0">✕</button>
        </li>
      `;
    }).join("");
  };

  $("existing-list").innerHTML = render(state.existing, "existing");
  $("new-list").innerHTML      = render(state.newCodes, "new");
  $("cnt-existing").textContent = `(${state.existing.size})`;
  $("cnt-new").textContent      = `(${state.newCodes.size})`;
}


// ============================================================
// 미리보기 & QR
// ============================================================
let previewTimer = null;
function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(updatePreview, 250);
}


async function updatePreview() {
  const total = state.existing.size + state.newCodes.size;
  if (total === 0) {
    $("preview").textContent = "약물을 추가하면 자동으로 미리보기가 표시됩니다.";
    $("length-counter").textContent = "0 / 200자";
    $("length-counter").className = "text-sm font-semibold text-slate-500";
    $("error-box").classList.add("hidden");
    $("btn-qr").disabled = true;
    return;
  }

  const body = { existing: [...state.existing], new: [...state.newCodes] };
  const res = await fetch("/api/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();

  if (res.ok) {
    $("preview").textContent = data.text;
    $("length-counter").textContent = `${data.length} / 200자`;
    $("length-counter").className = data.length > 180
      ? "text-sm font-semibold text-orange-600"
      : "text-sm font-semibold text-emerald-600";
    $("error-box").classList.add("hidden");
    $("btn-qr").disabled = false;
  } else if (res.status === 422) {
    const detail = data.detail;
    $("preview").textContent = detail.preview || "";
    $("length-counter").textContent = `${detail.length} / 200자 (초과)`;
    $("length-counter").className = "text-sm font-semibold text-red-600";
    $("error-box").classList.remove("hidden");
    $("error-box").textContent = detail.message;
    $("btn-qr").disabled = true;
  } else {
    $("preview").textContent = "(오류) " + (data.detail || res.statusText);
    $("btn-qr").disabled = true;
  }
}


async function generateQR() {
  const body = { existing: [...state.existing], new: [...state.newCodes] };
  const res = await fetch("/api/generate-qr", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json();
    alert("QR 생성 실패: " + (err.detail?.message || err.detail || res.statusText));
    return;
  }
  const data = await res.json();
  const src = `data:image/png;base64,${data.qr_base64}`;
  $("qr-image").src = src;
  $("qr-download").href = src;
  $("qr-path").textContent = data.file_path;
  $("qr-section").classList.remove("hidden");
  $("qr-section").scrollIntoView({ behavior: "smooth" });
}


function clearAll() {
  state.existing.clear();
  state.newCodes.clear();
  renderSelected();
  updatePreview();
  $("qr-section").classList.add("hidden");
}


// ============================================================
// 외부 검색 (식약처 e약은요)
// ============================================================
function openExternalModal() {
  const q = $("search").value.trim();
  if (q) $("external-query").value = q;
  $("external-modal").classList.remove("hidden");
  $("external-query").focus();
  if (q) searchExternal();
}


function closeExternalModal() {
  $("external-modal").classList.add("hidden");
}


async function searchExternal() {
  const q = $("external-query").value.trim();
  const box = $("external-results");
  if (!q) {
    box.innerHTML = '<p class="text-slate-400 text-sm text-center py-8">검색어를 입력하세요.</p>';
    return;
  }
  box.innerHTML = '<p class="text-slate-400 text-sm text-center py-8">⏳ 식약처 API 호출 중...</p>';

  const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
  if (!res.ok) {
    const err = await res.json();
    box.innerHTML = `<p class="text-red-600 text-sm py-4">❌ ${err.detail || res.statusText}</p>`;
    return;
  }
  const data = await res.json();

  if (data.count === 0) {
    box.innerHTML = `<p class="text-slate-400 text-sm py-4">'${q}' 검색 결과 없음.</p>`;
    return;
  }

  box.innerHTML = data.results.map((d, i) => `
    <div class="border rounded p-4 hover:border-indigo-300">
      <div class="flex justify-between items-start mb-2">
        <div>
          <h4 class="font-semibold text-slate-800">${d.name}</h4>
          <p class="text-xs text-slate-500">${d.company}</p>
        </div>
      </div>
      ${d.efficacy ? `<details class="mt-2 text-sm"><summary class="cursor-pointer text-blue-600">▸ 효능</summary><p class="mt-1 text-slate-700 whitespace-pre-wrap">${d.efficacy}</p></details>` : ""}
      ${d.caution ? `<details class="mt-2 text-sm"><summary class="cursor-pointer text-red-600">▸ 주의사항</summary><p class="mt-1 text-slate-700 whitespace-pre-wrap">${d.caution}</p></details>` : ""}
      ${d.interaction ? `<details class="mt-2 text-sm"><summary class="cursor-pointer text-amber-600">▸ 상호작용</summary><p class="mt-1 text-slate-700 whitespace-pre-wrap">${d.interaction}</p></details>` : ""}
      ${d.side_effect ? `<details class="mt-2 text-sm"><summary class="cursor-pointer text-orange-600">▸ 부작용</summary><p class="mt-1 text-slate-700 whitespace-pre-wrap">${d.side_effect}</p></details>` : ""}
      <div class="mt-3 border-t pt-3 bg-slate-50 -mx-4 -mb-4 px-4 pb-4 rounded-b">
        <p class="text-xs text-slate-600 mb-2">💾 마스터 DB에 추가:</p>
        <div class="grid grid-cols-12 gap-2 text-sm">
          <select id="cat-${i}" onchange="toggleKeywordField(${i})" class="col-span-3 border rounded px-2 py-1">
            <option value="normal">일반</option>
            <option value="warning">주의</option>
          </select>
          <input id="kw-${i}" type="text" placeholder="적응증 (예: 고혈압)"
                 class="col-span-6 border rounded px-2 py-1" />
          <button onclick="addToMaster(${i}, '${escapeQuote(d.name)}')"
                  class="col-span-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded">+ 추가</button>
        </div>
      </div>
    </div>
  `).join("");

  state.externalResults = data.results;
}


function escapeQuote(s) {
  return (s || "").replace(/'/g, "\\'");
}


function toggleKeywordField(i) {
  const cat = $(`cat-${i}`).value;
  const kw = $(`kw-${i}`);
  kw.placeholder = cat === "warning" ? "위험 키워드 (예: 출혈)" : "적응증 (예: 고혈압)";
}


async function addToMaster(i, name) {
  const category = $(`cat-${i}`).value;
  const keyword  = $(`kw-${i}`).value.trim();
  if (!keyword) {
    alert(category === "warning" ? "위험 키워드를 입력하세요." : "적응증을 입력하세요.");
    return;
  }
  const result = state.externalResults[i];

  const body = {
    short_name:   name,
    full_name:    result.name,
    category,
    risk_keyword: category === "warning" ? keyword : null,
    indication:   category === "normal"  ? keyword : null,
  };

  const res = await fetch("/api/cache-drug", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json();
    alert("DB 추가 실패: " + (err.detail || res.statusText));
    return;
  }

  const newDrug = await res.json();
  state.drugCache.set(newDrug.kd_code, newDrug);
  state.totalCount += 1;
  $("cnt-master").textContent = `(${state.totalCount.toLocaleString()}건)`;
  alert(`✅ '${name}' 추가 완료 (마스터 ${state.totalCount.toLocaleString()}건)`);
}


// ============================================================
// 초기화
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  loadInitial();
  $("search").addEventListener("input", scheduleSearch);
  $("btn-qr").addEventListener("click", generateQR);
  $("btn-clear").addEventListener("click", clearAll);
  $("btn-search-external").addEventListener("click", openExternalModal);
  $("external-modal").addEventListener("click", (e) => {
    if (e.target.id === "external-modal") closeExternalModal();
  });
  $("external-query").addEventListener("keydown", (e) => {
    if (e.key === "Enter") searchExternal();
  });
});
