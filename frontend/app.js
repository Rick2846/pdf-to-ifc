(() => {
  "use strict";

  const API_BASE = "http://localhost:8000";
  const API_URL = `${API_BASE}/api/generate-ifc`;
  const PARSE_URL = `${API_BASE}/api/parse-walls`;
  const DETECT_URL = `${API_BASE}/api/detect-lines`;

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
  //  Unified wall state
  //  形式: { start_point: {x,y}, end_point: {x,y}, height, thickness }
  // ================================================================
  let globalWalls = [];
  let pendingStart = null;

  // ================================================================
  //  Canvas UI
  // ================================================================
  const canvas = document.getElementById("drawCanvas");
  const ctx = canvas.getContext("2d");
  const imageInput = document.getElementById("imageInput");
  const autoDetectBtn = document.getElementById("autoDetectBtn");
  const undoBtn = document.getElementById("undoBtn");
  const clearBtn = document.getElementById("clearBtn");
  const wallCountEl = document.getElementById("wallCount");
  const generateBtn = document.getElementById("generateBtn");
  const globalWallCountEl = document.getElementById("globalWallCount");
  const statusMsg = document.getElementById("statusMsg");

  let bgImage = null;
  let uploadedFile = null;

  imageInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    uploadedFile = file;
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
      const height = parseFloat(document.getElementById("wallHeight").value) || 3000;
      const thickness = parseFloat(document.getElementById("wallThickness").value) || 200;
      globalWalls.push({
        start_point: { x: pendingStart.x, y: pendingStart.y },
        end_point: { x, y },
        height,
        thickness,
      });
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
      globalWalls.pop();
    }
    updateWallCount();
    redraw();
  });

  clearBtn.addEventListener("click", () => {
    globalWalls = [];
    pendingStart = null;
    updateWallCount();
    redraw();
  });

  generateBtn.addEventListener("click", async () => {
    if (globalWalls.length === 0) {
      setStatus(statusMsg, "壁が1つもありません。Canvasで描画するか、AIチャットで追加してください。", "error");
      return;
    }

    const scaleFactor = parseFloat(document.getElementById("scaleFactor").value) || 1.0;

    const payload = {
      walls: globalWalls.map((w) => ({
        start_point: w.start_point,
        end_point: w.end_point,
        height: w.height,
        thickness: w.thickness,
      })),
      scale_factor: scaleFactor,
    };

    await downloadIfc(payload, generateBtn, statusMsg);
  });

  // ======== Auto-detect from image ========
  autoDetectBtn.addEventListener("click", async () => {
    if (!uploadedFile) {
      setStatus(statusMsg, "先に「図面画像を読み込む」で画像をアップロードしてください。", "error");
      return;
    }

    const height = parseFloat(document.getElementById("wallHeight").value) || 3000;
    const thickness = parseFloat(document.getElementById("wallThickness").value) || 200;

    autoDetectBtn.disabled = true;
    setStatus(statusMsg, "画像を解析中…", "");

    try {
      const formData = new FormData();
      formData.append("file", uploadedFile);

      const res = await fetch(DETECT_URL, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "不明なエラー" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      if (!data.lines || data.lines.length === 0) {
        setStatus(statusMsg, "線が検出されませんでした。画像を確認してください。", "error");
        return;
      }

      data.lines.forEach((line) => {
        globalWalls.push({
          start_point: line.start_point,
          end_point: line.end_point,
          height,
          thickness,
        });
      });

      updateWallCount();
      redraw();
      setStatus(statusMsg, `${data.lines.length}本の線を検出し、壁データに追加しました。`, "success");
    } catch (err) {
      setStatus(statusMsg, `自動認識エラー: ${err.message}`, "error");
    } finally {
      autoDetectBtn.disabled = false;
    }
  });

  function redraw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (bgImage) {
      ctx.drawImage(bgImage, 0, 0, canvas.width, canvas.height);
    }
    globalWalls.forEach((w, i) => {
      ctx.strokeStyle = "#e11d48";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(w.start_point.x, w.start_point.y);
      ctx.lineTo(w.end_point.x, w.end_point.y);
      ctx.stroke();
      drawMarker(w.start_point.x, w.start_point.y, "#e11d48");
      drawMarker(w.end_point.x, w.end_point.y, "#e11d48");

      const mx = (w.start_point.x + w.end_point.x) / 2;
      const my = (w.start_point.y + w.end_point.y) / 2;
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
    wallCountEl.textContent = `壁: ${globalWalls.length}`;
    globalWallCountEl.textContent = `合計壁数: ${globalWalls.length}`;
  }

  // ================================================================
  //  AI Chat
  // ================================================================
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");
  const chatSendBtn = document.getElementById("chatSendBtn");
  const chatMessages = document.getElementById("chatMessages");
  const parsedJsonEl = document.getElementById("parsedJson");
  const chatStatusMsg = document.getElementById("chatStatusMsg");

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    appendChatMsg(text, "user");
    chatInput.value = "";
    chatSendBtn.disabled = true;
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

      const addedCount = data.walls.length;
      data.walls.forEach((w) => {
        globalWalls.push({
          start_point: w.start_point,
          end_point: w.end_point,
          height: w.height,
          thickness: w.thickness,
        });
      });

      updateWallCount();
      redraw();

      const summary = data.walls
        .map(
          (w, i) =>
            `壁${i + 1}: (${w.start_point.x}, ${w.start_point.y}) → (${w.end_point.x}, ${w.end_point.y}), H=${w.height}mm, T=${w.thickness}mm`
        )
        .join("\n");

      appendChatMsg(
        `${addedCount}枚の壁を追加しました（合計${globalWalls.length}枚）:\n${summary}`,
        "assistant"
      );
      parsedJsonEl.textContent = JSON.stringify(data, null, 2);
      setStatus(chatStatusMsg, `${addedCount}枚の壁をCanvasに追加しました。`, "success");
    } catch (err) {
      appendChatMsg(`エラー: ${err.message}`, "error");
      parsedJsonEl.textContent = "解析に失敗しました";
    } finally {
      chatSendBtn.disabled = false;
    }
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
