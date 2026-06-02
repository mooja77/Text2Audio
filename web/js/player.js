const Player = {
  mount(container, item) {
    container.innerHTML = `
      <div class="player">
        <div style="font-weight:600;font-size:16px">${item.title}</div>
        <div class="muted" style="font-size:13px">${item.author || ""} · ${item.chapters.length} chapters</div>
        <audio id="aud" controls preload="metadata" src="/api/audio/${item.id}"></audio>
        <div class="label">Chapters</div>
        <div id="chaps"></div>
      </div>`;
    const aud = container.querySelector("#aud");
    const chaps = container.querySelector("#chaps");
    chaps.innerHTML = item.chapters.map((c, i) =>
      `<div class="chap" data-s="${c.startMs / 1000}" data-i="${i}">
         <span class="muted">${i + 1}</span><span style="flex:1">${c.title}</span>
         <span class="muted">${fmt(c.startMs / 1000)}</span></div>`).join("");
    chaps.querySelectorAll(".chap").forEach(row => row.onclick = () => {
      aud.currentTime = parseFloat(row.dataset.s); aud.play(); });
    aud.ontimeupdate = () => {
      const t = aud.currentTime * 1000;
      let cur = 0; item.chapters.forEach((c, i) => { if (t >= c.startMs) cur = i; });
      chaps.querySelectorAll(".chap").forEach(r => r.classList.toggle("cur", +r.dataset.i === cur));
    };
    function fmt(s) { const m = Math.floor(s / 60), ss = Math.floor(s % 60); return `${m}:${String(ss).padStart(2, "0")}`; }
  },
};
