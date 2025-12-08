// ------------------------
// 1. i18n setup
// ------------------------

window.translations = {
  lt: window.FP_TRANSLATIONS_LT,
  en: window.FP_TRANSLATIONS_EN
};

let currentLang = "lt";

function t(key, vars = {}) {
  const dict = window.translations[currentLang] || {};
  let template = dict[key] || key;
  Object.keys(vars).forEach(k => {
    template = template.replace(`{${k}}`, vars[k]);
  });
  return template;
}

function applyLanguage(lang) {
  currentLang = lang;
  document.documentElement.lang = lang;

  // Text: data-i18n="key"
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    el.textContent = t(key);
  });

  // Attributes: data-i18n-attr="attr:key;attr2:key2"
  document.querySelectorAll("[data-i18n-attr]").forEach(el => {
    const spec = el.getAttribute("data-i18n-attr");
    if (!spec) return;
    spec.split(";").forEach(pair => {
      const trimmed = pair.trim();
      if (!trimmed) return;
      const [attr, key] = trimmed.split(":").map(s => s.trim());
      if (!attr || !key) return;
      const val = t(key);
      el.setAttribute(attr, val);
    });
  });

  const btnLT = document.getElementById("btnLangLT");
  const btnEN = document.getElementById("btnLangEN");
  if (btnLT && btnEN) {
    btnLT.classList.toggle("active", lang === "lt");
    btnEN.classList.toggle("active", lang === "en");
  }

  updatePeriodButtons();
  renderTables();
  initPopovers(); // IMPORTANT: reinit popovers after updating data-content
}

// ------------------------
// 2. Data loading
// ------------------------

let rawData = [];
let fundTypes = [];
let allManagers = [];
let selectedFundType = null;
let selectedManager = null;

function parseData(rows) {
  return rows.map(r => ({
    ...r,
    report_date: new Date(r.report_date),
    fund_type: r.fund_type,
    company_short: r.company_short,
    relative_change: r.relative_change != null ? Number(r.relative_change) : null,
    number_of_participants:
      r.number_of_participants != null ? Number(r.number_of_participants) : null,
    bik_pct: r.bik_pct != null ? Number(r.bik_pct) : null
  }));
}

function loadData() {
  return fetch("data/combined_results.json")
    .then(res => res.json())
    .then(data => {
      rawData = parseData(data);

      const ftSet = new Set();
      const mgrSet = new Set();
      rawData.forEach(row => {
        if (row.fund_type) ftSet.add(row.fund_type);
        if (row.company_short) mgrSet.add(row.company_short);
      });

      fundTypes = Array.from(ftSet).sort();
      allManagers = Array.from(mgrSet).sort();

      // defaults
      selectedFundType = fundTypes.length ? fundTypes[0] : null;
      selectedManager = allManagers.length ? allManagers[0] : null;
    });
}

// ------------------------
// 3. Helpers
// ------------------------

function getYtdRange(data) {
  const dates = data.map(r => r.report_date);
  const end = new Date(Math.max.apply(null, dates));
  const start = new Date(end.getFullYear(), 0, 1);
  return [start, end];
}

function getPreviousYearRange(data, months) {
  const dates = data.map(r => r.report_date);
  const end = new Date(Math.max.apply(null, dates));
  const base = new Date(end);
  base.setMonth(base.getMonth() - (months - 1));
  const candidates = data.filter(r => r.report_date > base).map(r => r.report_date);
  if (!candidates.length) return [null, null];
  const start = new Date(Math.min.apply(null, candidates));
  return [start, end];
}

function getRange(data, period) {
  if (!data.length) return [null, null];

  if (period === "YTD") return getYtdRange(data);
  if (period === "ALL") {
    const allDates = rawData.map(r => r.report_date);
    const min = new Date(Math.min.apply(null, allDates));
    const max = new Date(Math.max.apply(null, allDates));
    return [min, max];
  }
  if (/^\d+$/.test(period)) {
    const years = parseInt(period, 10);
    return getPreviousYearRange(data, years * 12);
  }
  return [null, null];
}

