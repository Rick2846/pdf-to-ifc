(() => {
  "use strict";

  const API_BASE = "http://localhost:8000";
  const API_URL = `${API_BASE}/api/generate-ifc`;
  const PARSE_URL = `${API_BASE}/api/parse-walls`;

  // ======== Tab switching ========
  const tabs = document.querySelectorAll(".tab");
  const tabContents = document.querySelectorAll(".tab-content");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tabContents.forEach((c) => c.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
    });
  });

  // ================================================================
  //  Canvas UI (Feature 3 / 4.2)
  // ================================================================
  const canvas = document.getElementById("drawCanvas");
  const ctx = canvas.getContext("2d");
  const imageInput = document.getElementById("imageInput");
  const undoBtn = document.getElementById("undoBtn");
  const clearBtn = document.getElementById("clearBtn");
  const wallCountEl = document.getElementById("wallCount");
  const generateBtn = document.getElementById("generateBtn");
  const statusMsg = document.getElementById("statusMsg");

  let bgImage = null;
  let walls = [];
  let pendingStart = null;

  imageInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const img = new Image();
    img.onload = () => {
      bgImage = img;
      canvas.width = img.width;
      canvas.height = img.height;
      redraw();
    };
    img.src = URL.createObjectURL(file);
  });

  canvas.addEventListener("click", (e) => {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    if (!pendingStart) {
      pendingStart = { x, y };
      redraw();
      drawMarker(x, y, "#4f46e5");
    } else {
      walls.push({ start: { ...pendingStart }, end: { x, y } });
      pendingStart = null;
      updateWallCount();
      redraw();
    }
  });

  canvas.addEventListener("mousemove", (e) => {
    if (!pendingStart) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const mx = (e.clientX - rect.left) * scaleX;
    const my = (e.clientY - rect.top) * scaleY;
    redraw();
    drawMarker(pendingStart.x, pendingStart.y, "#4f46e5");
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = "#6366f1";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(pendingStart.x, pendingStart.y);
    ctx.lineTo(mx, my);
    ctx.stroke();
    ctx.setLineDash([]);
  });

  undoBtn.addEventListener("click", () => {
    if (pendingStart) {
      pendingStart = null;
    } else {
      walls.pop();
    }
    updateWallCount();
    redraw();
  });

  clearBtn.addEventListener("click", () => {
    walls = [];
    pendingStart = null;
    updateWallCount();
    redraw();
  });

  generateBtn.addEventListener("click", async () => {
    if (walls.length === 0) {
      setStatus(statusMsg, "壁が1つも描画されていません。先にCanvasをクリックしてください。", "error");
      return;
    }

    const height = parseFloat(document.getElementById("wallHeight").value) || 3000;
    const thickness = parseFloat(document.getElementById("wallThickness").value) || 200;
    const scaleFactor = parseFloat(document.getElementById("scaleFactor").value) || 1.0;

    const payload = {
      walls: walls.map((w) => ({
        start_point: { x: w.start.x, y: w.start.y },
        end_point: { x: w.end.x, y: w.end.y },
        height,
        thickness,
      })),
      scale_factor: scaleFactor,
    };

    await downloadIfc(payload, generateBtn, statusMsg);
  });

  function redraw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (bgImage) {
      ctx.drawImage(bgImage, 0, 0, canvas.width, canvas.height);
    }
    walls.forEach((w, i) => {
      ctx.strokeStyle = "#e11d48";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(w.start.x, w.start.y);
      ctx.lineTo(w.end.x, w.end.y);
      ctx.stroke();
      drawMarker(w.start.x, w.start.y, "#e11d48");
      drawMarker(w.end.x, w.end.y, "#e11d48");

      const mx = (w.start.x + w.end.x) / 2;
      const my = (w.start.y + w.end.y) / 2;
      ctx.fillStyle = "#1e293b";
      ctx.font = "bold 13px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(`W${i + 1}`, mx, my - 8);
    });
  }

  function drawMarker(x, y, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fill();
  }

  function updateWallCount() {
    wallCountEl.textContent = `壁: ${walls.length}`;
  }

  // ================================================================
  //  AI Chat (Feature 2 / 4.1)
  // ================================================================
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");
  const chatSendBtn = document.getElementById("chatSendBtn");
  const chatMessages = document.getElementById("chatMessages");
  const parsedJsonEl = document.getElementById("parsedJson");
  const chatGenerateBtn = document.getElementById("chatGenerateBtn");
  const chatStatusMsg = document.getElementById("chatStatusMsg");

  let lastParsedPayload = null;

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    appendChatMsg(text, "user");
    chatInput.value = "";
    chatSendBtn.disabled = true;
    chatGenerateBtn.disabled = true;
    lastParsedPayload = null;
    parsedJsonEl.textContent = "解析中…";
    setStatus(chatStatusMsg, "", "");

    try {
      const res = await fetch(PARSE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "不明なエラー" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      lastParsedPayload = data;

      const summary = data.walls
        .map(
          (w, i) =>
            `壁${i + 1}: (${w.start_point.x}, ${w.start_point.y}) → (${w.end_point.x}, ${w.end_point.y}), H=${w.height}mm, T=${w.thickness}mm`
        )
        .join("\n");

      appendChatMsg(`${data.walls.length}枚の壁を検出しました:\n${summary}`, "assistant");
      parsedJsonEl.textContent = JSON.stringify(data, null, 2);
      chatGenerateBtn.disabled = false;
    } catch (err) {
      appendChatMsg(`エラー: ${err.message}`, "error");
      parsedJsonEl.textContent = "解析に失敗しました";
    } finally {
      chatSendBtn.disabled = false;
    }
  });

  chatGenerateBtn.addEventListener("click", async () => {
    if (!lastParsedPayload) return;
    await downloadIfc(lastParsedPayload, chatGenerateBtn, chatStatusMsg);
  });

  function appendChatMsg(text, role) {
    const div = document.createElement("div");
    div.className = `chat-msg ${role}`;
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // ================================================================
  //  Shared helpers
  // ================================================================
  async function downloadIfc(payload, btn, msgEl) {
    setStatus(msgEl, "IFCを生成中…", "");
    btn.disabled = true;

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "不明なエラー" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "output.ifc";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      setStatus(msgEl, "ダウンロード完了", "success");
    } catch (err) {
      setStatus(msgEl, `エラー: ${err.message}`, "error");
    } finally {
      btn.disabled = false;
    }
  }

  function setStatus(el, msg, type) {
    el.textContent = msg;
    el.className = "status" + (type ? ` ${type}` : "");
  }
})();
