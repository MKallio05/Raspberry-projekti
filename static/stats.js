const gridColor = "#0a0022";
const tickColor = "#060";

const baseOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { color: tickColor, maxTicksLimit: 8, font: { family: "monospace", size: 10 } }, grid: { color: gridColor } },
    y: { ticks: { color: tickColor, font: { family: "monospace", size: 10 } }, grid: { color: gridColor } }
  }
};

if (balanceData.length) {
  new Chart(document.getElementById("balanceChart"), {
    type: "line",
    data: {
      labels: balanceData.map((_, i) => i + 1),
      datasets: [{
        data: balanceData.map(d => d.c),
        borderColor: "#0f0",
        backgroundColor: "transparent",
        borderWidth: 1.5,
        pointRadius: balanceData.length > 50 ? 0 : 3,
        pointBackgroundColor: "#0f0",
        tension: 0.3,
      }]
    },
    options: baseOptions
  });
}