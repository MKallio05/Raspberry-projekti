const grid   = "#0a0022";
const tick   = "#060";
const green  = "#0a0";
const bright = "#0f0";

const base = {
  responsive: true,
  plugins: { legend: { labels: { color: tick, font: { family: "monospace", size: 10 } } } },
  scales: {
    x: { ticks: { color: tick, font: { family: "monospace", size: 10 } }, grid: { color: grid } },
    y: { ticks: { color: tick, font: { family: "monospace", size: 10 } }, grid: { color: grid } }
  }
};

if (perUser.length) {
  new Chart(document.getElementById("userChart"), {
    type: "bar",
    data: {
      labels: perUser.map(u => u.username),
      datasets: [
        { label: "spins", data: perUser.map(u => u.spins), backgroundColor: green,  borderWidth: 0 },
        { label: "wins",  data: perUser.map(u => u.wins),  backgroundColor: bright, borderWidth: 0 },
      ]
    },
    options: base
  });
}

const tbody = document.getElementById("user-table");
if (tbody) {
  tbody.innerHTML = perUser.map(u => {
    const winrate = u.spins > 0 ? ((u.wins / u.spins) * 100).toFixed(1) + "%" : "—";
    return `<tr>
      <td class="u-name">${u.username}</td>
      <td>${u.spins}</td>
      <td>${u.wins}</td>
      <td class="u-muted">${winrate}</td>
      <td class="u-muted">${u.total_bet}</td>
      <td class="u-muted">${u.total_won}</td>
    </tr>`;
  }).join("");
}