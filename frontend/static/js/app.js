import { API } from "./api.js";

document.addEventListener("DOMContentLoaded", () => {
  const state = {
    currentProject: null,
    activeTab: "studio", // studio or autopilot
    currentStep: 1,
    voices: [],
    formats: [],
    pollTimer: null
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

  // Load Voices & Formats
  async function initConfig() {
    try {
      const [voicesData, formatsData] = await Promise.all([
        API.getVoices(),
        API.getFormats()
      ]);
      state.voices = voicesData.voices || [];
      state.formats = formatsData.formats || [];

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

      loadProjectsList();
    } catch (e) {
      console.error("Config load error:", e);
      showToast("Error loading config from backend.", "error");
    }
  }

  async function loadProjectsList() {
    try {
      const data = await API.getProjects();
      projectSelect.innerHTML = `<option value="">-- Select or Create Project --</option>` +
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
      showToast("Error opening project.", "error");
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
      container.innerHTML = `<p class="text-slate-400 text-sm">Generate audio first to detect and align scenes.</p>`;
      gallery.innerHTML = `<p class="text-slate-400 text-sm">Generate scene prompts first.</p>`;
      return;
    }

    // Render Scene Prompts
    container.innerHTML = scenes.map((s, idx) => `
      <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col gap-2">
        <div class="flex items-center justify-between text-xs text-indigo-400 font-mono">
          <span>Scene ${s.index} [${s.start_time.toFixed(1)}s - ${s.end_time.toFixed(1)}s] (${s.duration.toFixed(1)}s)</span>
          <span class="text-slate-500 uppercase">${s.motion_type}</span>
        </div>
        <p class="text-xs text-slate-300 italic font-sans">"${s.speech_text}"</p>
        <div class="mt-1">
          <label class="text-[11px] text-slate-400 font-medium">Visual Prompt:</label>
          <textarea class="w-full text-xs p-2 rounded bg-slate-950 border border-slate-700 text-slate-200 scene-prompt-input font-mono" data-scene-id="${s.id}" rows="2">${s.visual_prompt || ""}</textarea>
        </div>
      </div>
    `).join("");

    // Render Images Gallery
    gallery.innerHTML = scenes.map((s, idx) => `
      <div class="relative group rounded-xl overflow-hidden border border-slate-800 bg-slate-950 flex flex-col">
        <div class="aspect-[9/16] w-full bg-slate-900 flex items-center justify-center overflow-hidden">
          ${s.image_url 
            ? `<img src="${s.image_url}" alt="Scene ${s.index}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />`
            : `<div class="text-center p-4"><span class="text-xs text-slate-500">Image not generated</span></div>`
          }
        </div>
        <div class="p-3 bg-slate-900/90 flex flex-col gap-1 text-xs">
          <div class="flex justify-between items-center">
            <span class="font-mono text-indigo-400 font-semibold">Scene ${s.index}</span>
            <span class="text-[11px] text-slate-400">[${s.start_time.toFixed(1)}s]</span>
          </div>
          <button class="mt-2 w-full py-1.5 px-2 bg-indigo-600/30 hover:bg-indigo-600 text-indigo-200 hover:text-white rounded text-[11px] font-medium transition-colors regen-scene-img-btn" data-scene-id="${s.id}">
            🔄 Regenerate Image
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
        btn.textContent = "⏳ Generating...";
        btn.disabled = true;
        try {
          const res = await API.generateImages(state.currentProject.id, sceneId);
          state.currentProject = res;
          renderProjectState();
          showToast(`Scene ${sceneId} regenerated!`, "success");
        } catch (err) {
          showToast("Failed to regenerate image", "error");
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
          📋 Copy
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
        showToast("Copied to clipboard!", "success");
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

    // Niche preset buttons
    document.querySelectorAll(".niche-preset-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const topic = btn.getAttribute("data-topic");
        const tone = btn.getAttribute("data-tone");
        document.getElementById("step1-topic").value = topic;
        document.getElementById("step1-tone").value = tone;
        showToast(`Loaded preset: ${topic}`, "info");
      });
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
    const topic = prompt("Enter the video topic / idea:", "The Unexplained Mystery of Deep Ocean Sounds");
    if (!topic) return;
    try {
      const proj = await API.createProject(topic, "shorts_9_16");
      state.currentProject = proj;
      await loadProjectsList();
      selectProject(proj.id);
      showToast("New project created!", "success");
    } catch (e) {
      showToast("Failed to create project.", "error");
    }
  });

  projectSelect.addEventListener("change", (e) => {
    selectProject(e.target.value);
  });

  // ---------------- STEP 1: SCRIPT ACTION ----------------
  document.getElementById("btn-generate-script").addEventListener("click", async () => {
    const topic = document.getElementById("step1-topic").value.trim();
    if (!topic) {
      showToast("Please enter a topic.", "error");
      return;
    }
    const format = document.getElementById("step1-format").value;
    const tone = document.getElementById("step1-tone").value;
    const duration = parseInt(document.getElementById("step1-duration").value);

    const btn = document.getElementById("btn-generate-script");
    btn.innerHTML = `<span>⏳ Writing Viral Script...</span>`;
    btn.disabled = true;

    try {
      if (!state.currentProject) {
        state.currentProject = await API.createProject(topic, format);
      }
      const proj = await API.generateScript(state.currentProject.id, {
        topic,
        video_format: format,
        tone,
        target_duration: duration
      });
      state.currentProject = proj;
      renderProjectState();
      showToast("Script generated successfully!", "success");
    } catch (e) {
      showToast("Error generating script: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>✨ Generate AI Script</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 2 & 3: AUDIO & ALIGN ACTION ----------------
  document.getElementById("btn-generate-audio").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const scriptText = document.getElementById("step1-script-preview").value.trim();
    const voiceId = document.getElementById("step2-voice-select").value;

    const btn = document.getElementById("btn-generate-audio");
    btn.innerHTML = `<span>🎙️ Synthesizing Voice & Extracting Timestamps...</span>`;
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
      showToast("Audio synthesized and scenes aligned!", "success");
    } catch (e) {
      showToast("Error in audio synthesis: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>🎙️ Generate Audio & Timestamps</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 4: PROMPTS ACTION ----------------
  document.getElementById("btn-generate-prompts").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const stylePref = document.getElementById("step4-art-style").value;
    const btn = document.getElementById("btn-generate-prompts");
    btn.innerHTML = `<span>🎨 Generating Visual Prompts...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.generatePrompts(state.currentProject.id, {
        topic: state.currentProject.topic,
        style_preference: stylePref
      });
      state.currentProject = proj;
      renderProjectState();
      showToast("Scene visual prompts generated!", "success");
    } catch (e) {
      showToast("Error generating scene prompts: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>🎨 Generate Scene Prompts</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 5: IMAGES ACTION ----------------
  document.getElementById("btn-generate-images").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const btn = document.getElementById("btn-generate-images");
    btn.innerHTML = `<span>🖼️ Generating All Scene Illustrations...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.generateImages(state.currentProject.id);
      state.currentProject = proj;
      renderProjectState();
      showToast("All illustrations generated!", "success");
    } catch (e) {
      showToast("Error generating illustrations: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>🖼️ Generate All Illustrations</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 6: SUBTITLES ACTION ----------------
  document.getElementById("btn-generate-subtitles").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const style = document.getElementById("step6-style-select").value;
    const btn = document.getElementById("btn-generate-subtitles");
    btn.innerHTML = `<span>📝 Compiling Karaoke Subtitles...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.generateSubtitles(state.currentProject.id, style);
      state.currentProject = proj;
      renderProjectState();
      showToast("Interactive karaoke subtitles generated!", "success");
    } catch (e) {
      showToast("Error generating subtitles: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>📝 Build Interactive Subtitles</span>`;
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
    btn.innerHTML = `<span>🎬 Rendering Full Video (Ken Burns + BGM + Subtitles)...</span>`;
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
      showToast("Video rendered successfully!", "success");
    } catch (e) {
      showToast("Rendering error: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>🎬 Render Final Video</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 8: METADATA ACTION ----------------
  document.getElementById("btn-generate-metadata").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const btn = document.getElementById("btn-generate-metadata");
    btn.innerHTML = `<span>📈 Generating SEO Package...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.generateMetadata(state.currentProject.id);
      state.currentProject = proj;
      renderProjectState();
      showToast("SEO Titles, Description and Tags ready!", "success");
    } catch (e) {
      showToast("Error generating metadata: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>📈 Generate SEO & Titles</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- STEP 9: THUMBNAIL ACTION ----------------
  document.getElementById("btn-generate-thumbnail").addEventListener("click", async () => {
    if (!state.currentProject) return;
    const customText = document.getElementById("step9-custom-text").value.trim();
    const btn = document.getElementById("btn-generate-thumbnail");
    btn.innerHTML = `<span>🖼️ Synthesizing Thumbnail...</span>`;
    btn.disabled = true;

    try {
      const proj = await API.generateThumbnail(state.currentProject.id, customText);
      state.currentProject = proj;
      renderProjectState();
      showToast("YouTube Thumbnail generated!", "success");
    } catch (e) {
      showToast("Error generating thumbnail: " + e.message, "error");
    } finally {
      btn.innerHTML = `<span>🖼️ Generate High-CTR Thumbnail</span>`;
      btn.disabled = false;
    }
  });

  // ---------------- 1-CLICK AUTO-PILOT ACTION ----------------
  document.getElementById("btn-start-autopilot").addEventListener("click", async () => {
    const topic = document.getElementById("auto-topic").value.trim();
    if (!topic) {
      showToast("Please enter a topic.", "error");
      return;
    }
    const format = document.getElementById("auto-format").value;
    const voiceId = document.getElementById("auto-voice-select").value;
    const subStyle = document.getElementById("auto-style-select").value;
    const bgmTrack = document.getElementById("auto-bgm-select").value;
    const artStyle = document.getElementById("auto-art-style").value;

    const btn = document.getElementById("btn-start-autopilot");
    btn.disabled = true;
    btn.innerHTML = `<span>🚀 Auto-Pilot Running...</span>`;

    const progressContainer = document.getElementById("autopilot-progress-container");
    const progressBar = document.getElementById("autopilot-progress-bar");
    const statusText = document.getElementById("autopilot-status-text");
    const logsConsole = document.getElementById("autopilot-logs");
    
    progressContainer.classList.remove("hidden");
    logsConsole.innerHTML = "";

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
            btn.innerHTML = `<span>🚀 Launch Complete 1-Click Video Production</span>`;
            if (updated.status === "completed") {
              showToast("🎉 Auto-Pilot Video Generation Finished!", "success");
              // Switch to studio view to inspect/download
              studioTabBtn.click();
              renderProjectState();
            } else {
              showToast("Auto-Pilot completed with errors. Check logs.", "error");
            }
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 1500);

    } catch (e) {
      showToast("Auto-Pilot launch failed: " + e.message, "error");
      btn.disabled = false;
      btn.innerHTML = `<span>🚀 Launch Complete 1-Click Video Production</span>`;
    }
  });

  // Initialize
  initConfig();
});
