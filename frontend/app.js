(() => {
  "use strict";

  const API_URL = "http://localhost:8000/api/generate-ifc";

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
  let pendingStart = null; // first click stored here

  // ---- Background image ----
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

  // ---- Canvas click ----
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
      walls.push({
        start: { ...pendingStart },
        end: { x, y },
      });
      pendingStart = null;
      updateWallCount();
      redraw();
    }
  });

  // ---- Mouse move preview ----
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

  // ---- Undo / Clear ----
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

  // ---- Generate IFC ----
  generateBtn.addEventListener("click", async () => {
    if (walls.length === 0) {
      setStatus("壁が1つも描画されていません。先にCanvasをクリックしてください。", "error");
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

    setStatus("IFCを生成中…", "");
    generateBtn.disabled = true;

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

      setStatus("ダウンロード完了 ✓", "success");
    } catch (err) {
      setStatus(`エラー: ${err.message}`, "error");
    } finally {
      generateBtn.disabled = false;
    }
  });

  // ---- Drawing helpers ----
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

  function setStatus(msg, type) {
    statusMsg.textContent = msg;
    statusMsg.className = "status" + (type ? ` ${type}` : "");
  }
})();
