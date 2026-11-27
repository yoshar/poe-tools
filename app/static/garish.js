(function () {
  const initialEl = document.getElementById("initial");
  if (!initialEl) return;
  const leagueEl = document.getElementById("league");
  const priceEl = document.getElementById("card_price");
  const resultsEl = document.getElementById("results");
  const tbody = document.querySelector("#jewels tbody");
  const ninjaCardEl = document.getElementById("ninja-card");

  const c = (v, d = 1) => (v == null ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d }));
  const pct = (v) => (v == null ? "–" : (v * 100).toFixed(1) + "%");
  const div = (v, rate) => (v == null || !rate ? "–" : (v / rate).toFixed(2));
  const esc = (s) => String(s).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  const warnIcon = (list) =>
    list && list.length ? ` <span class="weak" title="${esc(list.join("\n"))}">⚠</span>` : "";

  function ago(iso) {
    if (!iso) return "never";
    const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (mins < 1) return "just now";
    if (mins < 90) return mins + " min ago";
    return Math.round(mins / 60) + " h ago";
  }

  function render(ev) {
    const rate = ev.chaos_per_divine;
    ninjaCardEl.innerHTML =
      `poe.ninja card price: <b>${c(ev.card_price_ninja, 2)}c</b>` +
      (ev.card_volume_chaos != null ? ` · volume ${c(ev.card_volume_chaos, 0)}c` : "") +
      (rate ? ` · 1 div = ${c(rate)}c` : "") +
      ` · prices updated ${ago(ev.prices_updated_at)}` +
      (ev.card_price_overridden ? ` · <b>using your price</b>` : "");

    const warnings = [];
    if (ev.card_price_used == null) warnings.push("poe.ninja has no price for The Garish Power in this league. Type a card price above.");
    ev.card_warnings.forEach((w) => warnings.push("Card: " + w));
    if (ev.missing.length) warnings.push(`No poe.ninja price for ${ev.missing.join(", ")}. They are left out of the average.`);
    const weak = ev.jewels.filter((j) => j.chaos != null && j.warnings.length);
    const weakShare = weak.reduce((s, j) => s + (j.share || 0), 0);
    if (weak.length) warnings.push(`${weak.length} jewel price${weak.length > 1 ? "s are" : " is"} weak (⚠), making up ${pct(weakShare)} of the value.`);

    const profitClass = ev.profit == null ? "" : ev.profit > 0 ? "good" : "bad";
    resultsEl.innerHTML = `
      <div class="verdict ${profitClass}">${ev.verdict ? esc(ev.verdict) : "Not enough data"}</div>
      ${warnings.map((w) => `<p class="warn">⚠ ${esc(w)}</p>`).join("")}
      <dl class="stats">
        <div><dt>Cost per turn-in</dt><dd>${c(ev.cost)}c <small>${div(ev.cost, rate)} div</small></dd></div>
        <div><dt>Average jewel value</dt><dd>${c(ev.avg_value)}c <small>${div(ev.avg_value, rate)} div</small></dd></div>
        <div><dt>Expected profit per turn-in</dt><dd class="${profitClass}">${c(ev.profit)}c <small>${div(ev.profit, rate)} div</small></dd></div>
        <div><dt>ROI</dt><dd class="${profitClass}">${pct(ev.roi)}</dd></div>
        <div><dt>Break-even card price</dt><dd>${c(ev.break_even_card_price, 2)}c</dd></div>
        <div><dt>Median jewel value</dt><dd>${c(ev.median_value)}c</dd></div>
        <div><dt>Chance a turn-in covers its cost</dt><dd>${pct(ev.chance_beats_cost)}</dd></div>
        <div><dt>Average without the top jewel</dt><dd>${c(ev.avg_excluding_top)}c</dd></div>
      </dl>`;

    tbody.innerHTML = ev.jewels
      .map(
        (j) => `<tr class="${j.warnings.length ? "weak-row" : ""}">
        <td>${esc(j.name)}${warnIcon(j.warnings)}</td><td>${esc(j.base_type)}</td>
        <td class="num">${c(j.chaos)}</td><td class="num">${div(j.chaos, rate)}</td>
        <td class="num">${j.listing_count == null ? "–" : j.listing_count}</td>
        <td>${j.beats_cost == null ? "–" : j.beats_cost ? "Yes" : "No"}</td>
        <td class="num">${pct(j.share)}</td></tr>`
      )
      .join("");
  }

  let timer = null;
  let seq = 0;
  async function refresh() {
    const params = new URLSearchParams({ league: leagueEl.value });
    if (priceEl.value.trim() !== "") params.set("card_price", priceEl.value.trim());
    history.replaceState(null, "", "/tools/garish-power?" + params);
    const mine = ++seq;
    const r = await fetch("/api/tools/garish-power?" + params);
    if (!r.ok || mine !== seq) return;
    render(await r.json());
  }
  const soon = () => {
    clearTimeout(timer);
    timer = setTimeout(refresh, 250);
  };

  leagueEl.addEventListener("change", refresh);
  priceEl.addEventListener("input", soon);
  document.getElementById("reset").addEventListener("click", () => {
    priceEl.value = "";
    refresh();
  });
  document.getElementById("controls").addEventListener("submit", (e) => {
    e.preventDefault();
    refresh();
  });

  render(JSON.parse(initialEl.textContent));
  setInterval(refresh, 5 * 60 * 1000); // pick up new prices while the page is open
})();
