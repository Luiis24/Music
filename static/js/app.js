const form = document.querySelector("#form");
const urlInput = document.querySelector("#url");
const statusEl = document.querySelector("#status");
const overlay = document.querySelector("#overlay");
const qualitiesEl = document.querySelector("#qualities");
const titleEl = document.querySelector("#video-title");
const directoryStatus = document.querySelector("#directory-status");
const buttons = [...document.querySelectorAll("button")];
let downloadDirectory = null;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function setBusy(busy) {
  buttons.forEach((button) => {
    button.disabled = busy;
  });
}

function filenameFrom(response) {
  const header = response.headers.get("Content-Disposition") || "";
  const match = header.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
  return decodeURIComponent(match?.[1] || match?.[2] || "descarga");
}

async function saveAudio(blob, filename) {
  if (!downloadDirectory) {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    return;
  }

  let permission = await downloadDirectory.queryPermission({ mode: "readwrite" });
  if (permission !== "granted") {
    permission = await downloadDirectory.requestPermission({ mode: "readwrite" });
  }
  if (permission !== "granted") {
    throw new Error("No se concedió permiso para guardar en esa carpeta.");
  }

  const file = await downloadDirectory.getFileHandle(filename, { create: true });
  const writable = await file.createWritable();
  await writable.write(blob);
  await writable.close();
}

async function download(kind, height) {
  setBusy(true);
  const label = kind === "mp4" ? "MP4" : kind.toUpperCase();
  setStatus(`Preparando el ${label}…`);
  try {
    const response = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: urlInput.value.trim(), kind, height }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || "No se pudo descargar.");
    }
    const blob = await response.blob();
    const filename = filenameFrom(response);
    if (kind === "mp3" || kind === "opus") {
      await saveAudio(blob, filename);
      setStatus(downloadDirectory ? `Listo. Guardado en ${downloadDirectory.name}.` : "Listo. Revisa tu carpeta de descargas.");
    } else {
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
      setStatus("Listo. Revisa tu carpeta de descargas.");
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(false);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  download("mp3");
});

document.querySelector('[data-kind="opus"]').addEventListener("click", () => {
  if (form.reportValidity()) download("opus");
});

document.querySelector("#choose-directory").addEventListener("click", async () => {
  if (!window.showDirectoryPicker) {
    setStatus("Este navegador no permite elegir una carpeta. Se usará su carpeta de descargas.", true);
    return;
  }
  try {
    downloadDirectory = await window.showDirectoryPicker({ mode: "readwrite" });
    directoryStatus.textContent = `Carpeta seleccionada: ${downloadDirectory.name}`;
    setStatus("");
  } catch (error) {
    if (error.name !== "AbortError") setStatus(error.message, true);
  }
});

document.querySelector("#mp4").addEventListener("click", async () => {
  if (!form.reportValidity()) return;
  setBusy(true);
  setStatus("Buscando calidades…");
  try {
    const response = await fetch("/api/qualities", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: urlInput.value.trim() }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "No se pudo leer el video.");
    titleEl.textContent = data.title;
    qualitiesEl.replaceChildren();
    data.qualities.forEach((quality, index) => {
      const label = document.createElement("label");
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "quality";
      radio.value = quality.height;
      radio.checked = index === 0;
      label.append(radio, ` ${quality.label}`);
      qualitiesEl.appendChild(label);
    });
    overlay.classList.add("open");
    setStatus("");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(false);
  }
});

document.querySelector("#cancel").addEventListener("click", () => {
  overlay.classList.remove("open");
});

overlay.addEventListener("click", (event) => {
  if (event.target === overlay) overlay.classList.remove("open");
});

document.querySelector("#confirm").addEventListener("click", () => {
  const selected = document.querySelector('input[name="quality"]:checked');
  if (!selected) return;
  overlay.classList.remove("open");
  download("mp4", Number(selected.value));
});