function geometricCumulativeGrowth(series) {
  const clean = series.filter(v => v != null && !Number.isNaN(v));
  if (!clean.length) return NaN;
  const results = clean.map(v => v / 100.0);
  const prod = results.reduce((acc, x) => acc * (1.0 + x), 1.0);
  return (prod - 1.0) * 100.0;
}

function annualisedYearlyReturn(series) {
  const clean = series.filter(v => v != null && !Number.isNaN(v));
  const quarters = clean.length;
  if (!quarters) return NaN;
  const years = quarters / 4.0;
  if (years <= 0) return NaN;

  const totalGrowthPct = geometricCumulativeGrowth(clean);
  const totalGrowth = totalGrowthPct / 100.0;
  const annualised = Math.pow(1.0 + totalGrowth, 1.0 / years) - 1.0;
  return annualised * 100.0;
}

function fmtSigned(val, decimals = 2, msgIfNaN = t("msg.fund_not_exist")) {
  if (val === null || Number.isNaN(val)) return msgIfNaN;
  const factor = Math.pow(10, decimals);
  const rounded = Math.round(val * factor) / factor;
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${rounded.toFixed(decimals)}`;
}

function formatDate(d) {
  if (!d) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// ------------------------
// 4. UI helpers
// ------------------------

function getSelectedFundType() {
  return selectedFundType;
}

function getSelectedManager() {
  return selectedManager;
}

function getSelectedPeriod() {
  const radios = document.querySelectorAll('input[name="period"]');
  for (const r of radios) {
    if (r.checked) return r.value;
  }
  return "YTD";
}

// Populate Bootstrap dropdowns
function initFilters() {
  const ftButtonLabel = document.getElementById("fundTypeButtonLabel");
  const ftMenu = document.getElementById("fundTypeMenu");
  const mgrButtonLabel = document.getElementById("fundManagerButtonLabel");
  const mgrMenu = document.getElementById("fundManagerMenu");

  // Fund types
  if (ftMenu && ftButtonLabel) {
    ftMenu.innerHTML = "";
    fundTypes.forEach(ft => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "dropdown-item";
      btn.textContent = ft;
      btn.setAttribute("data-fund-type", ft);
      ftMenu.appendChild(btn);
    });
    if (selectedFundType) {
      ftButtonLabel.textContent = selectedFundType;
    } else if (fundTypes.length) {
      selectedFundType = fundTypes[0];
      ftButtonLabel.textContent = selectedFundType;
    } else {
      ftButtonLabel.textContent = "–";
    }
  }

  // Managers (independent)
  if (mgrMenu && mgrButtonLabel) {
    mgrMenu.innerHTML = "";
    allManagers.forEach(c => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "dropdown-item";
      btn.textContent = c;
      btn.setAttribute("data-manager", c);
      mgrMenu.appendChild(btn);
    });
    if (selectedManager) {
      mgrButtonLabel.textContent = selectedManager;
    } else if (allManagers.length) {
      selectedManager = allManagers[0];
      mgrButtonLabel.textContent = selectedManager;
    } else {
      mgrButtonLabel.textContent = "–";
    }
  }

  updatePeriodButtons();
}

// dynamically enable/disable period buttons based on selected manager's history
function updatePeriodButtons() {
  const ft = getSelectedFundType();
  const mgr = getSelectedManager();
  const periodRadios = document.querySelectorAll('input[name="period"]');
  const periodLabels = document.querySelectorAll("#periodButtons .btn-period");

  if (!ft || !rawData.length) return;

  const fundData = rawData.filter(r => r.fund_type === ft);
  if (!fundData.length) return;

  let managerData = null;
  if (mgr) {
    managerData = fundData.filter(r => r.company_short === mgr);
  }
  if (!managerData || !managerData.length) {
    managerData = fundData;
  }

  const dates = managerData.map(r => r.report_date);
  const min = new Date(Math.min.apply(null, dates));
  const max = new Date(Math.max.apply(null, dates));
  const spanYears = (max - min) / (1000 * 60 * 60 * 24 * 365.25);
  const maxWholeYears = Math.floor(spanYears);
  const maxButtonYears = Math.min(maxWholeYears, 5);

  let currentPeriod = getSelectedPeriod();
  const validPeriods = new Set(["YTD", "ALL"]);

  periodRadios.forEach((radio, idx) => {
    const val = radio.value;
    const label = periodLabels[idx];

    if (/^\d+$/.test(val)) {
      const years = parseInt(val, 10);
      const enabled = years <= maxButtonYears;
      radio.disabled = !enabled;
      label.classList.toggle("disabled", !enabled);
      if (enabled) validPeriods.add(val);
    } else {
      // YTD & ALL always enabled
      radio.disabled = false;
      label.classList.remove("disabled");
    }
  });

  // If current period is no longer valid, fallback to YTD
  if (!validPeriods.has(currentPeriod)) {
    currentPeriod = "YTD";
    periodRadios.forEach((r, idx) => {
      const label = periodLabels[idx];
      r.checked = r.value === currentPeriod;
      label.classList.toggle("active", r.value === currentPeriod);
    });
  }
}

// ------------------------
// 5. Tables (with full-range "Veikė anksčiau" logic)
// ------------------------

function renderTables() {
  const ft = getSelectedFundType();
  const period = getSelectedPeriod();
  const mgr = getSelectedManager();

  const msgFundNotExist = t("msg.fund_not_exist");
  const msgNoData = t("msg.no_data_reported");

  if (!ft || !period) {
    ["growthTableBody", "avgTableBody", "extremesTableBody", "participantsTableBody", "bikTableBody"]
      .forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = "";
      });
    return;
  }

  const fundData = rawData.filter(r => r.fund_type === ft);
  if (!fundData.length) return;

  // coverage in years per company (over its whole available history)
  const coverageYears = {};
  const companies = Array.from(new Set(fundData.map(r => r.company_short))).sort();

  companies.forEach(c => {
    const rows = fundData.filter(r => r.company_short === c);
    const dates = rows.map(r => r.report_date);
    const min = new Date(Math.min.apply(null, dates));
    const max = new Date(Math.max.apply(null, dates));
    const days = (max - min) / (1000 * 60 * 60 * 24);
    coverageYears[c] = days / 365.25;
  });

  // requestedYears: how many full years we require a fund to cover
  let requestedYears = null;
  if (/^\d+$/.test(period)) {
    requestedYears = parseInt(period, 10);
  }

  let baseData;
  if (period === "ALL") {
    baseData = rawData;   // ignore fund type and manager
  } else {
    baseData = fundData;  // normal behavior
  }

  const [start, end] = getRange(baseData, period);
  const rangeData = fundData.filter(
    r => r.report_date >= start && r.report_date <= end
  );

  // For ALL, require full coverage of the ALL-range
  if (period === "ALL" && start && end) {
    const fullDays = (end - start) / (1000 * 60 * 60 * 24);
    const fullYears = fullDays / 365.25;
    requestedYears = fullYears;
  }

  const growthNumeric = [];
  const growthNoData = [];
  const avgNumeric = [];
  const avgNoData = [];
  const extremesNumeric = [];
  const extremesNoData = [];
  const participantsNumeric = [];
  const participantsNoData = [];
  const bikNumeric = [];
  const bikNoData = [];

  companies.forEach(c => {
    const grpRange = rangeData.filter(r => r.company_short === c);
    const covYears = coverageYears[c] || 0.0;

    let hasEnoughHistory = true;
    if (requestedYears !== null) {
      hasEnoughHistory = covYears + 1e-6 >= requestedYears;
    }

    if (!grpRange.length || !hasEnoughHistory) {
      // Fund does not cover the entire requested range
      growthNoData.push({ company_short: c, cumulative_growth: msgFundNotExist });
      avgNoData.push({ company_short: c, avg_yearly_return: msgFundNotExist });
      extremesNoData.push({
        company_short: c,
        worst_quarter: msgFundNotExist,
        best_quarter: msgFundNotExist
      });
      participantsNoData.push({
        company_short: c,
        participants_latest: msgFundNotExist,
        participants_change: msgFundNotExist
      });
      bikNoData.push({ company_short: c, expense_ratio: msgFundNotExist });
      return;
    }

    const sorted = grpRange.slice().sort((a, b) => a.report_date - b.report_date);
    const relChanges = sorted.map(r => r.relative_change);

    const growthVal = geometricCumulativeGrowth(relChanges);
    const avgVal = annualisedYearlyReturn(relChanges);

    const worstVal = Math.min.apply(null, relChanges);
    const bestVal = Math.max.apply(null, relChanges);

    const firstPart = sorted[0].number_of_participants;
    const lastPart = sorted[sorted.length - 1].number_of_participants;
    let partLatestStr, partChangeStr, sortPart;

    if (
      firstPart == null || lastPart == null ||
      Number.isNaN(firstPart) || Number.isNaN(lastPart)
    ) {
      partLatestStr = msgFundNotExist;
      partChangeStr = msgFundNotExist;
      sortPart = -Infinity;
    } else {
      const latest = Math.round(lastPart);
      const diff = Math.round(lastPart - firstPart);
      partLatestStr = String(latest);
      partChangeStr = diff >= 0 ? `+${diff}` : String(diff);
      sortPart = latest;
    }

    const lastBik = sorted[sorted.length - 1].bik_pct;
    let bikStr, sortBik;
    if (lastBik == null || Number.isNaN(lastBik)) {
      bikStr = msgNoData;
      sortBik = Infinity;       // sort missing values last
    } else {
      bikStr = lastBik.toFixed(3);
      sortBik = lastBik;
    }

    growthNumeric.push({
      company_short: c,
      cumulative_growth: fmtSigned(growthVal, 2, msgFundNotExist),
      _sort: growthVal
    });
    avgNumeric.push({
      company_short: c,
      avg_yearly_return: fmtSigned(avgVal, 2, msgFundNotExist),
      _sort: avgVal
    });
    extremesNumeric.push({
      company_short: c,
      worst_quarter: fmtSigned(worstVal, 2, msgFundNotExist),
      best_quarter: fmtSigned(bestVal, 2, msgFundNotExist),
      _sort: worstVal
    });
    participantsNumeric.push({
      company_short: c,
      participants_latest: partLatestStr,
      participants_change: partChangeStr,
      _sort: sortPart
    });
    bikNumeric.push({
      company_short: c,
      expense_ratio: bikStr,
      _sort: sortBik
    });
  });

  growthNumeric.sort((a, b) => b._sort - a._sort);
  avgNumeric.sort((a, b) => b._sort - a._sort);
  extremesNumeric.sort((a, b) => a._sort - b._sort);
  participantsNumeric.sort((a, b) => b._sort - a._sort);
  bikNumeric.sort((a, b) => a._sort - b._sort);

  [growthNumeric, avgNumeric, extremesNumeric, participantsNumeric, bikNumeric]
    .forEach(list => list.forEach(r => delete r._sort));

  const growthRows = growthNumeric.concat(growthNoData);
  const avgRows = avgNumeric.concat(avgNoData);
  const extremesRows = extremesNumeric.concat(extremesNoData);
  const participantsRows = participantsNumeric.concat(participantsNoData);
  const bikRows = bikNumeric.concat(bikNoData);

  renderTable("growthTableBody", growthRows, ["company_short", "cumulative_growth"], mgr);
  renderTable("avgTableBody", avgRows, ["company_short", "avg_yearly_return"], mgr);
  renderTable("extremesTableBody", extremesRows, ["company_short", "worst_quarter", "best_quarter"], mgr);
  renderTable(
    "participantsTableBody",
    participantsRows,
    ["company_short", "participants_latest", "participants_change"],
    mgr
  );
  renderTable("bikTableBody", bikRows, ["company_short", "expense_ratio"], mgr);
}

function renderTable(tbodyId, rows, columns, selectedManager) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  tbody.innerHTML = "";

  rows.forEach(row => {
    const tr = document.createElement("tr");
    if (row.company_short === selectedManager) {
      tr.style.backgroundColor = "#fff3cd";
      tr.style.fontWeight = "700";
    }

    columns.forEach(col => {
      const td = document.createElement("td");
      const value = row[col];
      td.textContent = value;

      if (["cumulative_growth", "avg_yearly_return", "worst_quarter", "best_quarter", "participants_change"].includes(col)) {
        const v = String(value || "");
        if (v.includes("+")) {
          td.style.color = "#2e7d32";
          td.style.fontWeight = "600";
        } else if (v.includes("-")) {
          td.style.color = "#c62828";
          td.style.fontWeight = "600";
        }
      }
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });
}

// ------------------------
// 6. Popovers
// ------------------------

const isTouchDevice =
  "ontouchstart" in window ||
  navigator.maxTouchPoints > 0 ||
  navigator.msMaxTouchPoints > 0;

function initPopovers() {
  if (typeof $ === "undefined" || !$.fn.popover) return;

  // Destroy any existing popovers so they don't keep old content
  $(".help-popover").popover("dispose");

  $(".help-popover").each(function () {
    const $el = $(this);

    if (isTouchDevice) {
      // Mobile/tablet → click to open, tap outside to close
      $el.popover({ trigger: "click" });

      $(document).off("touchstart.fpPopover").on("touchstart.fpPopover", function (e) {
        if (!$(e.target).closest(".help-popover").length) {
          $(".help-popover").popover("hide");
        }
      });

    } else {
      // Desktop → hover
      $el.popover({ trigger: "manual" });

      $el.off("mouseenter.fpPopover mouseleave.fpPopover");
      $el.on("mouseenter.fpPopover", function () {
        $el.popover("show");
      });

      $el.on("mouseleave.fpPopover", function () {
        $el.popover("hide");
      });
    }
  });
}

// ------------------------
// 7. Init
// ------------------------

document.addEventListener("DOMContentLoaded", () => {
  const btnLT = document.getElementById("btnLangLT");
  const btnEN = document.getElementById("btnLangEN");
  if (btnLT) btnLT.addEventListener("click", () => applyLanguage("lt"));
  if (btnEN) btnEN.addEventListener("click", () => applyLanguage("en"));

  const periodButtons = document.getElementById("periodButtons");
  if (periodButtons) {
    periodButtons.addEventListener("click", ev => {
      const label = ev.target.closest(".btn-period");
      if (!label) return;
      const radio = label.querySelector('input[type="radio"]');
      if (!radio || radio.disabled) return;

      document.querySelectorAll(".btn-period").forEach(l => l.classList.remove("active"));
      label.classList.add("active");
      radio.checked = true;

      renderTables();
    });
  }

  // Dropdown event delegation
  const ftMenu = document.getElementById("fundTypeMenu");
  if (ftMenu) {
    ftMenu.addEventListener("click", ev => {
      const item = ev.target.closest("[data-fund-type]");
      if (!item) return;
      selectedFundType = item.getAttribute("data-fund-type");
      const labelEl = document.getElementById("fundTypeButtonLabel");
      if (labelEl) labelEl.textContent = selectedFundType;
      updatePeriodButtons();
      renderTables();
    });
  }

  const mgrMenu = document.getElementById("fundManagerMenu");
  if (mgrMenu) {
    mgrMenu.addEventListener("click", ev => {
      const item = ev.target.closest("[data-manager]");
      if (!item) return;
      selectedManager = item.getAttribute("data-manager");
      const labelEl = document.getElementById("fundManagerButtonLabel");
      if (labelEl) labelEl.textContent = selectedManager;
      updatePeriodButtons();
      renderTables();
    });
  }

  loadData().then(() => {
    initFilters();
    applyLanguage("lt"); // this will also call initPopovers()
  });
});