import { API } from "./api.js";

document.addEventListener("DOMContentLoaded", () => {
  const state = {
    currentProject: null,
    activeTab: "studio", // studio or autopilot
    currentStep: 1,
    voices: [],
    formats: [],
    genres: [],
    apiKeysStatus: {}
  };

  // DOM Elements
  const studioTabBtn = document.getElementById("tab-studio-btn");
  const autopilotTabBtn = document.getElementById("tab-autopilot-btn");
  const studioView = document.getElementById("studio-view");
  const autopilotView = document.getElementById("autopilot-view");
  
  const stepIndicators = document.querySelectorAll(".step-item");
  const stepPanels = document.querySelectorAll(".step-panel");
  const projectSelect = document.getElementById("project-select");
  const newProjectBtn = document.getElementById("new-project-btn");
  const toastContainer = document.getElementById("toast-container");

  // Settings Modal Elements
  const openSettingsBtn = document.getElementById("open-settings-btn");
  const closeSettingsBtn = document.getElementById("close-settings-btn");
  const doneSettingsBtn = document.getElementById("done-settings-btn");
  const settingsModal = document.getElementById("settings-modal");
  const apiStatusDot = document.getElementById("api-status-dot");
  
  const keyGeminiInput = document.getElementById("key-gemini-input");
  const keyGroqInput = document.getElementById("key-groq-input");
  const keyOpenaiInput = document.getElementById("key-openai-input");
  const testGeminiBtn = document.getElementById("test-gemini-btn");
  const testGroqBtn = document.getElementById("test-groq-btn");
  const testOpenaiBtn = document.getElementById("test-openai-btn");

  // Topic & Genre Elements
  const genreSelect = document.getElementById("genre-select");
  const autoGenreSelect = document.getElementById("auto-genre-select");
  const btnGenerateTopics = document.getElementById("btn-generate-topics");
  const suggestedTopicsContainer = document.getElementById("suggested-topics-container");
  const step1Format = document.getElementById("step1-format");
  const wordTargetHint = document.getElementById("word-target-hint");
  const scriptStatsLabel = document.getElementById("script-stats-label");
  const wordCountBadge = document.getElementById("word-count-badge");
  const scriptPreview = document.getElementById("step1-script-preview");

  // Show Toast helper
  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    const bgColors = {
      info: "bg-indigo-600",
      success: "bg-emerald-600",
      error: "bg-rose-600"
    };
    toast.className = `${bgColors[type] || bgColors.info} text-white px-4 py-2.5 rounded-lg shadow-lg text-sm font-medium transition-all duration-300 transform translate-y-2 opacity-0 flex items-center gap-2`;
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

  // Update Word Count Tracker
  function updateWordCount() {
    const text = scriptPreview.value.trim();
    const count = text ? text.split(/\s+/).length : 0;
    const format = step1Format.value;
    const isShort = format === "shorts_9_16";
    const minTarget = isShort ? 200 : 3000;
    const maxTarget = isShort ? 400 : 4500;
    
    let statusClass = "text-amber-400";
    let statusText = "Em progresso";
    if (count >= minTarget && count <= maxTarget) {
      statusClass = "text-emerald-400";
      statusText = "✓ Meta Atingida";
    } else if (count > maxTarget) {
      statusClass = "text-rose-400";
      statusText = "Excesso de palavras";
    }

    scriptStatsLabel.textContent = `${count} palavras (${statusText})`;
    wordCountBadge.innerHTML = `<span class="${statusClass} font-bold">Palavras: ${count.toLocaleString()}</span> <span class="text-slate-500">| Meta: ${minTarget.toLocaleString()}-${maxTarget.toLocaleString()}</span>`;
  }

  scriptPreview.addEventListener("input", updateWordCount);

  step1Format.addEventListener("change", (e) => {
    const isShort = e.target.value === "shorts_9_16";
    wordTargetHint.textContent = isShort ? "Shorts: 200 - 400 palavras" : "Longo: 3.000 - 4.500 palavras";
    updateWordCount();
  });

  // Load API Keys & Config
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

  // Settings Modal Handlers
  openSettingsBtn.addEventListener("click", () => {
    settingsModal.classList.remove("hidden");
  });
  closeSettingsBtn.addEventListener("click", () => {
    settingsModal.classList.add("hidden");
  });
  doneSettingsBtn.addEventListener("click", () => {
    settingsModal.classList.add("hidden");
  });

  // Test Gemini
  testGeminiBtn.addEventListener("click", async () => {
    const key = keyGeminiInput.value.trim();
    if (!key) {
      showToast("Insira a chave do Gemini.", "error");
      return;
    }
    testGeminiBtn.textContent = "Testando...";
    testGeminiBtn.disabled = true;
    try {
      const res = await API.saveApiKeys({ test_provider: "gemini", gemini: key });
      showToast(res.message, "success");
      checkApiKeys();
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      testGeminiBtn.textContent = "Testar & Salvar";
      testGeminiBtn.disabled = false;
    }
  });

  // Test Groq
  testGroqBtn.addEventListener("click", async () => {
    const key = keyGroqInput.value.trim();
    if (!key) {
      showToast("Insira a chave do Groq.", "error");
      return;
    }
    testGroqBtn.textContent = "Testando...";
    testGroqBtn.disabled = true;
    try {
      const res = await API.saveApiKeys({ test_provider: "groq", groq: key });
      showToast(res.message, "success");
      checkApiKeys();
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      testGroqBtn.textContent = "Testar & Salvar";
      testGroqBtn.disabled = false;
    }
  });

  // Test OpenAI
  testOpenaiBtn.addEventListener("click", async () => {
    const key = keyOpenaiInput.value.trim();
    if (!key) {
      showToast("Insira a chave da OpenAI.", "error");
      return;
    }
    testOpenaiBtn.textContent = "Testando...";
    testOpenaiBtn.disabled = true;
    try {
      const res = await API.saveApiKeys({ test_provider: "openai", openai: key });
      showToast(res.message, "success");
      checkApiKeys();
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      testOpenaiBtn.textContent = "Testar & Salvar";
      testOpenaiBtn.disabled = false;
    }
  });

  // Load Voices, Formats & Genres
  async function initConfig() {
    try {
      const [voicesData, formatsData, genresData] = await Promise.all([
        API.getVoices(),
        API.getFormats(),
        API.getGenres()
      ]);
      state.voices = voicesData.voices || [];
      state.formats = formatsData.formats || [];
      state.genres = genresData.genres || [];

      // Populate voice selects
      const voiceSelects = [
        document.getElementById("step2-voice-select"),
        document.getElementById("auto-voice-select")
      ];
      voiceSelects.forEach(sel => {
        if (!sel) return;
        sel.innerHTML = state.voices.map(v => 
          `<option value="${v.id}">${v.name}</option>`
        ).join("");
      });

      // Populate genre selects
      const genreSelects = [genreSelect, autoGenreSelect];
      genreSelects.forEach(sel => {
        if (!sel) return;
        sel.innerHTML = state.genres.map(g => 
          `<option value="${g.id}">${g.name}</option>`
        ).join("");
      });

      checkApiKeys();
      loadProjectsList();
    } catch (e) {
      console.error("Config load error:", e);
      showToast("Erro ao carregar configurações do backend.", "error");
    }
  }

  // Generate Topics by Genre Handler
  btnGenerateTopics.addEventListener("click", async () => {
    const genreId = genreSelect.value;
    const format = step1Format.value;
    btnGenerateTopics.innerHTML = `<span>⏳ Gerando 3 ideias...</span>`;
    btnGenerateTopics.disabled = true;

    try {
      const data = await API.generateTopics(genreId, format);
      const topics = data.topics || [];
      
      suggestedTopicsContainer.classList.remove("hidden");
      suggestedTopicsContainer.innerHTML = topics.map((t, idx) => `
        <div class="p-3 rounded-lg bg-slate-950 border border-slate-700 hover:border-indigo-500 cursor-pointer transition-all flex flex-col gap-1 topic-card group" data-topic="${t.topic.replace(/"/g, '&quot;')}" data-tone="${t.tone}">
          <div class="flex justify-between items-center">
            <span class="text-xs font-bold text-indigo-300 group-hover:text-indigo-200">#${idx+1} ${t.topic}</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-400 uppercase font-mono">${t.tone}</span>
          </div>
          <p class="text-[11px] text-slate-400 italic">"${t.hook}"</p>
        </div>
      `).join("");

      // Attach click handlers to topic cards
      document.querySelectorAll(".topic-card").forEach(card => {
        card.addEventListener("click", () => {
          const top = card.getAttribute("data-topic");
          const tone = card.getAttribute("data-tone");
          document.getElementById("step1-topic").value = top;
          if (tone) document.getElementById("step1-tone").value = tone;
          showToast("Tema selecionado!", "success");
        });
      });

    } catch (e) {
      showToast("Erro ao sugerir temas: " + e.message, "error");
    } finally {
      btnGenerateTopics.innerHTML = `<span>🎲 Sugerir 3 Temas com IA</span>`;
      btnGenerateTopics.disabled = false;
    }
  });

  // Auto-pilot generate topic
  const btnAutoGenerateTopic = document.getElementById("btn-auto-generate-topic");
  if (btnAutoGenerateTopic) {
    btnAutoGenerateTopic.addEventListener("click", async () => {
      const genreId = autoGenreSelect.value;
      const format = document.getElementById("auto-format").value;
      btnAutoGenerateTopic.textContent = "⏳ Gerando...";
      try {
        const data = await API.generateTopics(genreId, format);
        if (data.topics && data.topics.length > 0) {
          document.getElementById("auto-topic").value = data.topics[0].topic;
          showToast(`Tema gerado: ${data.topics[0].topic}`, "info");
        }
      } catch (e) {
        showToast("Erro ao gerar tema automático", "error");
      } finally {
        btnAutoGenerateTopic.textContent = "🎲 Gerar Ideia com IA";
      }
    });
  }

  async function loadProjectsList() {
    try {
      const data = await API.getProjects();
      projectSelect.innerHTML = `<option value="">-- Selecionar ou Criar Projeto --</option>` +
        data.projects.map(p => `<option value="${p.id}">${p.title} (${p.video_format})</option>`).join("");
      
      if (data.projects.length > 0 && !state.currentProject) {
        selectProject(data.projects[0].id);
      }
    } catch (e) {
      console.error("Failed to load projects", e);
    }
  }

  async function selectProject(projectId) {
    if (!projectId) return;
    try {
      const proj = await API.getProject(projectId);
      state.currentProject = proj;
      projectSelect.value = projectId;
      renderProjectState();
    } catch (e) {
      showToast("Erro ao abrir projeto.", "error");
    }
  }

  function setStep(stepNum) {
    state.currentStep = stepNum;
    
    stepIndicators.forEach(ind => {
      const s = parseInt(ind.getAttribute("data-step"));
      ind.classList.remove("active", "completed");
      if (s === stepNum) {
        ind.classList.add("active");
      } else if (state.currentProject && s < state.currentProject.current_step) {
        ind.classList.add("completed");
      }
    });

    stepPanels.forEach(panel => {
      const pStep = parseInt(panel.getAttribute("data-step"));
      if (pStep === stepNum) {
        panel.classList.remove("hidden");
      } else {
        panel.classList.add("hidden");
      }
    });
  }

  function renderProjectState() {
    const proj = state.currentProject;
    if (!proj) return;

    // Update Step 1 Inputs
    document.getElementById("step1-topic").value = proj.topic || "";
    document.getElementById("step1-format").value = proj.video_format || "shorts_9_16";
    if (proj.full_script) {
      document.getElementById("step1-script-preview").value = proj.full_script;
      document.getElementById("step1-script-container").classList.remove("hidden");
      updateWordCount();
    }

    // Update Step 2 TTS
    if (proj.voice_id) {
      document.getElementById("step2-voice-select").value = proj.voice_id;
    }
    if (proj.audio_path) {
      const audioElem = document.getElementById("step2-audio-player");
      audioElem.src = proj.audio_path;
      document.getElementById("step2-audio-container").classList.remove("hidden");
      document.getElementById("step2-duration-badge").textContent = `${proj.audio_duration.toFixed(1)}s`;
    }

    // Update Step 4 & 5 Scenes & Prompts
    renderScenes(proj.scenes);

    // Update Step 6 Subtitles
    if (proj.subtitle_style) {
      document.getElementById("step6-style-select").value = proj.subtitle_style;
    }

    // Update Step 7 Final Video
    if (proj.final_video_path) {
      const videoElem = document.getElementById("step7-video-player");
      videoElem.src = proj.final_video_path;
      document.getElementById("step7-video-container").classList.remove("hidden");
      document.getElementById("download-video-btn").href = proj.final_video_path;
    }

    // Update Step 8 Metadata
    if (proj.metadata) {
      renderMetadata(proj.metadata);
      document.getElementById("step8-meta-container").classList.remove("hidden");
    }

    // Update Step 9 Thumbnail
    if (proj.thumbnail && proj.thumbnail.thumbnail_url) {
      document.getElementById("step9-thumb-img").src = proj.thumbnail.thumbnail_url;
      document.getElementById("step9-thumb-container").classList.remove("hidden");
      document.getElementById("download-thumb-btn").href = proj.thumbnail.thumbnail_url;
    }

    // Set active step to current project progress
    setStep(proj.current_step || 1);
  }

  function renderScenes(scenes) {
    const container = document.getElementById("step4-scenes-container");
    const gallery = document.getElementById("step5-images-gallery");
    if (!container || !gallery) return;

    if (!scenes || scenes.length === 0) {
      container.innerHTML = `<p class="text-slate-400 text-sm">Gere o áudio primeiro para segmentar e alinhar as cenas.</p>`;
      gallery.innerHTML = `<p class="text-slate-400 text-sm">Gere os prompts de cena primeiro.</p>`;
      return;
    }

    // Render Scene Prompts
    container.innerHTML = scenes.map((s, idx) => `
      <div class="p-4 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col gap-2">
        <div class="flex items-center justify-between text-xs text-indigo-400 font-mono">
          <span>Cena ${s.index} [${s.start_time.toFixed(1)}s - ${s.end_time.toFixed(1)}s] (${s.duration.toFixed(1)}s)</span>
          <span class="text-slate-500 uppercase">${s.motion_type}</span>
        </div>
        <p class="text-xs text-slate-300 italic font-sans">"${s.speech_text}"</p>
        <div class="mt-1">
          <label class="text-[11px] text-indigo-300 font-medium">Prompt Cinematográfico do Diretor:</label>
          <textarea class="w-full text-xs p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-slate-200 scene-prompt-input font-mono leading-relaxed" data-scene-id="${s.id}" rows="3">${s.visual_prompt || ""}</textarea>
        </div>
      </div>
    `).join("");

    // Render Images Gallery
    gallery.innerHTML = scenes.map((s, idx) => `
      <div class="relative group rounded-xl overflow-hidden border border-slate-800 bg-slate-950 flex flex-col">
        <div class="aspect-[9/16] w-full bg-slate-900 flex items-center justify-center overflow-hidden">
          ${s.image_url 
            ? `<img src="${s.image_url}" alt="Cena ${s.index}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />`
            : `<div class="text-center p-4"><span class="text-xs text-slate-500">Imagem não gerada</span></div>`
          }
        </div>
        <div class="p-3 bg-slate-900/90 flex flex-col gap-1 text-xs">
          <div class="flex justify-between items-center">
            <span class="font-mono text-indigo-400 font-semibold">Cena ${s.index}</span>
            <span class="text-[11px] text-slate-400">[${s.start_time.toFixed(1)}s]</span>
          </div>
          <button class="mt-2 w-full py-1.5 px-2 bg-indigo-600/30 hover:bg-indigo-600 text-indigo-200 hover:text-white rounded text-[11px] font-medium transition-colors regen-scene-img-btn" data-scene-id="${s.id}">
            🔄 Regenerar Imagem
          </button>
        </div>
      </div>
    `).join("");

    // Attach scene prompt edit listeners
    document.querySelectorAll(".scene-prompt-input").forEach(input => {
      input.addEventListener("change", (e) => {
        const sceneId = e.target.getAttribute("data-scene-id");
        const found = state.currentProject.scenes.find(sc => sc.id === sceneId);
        if (found) found.visual_prompt = e.target.value;
      });
    });

    // Attach single scene image regeneration
    document.querySelectorAll(".regen-scene-img-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const sceneId = btn.getAttribute("data-scene-id");
        btn.textContent = "⏳ Gerando...";
        btn.disabled = true;
        try {
          const res = await API.generateImages(state.currentProject.id, sceneId);
          state.currentProject = res;
          renderProjectState();
          showToast(`Cena ${sceneId} regenerada!`, "success");
        } catch (err) {
          showToast("Falha ao regenerar imagem", "error");
        }
      });
    });
  }

  function renderMetadata(meta) {
    // Titles
    const titlesContainer = document.getElementById("meta-titles-list");
    titlesContainer.innerHTML = meta.titles.map((t, i) => `
      <div class="flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-slate-800">
        <span class="text-sm font-semibold text-slate-200">${t}</span>
        <button class="text-xs px-2.5 py-1 bg-slate-800 hover:bg-indigo-600 text-slate-300 hover:text-white rounded transition-colors copy-btn" data-copy="${t}">
          📋 Copiar
        </button>
      </div>
    `).join("");

    // Description
    const descTextarea = document.getElementById("meta-description-text");
    descTextarea.value = meta.description;

    // Tags
    const tagsContainer = document.getElementById("meta-tags-list");
    tagsContainer.innerHTML = meta.tags.map(tag => `
      <span class="px-2.5 py-1 bg-indigo-950/60 text-indigo-300 border border-indigo-800/50 rounded-md text-xs font-mono">#${tag}</span>
    `).join("");

    // Copy handlers
    document.querySelectorAll(".copy-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const text = btn.getAttribute("data-copy");
        navigator.clipboard.writeText(text);
        showToast("Copiado para a área de transferência!", "success");
      });
    });
  }

  // Tab switching
  studioTabBtn.addEventListener("click", () => {
    state.activeTab = "studio";
    studioTabBtn.className = "px-4 py-2 text-sm font-semibold rounded-lg bg-indigo-600 text-white transition-colors";
    autopilotTabBtn.className = "px-4 py-2 text-sm font-semibold rounded-lg bg-slate-800 text-slate-400 hover:text-white transition-colors";
    studioView.classList.remove("hidden");
    autopilotView.classList.add("hidden");
  });

  autopilotTabBtn.addEventListener("click", () => {
    state.activeTab = "autopilot";
    autopilotTabBtn.className = "px-4 py-2 text-sm font-semibold rounded-lg bg-indigo-600 text-white transition-colors";
    studioTabBtn.className = "px-4 py-2 text-sm font-semibold rounded-lg bg-slate-800 text-slate-400 hover:text-white transition-colors";
    autopilotView.classList.remove("hidden");
    studioView.classList.add("hidden");
  });

  // Step Indicators Click
  stepIndicators.forEach(ind => {
    ind.addEventListener("click", () => {
      const stepNum = parseInt(ind.getAttribute("data-step"));
      setStep(stepNum);
    });
  });

  // New Project Button
  newProjectBtn.addEventListener("click", async () => {
    const topic = prompt("Digite o tema ou ideia inicial do vídeo:", "The Mysterious Wow! Signal");
    if (!topic) return;
    try {
      const proj = await API.createProject(topic, "shorts_9_16");
      state.currentProject = proj;
      await loadProjectsList();
      selectProject(proj.id);
      showToast("Novo projeto criado!", "success");
    } catch (e) {
      showToast("Falha ao criar projeto.", "error");
    }
  });

  projectSelect.addEventListener("change", (e) => {
    selectProject(e.target.value);
  });

  // ---------------- STEP 1: SCRIPT ACTION ----------------
  document.getElementById("btn-generate-script").addEventListener("click", async () => {
    const topic = document.getElementById("step1-topic").value.trim();
    if (!topic) {
      showToast("Selecione ou digite um tema primeiro.", "error");
      return;
    }
    const format = document.getElementById("step1-format").value;
    const tone = document.getElementById("step1-tone").value;

    const btn = document.getElementById("btn-generate-script");
    btn.innerHTML = `<span>⏳ Escrevendo Roteiro Detalhado com IA...</span>`;
    btn.disabled = true;

    try {
      if (!state.currentProject) {
        state.currentProject = await API.createProject(topic, format);
      }
      const proj = await API.generateScript(state.currentProject.id, {
        topic,
        video_format: format,
        tone,
        target_duration: format === "shorts_9_16" ? 45 : 180
      });
      state.currentProject = proj;
      renderProjectState();
      showToast("Roteiro estruturado gerado com sucesso!", "success");
    } catch (e) {
      showToast("Erro ao gerar roteiro: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>✨ Escrever Roteiro Estruturado com IA</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 2 & 3: AUDIO & ALIGN ACTION ----------------
  document.getElementById("btn-generate-audio").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const scriptText = document.getElementById("step1-script-preview").value.trim();
    const voiceId = document.getElementById("step2-voice-select").value;

    const btn = document.getElementById("btn-generate-audio");
    btn.innerHTML = `<span>🎙️ Sintetizando Voz & Mapeando Pausas...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.generateAudio(state.currentProject.id, {
        script_text: scriptText,
        voice_id: voiceId,
        rate: "+0%",
        pitch: "+0Hz"
      });
      state.currentProject = proj;
      renderProjectState();
      showToast("Áudio sintetizado e cenas alinhadas!", "success");
    } catch (e) {
      showToast("Erro na síntese de áudio: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>🎙️ Gerar Áudio & Alinhar Cenas</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 4: PROMPTS ACTION ----------------
  document.getElementById("btn-generate-prompts").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const stylePref = document.getElementById("step4-art-style").value;
    const btn = document.getElementById("btn-generate-prompts");
    btn.innerHTML = `<span>🎨 Criando Prompts Cinematográficos...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.generatePrompts(state.currentProject.id, {
        topic: state.currentProject.topic,
        style_preference: stylePref
      });
      state.currentProject = proj;
      renderProjectState();
      showToast("Prompts cinematográficos gerados!", "success");
    } catch (e) {
      showToast("Erro ao gerar prompts de cena: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>🎨 Gerar Prompts Personalizados</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 5: IMAGES ACTION ----------------
  document.getElementById("btn-generate-images").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const btn = document.getElementById("btn-generate-images");
    btn.innerHTML = `<span>🖼️ Gerando Todas as Ilustrações...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.generateImages(state.currentProject.id);
      state.currentProject = proj;
      renderProjectState();
      showToast("Todas as ilustrações foram geradas!", "success");
    } catch (e) {
      showToast("Erro ao gerar ilustrações: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>🖼️ Gerar Todas as Ilustrações</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 6: SUBTITLES ACTION ----------------
  document.getElementById("btn-generate-subtitles").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const style = document.getElementById("step6-style-select").value;
    const btn = document.getElementById("btn-generate-subtitles");
    btn.innerHTML = `<span>📝 Compilando Legendas Karaoke...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.generateSubtitles(state.currentProject.id, style);
      state.currentProject = proj;
      renderProjectState();
      showToast("Legendas interativas geradas!", "success");
    } catch (e) {
      showToast("Erro ao gerar legendas: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>📝 Compilar Legendas Interativas</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 7: RENDER VIDEO ACTION ----------------
  document.getElementById("btn-render-video").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const format = state.currentProject.video_format || "shorts_9_16";
    const subStyle = document.getElementById("step6-style-select").value || "hormozi";
    const bgmTrack = document.getElementById("step7-bgm-select").value || "cinematic";
    const bgmVol = parseFloat(document.getElementById("step7-bgm-volume").value) || 0.15;

    const btn = document.getElementById("btn-render-video");
    btn.innerHTML = `<span>🎬 Renderizando Vídeo Completo (Ken Burns + BGM + Legendas)...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.renderVideo(state.currentProject.id, {
        video_format: format,
        subtitle_style: subStyle,
        bgm_track: bgmTrack,
        bgm_volume: bgmVol
      });
      state.currentProject = proj;
      renderProjectState();
      showToast("Vídeo renderizado com sucesso!", "success");
    } catch (e) {
      showToast("Erro na renderização: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>🎬 Renderizar Vídeo Final</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 8: METADATA ACTION ----------------
  document.getElementById("btn-generate-metadata").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const btn = document.getElementById("btn-generate-metadata");
    btn.innerHTML = `<span>📈 Gerando Pacote de SEO...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.generateMetadata(state.currentProject.id);
      state.currentProject = proj;
      renderProjectState();
      showToast("Títulos, descrição e tags prontos!", "success");
    } catch (e) {
      showToast("Erro ao gerar metadados: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>📈 Gerar Pacote de SEO</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 9: THUMBNAIL ACTION ----------------
  document.getElementById("btn-generate-thumbnail").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const customText = document.getElementById("step9-custom-text").value.trim();
    const btn = document.getElementById("btn-generate-thumbnail");
    btn.innerHTML = `<span>🖼️ Sintetizando Thumbnail...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.generateThumbnail(state.currentProject.id, customText);
      state.currentProject = proj;
      renderProjectState();
      showToast("Thumbnail do YouTube gerada!", "success");
    } catch (e) {
      showToast("Erro ao gerar thumbnail: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>🖼️ Gerar Thumbnail</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- 1-CLICK AUTO-PILOT ACTION ----------------
  document.getElementById("btn-start-autopilot").addEventListener("click", async () => {
    let topic = document.getElementById("auto-topic").value.trim();
    const genreId = autoGenreSelect.value;
    const format = document.getElementById("auto-format").value;
    const voiceId = document.getElementById("auto-voice-select").value;
    const subStyle = document.getElementById("auto-style-select").value;
    const bgmTrack = document.getElementById("auto-bgm-select").value;
    const artStyle = document.getElementById("auto-art-style").value;

    const btn = document.getElementById("btn-start-autopilot");
    btn.disabled = true;
    btn.innerHTML = `<span>🚀 Auto-Pilot em Execução...</span>`;

    const progressContainer = document.getElementById("autopilot-progress-container");
    const progressBar = document.getElementById("autopilot-progress-bar");
    const statusText = document.getElementById("autopilot-status-text");
    const logsConsole = document.getElementById("autopilot-logs");
    
    progressContainer.classList.remove("hidden");
    logsConsole.innerHTML = "";

    // If topic is empty, generate one from the genre first
    if (!topic) {
      try {
        const topData = await API.generateTopics(genreId, format);
        if (topData.topics && topData.topics.length > 0) {
          topic = topData.topics[0].topic;
          document.getElementById("auto-topic").value = topic;
        } else {
          topic = "The Mysterious Wow Signal Anomaly";
        }
      } catch (e) {
        topic = "The Mysterious Wow Signal Anomaly";
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
      
      // Poll progress every 1.5s
      const poll = setInterval(async () => {
        try {
          const updated = await API.getProject(proj.id);
          state.currentProject = updated;
          progressBar.style.width = `${updated.progress || 10}%`;
          statusText.textContent = `Status: ${updated.status} (${updated.progress}%)`;
          
          if (updated.logs) {
            logsConsole.innerHTML = updated.logs.map(l => `<div class="py-0.5 font-mono text-xs text-slate-300">${l}</div>`).join("");
            logsConsole.scrollTop = logsConsole.scrollHeight;
          }

          if (updated.status === "completed" || updated.status === "error") {
            clearInterval(poll);
            btn.disabled = false;
            btn.innerHTML = `<span>🚀 Iniciar Produção Completa em 1-Clique</span>`;
            if (updated.status === "completed") {
              showToast("🎉 Vídeo gerado com sucesso!", "success");
              studioTabBtn.click();
              renderProjectState();
            } else {
              showToast("Auto-Pilot concluído com avisos. Veja os logs.", "error");
            }
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 1500);

    } catch (e) {
      showToast("Falha ao iniciar Auto-Pilot: " + e.message, "error");
      btn.disabled = false;
      btn.innerHTML = `<span>🚀 Iniciar Produção Completa em 1-Clique</span>`;
    }
  });

  // Initialize
  initConfig();
});
