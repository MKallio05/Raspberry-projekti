const SYMS = ["♠","♥","♦","♣","★"];
  let animating = false;
  const history = [];

  function rand() { return SYMS[Math.floor(Math.random() * SYMS.length)]; }
  function getCell(r, c) { return document.getElementById(`c${r}${c}`); }

  function clearWins() {
    for (let r = 0; r < 3; r++)
      for (let c = 0; c < 3; c++)
        getCell(r, c).classList.remove("win");
  }

  const lineMap = {
    row0:  [[0,0],[0,1],[0,2]], row1: [[1,0],[1,1],[1,2]], row2: [[2,0],[2,1],[2,2]],
    diag0: [[0,0],[1,1],[2,2]], diag1: [[0,2],[1,1],[2,0]],
  };

  function highlightWins(lines) {
    lines.forEach(l => { if (lineMap[l]) lineMap[l].forEach(([r,c]) => getCell(r,c).classList.add("win")); });
  }

  async function animateReels(finalGrid) {
    clearWins();
    let delay = 50;
    for (let i = 0; i < 20; i++) {
      for (let r = 0; r < 3; r++)
        for (let c = 0; c < 3; c++)
          getCell(r,c).innerText = rand();
      await new Promise(res => setTimeout(res, delay));
      delay += 10;
    }
    for (let r = 0; r < 3; r++)
      for (let c = 0; c < 3; c++)
        getCell(r,c).innerText = finalGrid[r][c];
  }

  function fmtLines(lines) {
    return lines.map(l =>
      l.replace("row0","R1").replace("row1","R2").replace("row2","R3")
       .replace("diag0","↘").replace("diag1","↙")).join(" ") || "—";
  }

  const source = new EventSource("/stream");
  source.onmessage = async function(event) {
    const data = JSON.parse(event.data);
    animating = true;
    document.getElementById("spin-btn").disabled = true;

    await animateReels(data.grid);
    if (data.win_lines.length) highlightWins(data.win_lines);

    document.getElementById("credits").innerText = data.credits;
    document.getElementById("bet").innerText = data.bet;
    document.getElementById("result").innerText =
      data.win > 0 ? `WIN +${data.win}  [${fmtLines(data.win_lines)}]` : "";

    history.unshift({ lines: fmtLines(data.win_lines), win: data.win, bet: data.bet });
    if (history.length > 5) history.pop();
    document.getElementById("history-list").innerHTML = history.map(h => `
      <div class="history-item">
        <span class="h-lines">${h.lines}</span>
        <span class="${h.win > 0 ? 'h-win' : 'h-loss'}">${h.win > 0 ? '+'+h.win : '-'+h.bet}</span>
      </div>`).join("");

    animating = false;
    document.getElementById("spin-btn").disabled = false;
  };

  async function updateState() {
    if (animating) return;
    const r = await fetch("/state");
    const s = await r.json();
    document.getElementById("credits").innerText = s.credits;
    document.getElementById("bet").innerText = s.bet;
  }

  setInterval(updateState, 500);
  updateState();

  async function betUp()   { await fetch("/bet_up"); }
  async function betDown() { await fetch("/bet_down"); }

  async function spin() {
    if (animating) return;
    document.getElementById("result").innerText = "";
    clearWins();
    await fetch("/spin", { method: "POST" });
  }