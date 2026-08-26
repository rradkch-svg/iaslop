import { API } from "./api.js";

document.addEventListener("DOMContentLoaded", () => {
  const state = {
    currentProject: null,
    projects: [],
    voices: [],
    apiKeysStatus: {},
    youtubeStatus: { authenticated: false },
    activePollingInterval: null
  };

  // DOM Elements - Settings & Modals
  const openSettingsBtn = document.getElementById("open-settings-btn");
  const closeSettingsBtn = document.getElementById("close-settings-btn");
  const doneSettingsBtn = document.getElementById("done-settings-btn");
  const settingsModal = document.getElementById("settings-modal");
  const apiStatusDot = document.getElementById("api-status-dot");
  
  const keyGeminiInput = document.getElementById("key-gemini-input");
  const keyGroqInput = document.getElementById("key-groq-input");
  const testGeminiBtn = document.getElementById("test-gemini-btn");
  const testGroqBtn = document.getElementById("test-groq-btn");

  const youtubeSecretsFile = document.getElementById("youtube-secrets-file");
  const uploadSecretsBtn = document.getElementById("upload-secrets-btn");
  const connectYoutubeBtn = document.getElementById("connect-youtube-btn");
  const youtubeAuthStatus = document.getElementById("youtube-auth-status");

  // DOM Elements - Generation Form
  const btnResetForm = document.getElementById("btn-reset-form");
  const autoTopicInput = document.getElementById("auto-topic");
  const btnSuggestTopics = document.getElementById("btn-suggest-topics");
  const suggestedTopicsContainer = document.getElementById("suggested-topics-container");
  const topicsChipsList = document.getElementById("topics-chips-list");

  const autoFormat = document.getElementById("auto-format");
  const autoVoiceSelect = document.getElementById("auto-voice-select");
  const autoStyleSelect = document.getElementById("auto-style-select");
  const autoBgmSelect = document.getElementById("auto-bgm-select");
  const autoArtStyle = document.getElementById("auto-art-style");

  const btnStartAutopilot = document.getElementById("btn-start-autopilot");
  const autopilotProgressContainer = document.getElementById("autopilot-progress-container");
  const autopilotProgressBar = document.getElementById("autopilot-progress-bar");
  const autopilotStatusText = document.getElementById("autopilot-status-text");
  const autopilotLogs = document.getElementById("autopilot-logs");

  // DOM Elements - Video Player & Actions
  const videoStatusBadge = document.getElementById("video-status-badge");
  const videoEmptyState = document.getElementById("video-empty-state");
  const finalVideoPlayer = document.getElementById("final-video-player");
  const videoActionsContainer = document.getElementById("video-actions-container");
  const metaTitleText = document.getElementById("meta-title-text");
  const btnCopyTitle = document.getElementById("btn-copy-title");
  const btnDownloadVideo = document.getElementById("btn-download-video");
  const btnDownloadThumb = document.getElementById("btn-download-thumb");
  const btnUploadYtDirect = document.getElementById("btn-upload-yt-direct");
  const ytResultBox = document.getElementById("yt-result-box");
  const ytResultLink = document.getElementById("yt-result-link");

  const projectsHistoryList = document.getElementById("projects-history-list");
  const btnRefreshProjects = document.getElementById("btn-refresh-projects");
  const toastContainer = document.getElementById("toast-container");

  // Helper: Show Toast Notification
  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    const bgColors = {
      info: "bg-indigo-600",
      success: "bg-emerald-600",
      error: "bg-rose-600"
    };
    toast.className = `${bgColors[type] || bgColors.info} text-white px-4 py-2.5 rounded-lg shadow-xl text-xs font-medium transition-all duration-300 transform translate-y-2 opacity-0 flex items-center gap-2 border border-white/10 pointer-events-auto`;
    toast.innerHTML = `<span>${message}</span>`;
    toastContainer.appendChild(toast);
    
    setTimeout(() => {
      toast.classList.remove("translate-y-2", "opacity-0");
    }, 10);

    setTimeout(() => {
      toast.classList.add("opacity-0", "translate-y-2");
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Check and display API Keys status
  async function checkApiKeys() {
    try {
      const keys = await API.getApiKeys();
      state.apiKeysStatus = keys;
      if (keys.gemini_configured || keys.groq_configured || keys.openai_configured) {
        apiStatusDot.className = "w-2 h-2 rounded-full bg-emerald-400 shadow shadow-emerald-400/50";
      } else {
        apiStatusDot.className = "w-2 h-2 rounded-full bg-amber-400";
      }
    } catch (e) {
      console.error("API keys check error", e);
    }
  }

  // Check and display YouTube Authentication status
  async function checkYoutubeStatus() {
    try {
      const res = await API.getYoutubeStatus();
      state.youtubeStatus = res;
      if (res.authenticated) {
        youtubeAuthStatus.innerHTML = `<span class="text-emerald-400 font-bold">✓ Conectado: ${res.title || "Canal YouTube"}</span>`;
      } else {
        youtubeAuthStatus.textContent = "Status: Não conectado";
      }
    } catch (e) {
      console.error("YouTube status error:", e);
    }
  }

  // Settings Modal Events
  openSettingsBtn.addEventListener("click", () => {
    settingsModal.classList.remove("hidden");
    checkYoutubeStatus();
  });
  closeSettingsBtn.addEventListener("click", () => settingsModal.classList.add("hidden"));
  doneSettingsBtn.addEventListener("click", () => settingsModal.classList.add("hidden"));

  // Test & Save Gemini Key
  testGeminiBtn.addEventListener("click", async () => {
    const key = keyGeminiInput.value.trim();
    if (!key) {
      showToast("Insira sua chave do Google Gemini.", "error");
      return;
    }
    testGeminiBtn.textContent = "Testando...";
    testGeminiBtn.disabled = true;
    try {
      const res = await API.saveApiKeys({ test_provider: "gemini", gemini: key });
      if (res.valid) {
        showToast(res.message, "success");
      } else {
        showToast(res.message, "error");
      }
      checkApiKeys();
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      testGeminiBtn.textContent = "Testar & Salvar";
      testGeminiBtn.disabled = false;
    }
  });

  // Test & Save Groq Key
  testGroqBtn.addEventListener("click", async () => {
    const key = keyGroqInput.value.trim();
    if (!key) {
      showToast("Insira sua chave da Groq.", "error");
      return;
    }
    testGroqBtn.textContent = "Testando...";
    testGroqBtn.disabled = true;
    try {
      const res = await API.saveApiKeys({ test_provider: "groq", groq: key });
      if (res.valid) {
        showToast(res.message, "success");
      } else {
        showToast(res.message, "error");
      }
      checkApiKeys();
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      testGroqBtn.textContent = "Testar & Salvar";
      testGroqBtn.disabled = false;
    }
  });

  // YouTube OAuth JSON Upload
  uploadSecretsBtn.addEventListener("click", async () => {
    const file = youtubeSecretsFile.files[0];
    if (!file) {
      showToast("Selecione o arquivo client_secrets.json primeiro.", "error");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await API.uploadYoutubeClientSecrets(formData);
      showToast(res.message || "Arquivo salvo com sucesso!", "success");
    } catch (e) {
      showToast("Erro ao carregar client_secrets.json: " + e.message, "error");
    }
  });

  // YouTube Connect Desktop Flow
  connectYoutubeBtn.addEventListener("click", async () => {
    try {
      showToast("Abrindo autenticação do Google no navegador...", "info");
      const res = await API.authYoutubeDesktop();
      if (res.authenticated) {
        showToast(`Canal conectado com sucesso: ${res.title}`, "success");
        checkYoutubeStatus();
      }
    } catch (e) {
      showToast(e.message, "error");
    }
  });

  // Reset form to start a new video
  btnResetForm.addEventListener("click", () => {
    autoTopicInput.value = "";
    suggestedTopicsContainer.classList.add("hidden");
    autopilotProgressContainer.classList.add("hidden");
    autoTopicInput.focus();
    showToast("Pronto para criar um novo vídeo de curiosidades!", "info");
  });

  // Suggest Curiosities Topics with AI
  btnSuggestTopics.addEventListener("click", async () => {
    btnSuggestTopics.disabled = true;
    btnSuggestTopics.innerHTML = `<span>🎲 Gerando Ideias...</span>`;
    try {
      const format = autoFormat.value;
      const res = await API.generateTopics("curiosidades", format);
      const topics = res.topics || [];
      if (topics.length > 0) {
        topicsChipsList.innerHTML = "";
        topics.forEach(t => {
          const chip = document.createElement("div");
          chip.className = "p-2.5 rounded-lg bg-slate-950/80 hover:bg-slate-900 border border-slate-800 hover:border-indigo-500/60 cursor-pointer transition-all flex flex-col gap-0.5 group";
          chip.innerHTML = `
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-slate-200 group-hover:text-indigo-300 transition-colors">${t.topic}</span>
              <span class="text-[10px] text-indigo-400 font-mono">Selecionar ↵</span>
            </div>
            <p class="text-[11px] text-slate-400 line-clamp-1">${t.hook}</p>
          `;
          chip.addEventListener("click", () => {
            autoTopicInput.value = t.topic;
            showToast(`Tema selecionado: "${t.topic}"`, "info");
          });
          topicsChipsList.appendChild(chip);
        });
        suggestedTopicsContainer.classList.remove("hidden");
      }
    } catch (e) {
      showToast("Erro ao sugerir temas: " + e.message, "error");
    } finally {
      btnSuggestTopics.disabled = false;
      btnSuggestTopics.innerHTML = `<span>🎲 Sugerir Curiosidades com IA</span>`;
    }
  });

  // Populate Voices & Configuration
  async function loadInitialConfig() {
    try {
      const voiceData = await API.getVoices();
      state.voices = voiceData.voices || [];
      autoVoiceSelect.innerHTML = "";
      state.voices.forEach(v => {
        const opt = document.createElement("option");
        opt.value = v.id;
        opt.textContent = `${v.name} (${v.gender})`;
        if (v.id === "en-US-ChristopherNeural") opt.selected = true;
        autoVoiceSelect.appendChild(opt);
      });
    } catch (e) {
      console.error("Error loading voices:", e);
    }
    checkApiKeys();
    checkYoutubeStatus();
    loadProjectsList();
  }

  // Load and render projects history list
  async function loadProjectsList() {
    try {
      const res = await API.getProjects();
      state.projects = res.projects || [];
      projectsHistoryList.innerHTML = "";

      if (state.projects.length === 0) {
        projectsHistoryList.innerHTML = `<div class="text-xs text-slate-500 py-4 text-center">Nenhum projeto salvo ainda.</div>`;
        return;
      }

      state.projects.forEach(p => {
        const isShort = p.video_format === "shorts_9_16";
        const formatIcon = isShort ? "📱" : "🖥️";
        const isDone = p.status === "completed";
        const statusBadge = isDone 
          ? `<span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/60 font-semibold">✓ Pronto</span>`
          : `<span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800/60 font-semibold">${p.status}</span>`;

        const item = document.createElement("div");
        item.className = "p-2.5 rounded-lg bg-slate-900/60 hover:bg-slate-800/90 border border-slate-800/80 hover:border-slate-700 cursor-pointer transition-all flex items-center justify-between gap-2 group";
        item.innerHTML = `
          <div class="flex items-center gap-2.5 overflow-hidden">
            <span class="text-base flex-shrink-0">${formatIcon}</span>
            <div class="flex flex-col min-w-0">
              <span class="text-xs font-semibold text-slate-200 group-hover:text-white truncate">${p.title || p.topic || p.id}</span>
              <span class="text-[10px] text-slate-500 font-mono">${p.id}</span>
            </div>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            ${statusBadge}
          </div>
        `;

        item.addEventListener("click", () => {
          loadProjectIntoPlayer(p.id);
        });

        projectsHistoryList.appendChild(item);
      });
    } catch (e) {
      console.error("Error loading projects list:", e);
    }
  }

  btnRefreshProjects.addEventListener("click", loadProjectsList);

  // Load a selected project into the Player and Metadata view
  async function loadProjectIntoPlayer(projectId) {
    try {
      const proj = await API.getProject(projectId);
      state.currentProject = proj;
      
      const isShort = proj.video_format === "shorts_9_16";
      videoStatusBadge.innerHTML = `<span class="text-emerald-400 font-semibold">✓ ${isShort ? "Shorts (9:16)" : "Long-form (16:9)"}</span>`;

      if (proj.final_video_path) {
        videoEmptyState.classList.add("hidden");
        finalVideoPlayer.classList.remove("hidden");
        finalVideoPlayer.src = `${proj.final_video_path}?t=${Date.now()}`;
        finalVideoPlayer.load();

        // Metadata & Actions
        videoActionsContainer.classList.remove("hidden");
        const title = (proj.metadata && proj.metadata.titles && proj.metadata.titles[0]) || proj.title || proj.topic;
        metaTitleText.textContent = title;
        
        btnDownloadVideo.href = proj.final_video_path;
        btnDownloadVideo.download = `${proj.id}_video.mp4`;

        if (proj.thumbnail && proj.thumbnail.thumbnail_url) {
          btnDownloadThumb.href = proj.thumbnail.thumbnail_url;
          btnDownloadThumb.classList.remove("opacity-50", "pointer-events-none");
        } else {
          btnDownloadThumb.classList.add("opacity-50", "pointer-events-none");
        }

        ytResultBox.classList.add("hidden");
      } else {
        videoEmptyState.classList.remove("hidden");
        finalVideoPlayer.classList.add("hidden");
        videoActionsContainer.classList.add("hidden");
        videoStatusBadge.textContent = `Status: ${proj.status}`;
      }
    } catch (e) {
      showToast("Erro ao carregar vídeo: " + e.message, "error");
    }
  }

  // Copy Title to clipboard
  btnCopyTitle.addEventListener("click", () => {
    const text = metaTitleText.textContent;
    navigator.clipboard.writeText(text).then(() => {
      showToast("Título copiado para a área de transferência!", "success");
    });
  });

  // Direct YouTube Upload
  btnUploadYtDirect.addEventListener("click", async () => {
    if (!state.currentProject) {
      showToast("Nenhum vídeo carregado no momento.", "error");
      return;
    }
    btnUploadYtDirect.disabled = true;
    btnUploadYtDirect.innerHTML = `<span>Publicando...</span>`;

    try {
      const proj = state.currentProject;
      const title = (proj.metadata && proj.metadata.titles && proj.metadata.titles[0]) || proj.title || proj.topic;
      const desc = (proj.metadata && proj.metadata.description) || "";
      const tags = (proj.metadata && proj.metadata.tags) || [];

      const res = await API.uploadToYoutube(proj.id, {
        title,
        description: desc,
        tags,
        privacy_status: "private",
        category_id: "27"
      });

      if (res.video_url) {
        showToast("Vídeo postado no YouTube com sucesso!", "success");
        ytResultBox.classList.remove("hidden");
        ytResultLink.href = res.video_url;
        ytResultLink.textContent = `Assistir no YouTube: ${res.video_id}`;
      }
    } catch (e) {
      showToast("Falha no upload do YouTube: " + e.message, "error");
    } finally {
      btnUploadYtDirect.disabled = false;
      btnUploadYtDirect.innerHTML = `<span>🔴 Postar YouTube</span>`;
    }
  });

  // ---------------- 1-CLICK AUTO-PILOT EXECUTION ----------------
  btnStartAutopilot.addEventListener("click", async () => {
    let topic = autoTopicInput.value.trim();
    const format = autoFormat.value;
    const voiceId = autoVoiceSelect.value;
    const subStyle = autoStyleSelect.value;
    const bgmTrack = autoBgmSelect.value;
    const artStyle = autoArtStyle.value;

    btnStartAutopilot.disabled = true;
    btnStartAutopilot.innerHTML = `<span>🚀 Auto-Pilot em Execução...</span>`;

    autopilotProgressContainer.classList.remove("hidden");
    autopilotProgressBar.style.width = "5%";
    autopilotStatusText.textContent = "Status: Iniciando produção autônoma...";
    autopilotLogs.innerHTML = `<div class="text-indigo-400">🚀 Disparo iniciado: Preparando pipeline de curiosidades...</div>`;

    // If topic is empty, generate one with AI
    if (!topic) {
      try {
        autopilotLogs.innerHTML += `<div class="text-slate-400">🎲 Nenhum tema fornecido. IA selecionando curiosidade viral...</div>`;
        const topData = await API.generateTopics("curiosidades", format);
        if (topData.topics && topData.topics.length > 0) {
          topic = topData.topics[0].topic;
          autoTopicInput.value = topic;
          autopilotLogs.innerHTML += `<div class="text-emerald-400">✓ Curiosidade selecionada: "${topic}"</div>`;
        } else {
          topic = "The Immortal Jellyfish and Biological Eternity";
        }
      } catch (e) {
        topic = "The Immortal Jellyfish and Biological Eternity";
      }
    }

    try {
      const proj = await API.triggerAutoPilot({
        topic,
        video_format: format,
        voice_id: voiceId,
        subtitle_style: subStyle,
        bgm_track: bgmTrack,
        art_style: artStyle
      });

      state.currentProject = proj;
      
      if (state.activePollingInterval) {
        clearInterval(state.activePollingInterval);
      }

      // Poll progress every 1.5s
      state.activePollingInterval = setInterval(async () => {
        try {
          const updated = await API.getProject(proj.id);
          state.currentProject = updated;
          
          const progress = updated.progress || 10;
          autopilotProgressBar.style.width = `${progress}%`;
          autopilotStatusText.textContent = `Status: ${updated.status} (${progress}%)`;
          
          if (updated.logs && updated.logs.length > 0) {
            autopilotLogs.innerHTML = updated.logs.map(l => `<div class="py-0.5 font-mono text-[11px] text-slate-300">${l}</div>`).join("");
            autopilotLogs.scrollTop = autopilotLogs.scrollHeight;
          }

          if (updated.status === "completed" || updated.status === "error") {
            clearInterval(state.activePollingInterval);
            state.activePollingInterval = null;
            btnStartAutopilot.disabled = false;
            btnStartAutopilot.innerHTML = `<span>🚀 Iniciar Produção Completa em 1-Clique</span>`;

            if (updated.status === "completed") {
              showToast("🎉 Vídeo de Curiosidades renderizado com sucesso!", "success");
              loadProjectIntoPlayer(updated.id);
              loadProjectsList();
            } else {
              showToast("Auto-Pilot encontrou um erro. Veja o terminal de logs.", "error");
            }
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 1500);

    } catch (e) {
      showToast("Falha ao iniciar Auto-Pilot: " + e.message, "error");
      btnStartAutopilot.disabled = false;
      btnStartAutopilot.innerHTML = `<span>🚀 Iniciar Produção Completa em 1-Clique</span>`;
    }
  });

  // Start initial configuration
  loadInitialConfig();
});
