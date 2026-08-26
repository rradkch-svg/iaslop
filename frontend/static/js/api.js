const API_BASE = "";

export const API = {
  async getVoices() {
    const res = await fetch(`${API_BASE}/api/voices`);
    return await res.json();
  },

  async getFormats() {
    const res = await fetch(`${API_BASE}/api/formats`);
    return await res.json();
  },

  async getGenres() {
    const res = await fetch(`${API_BASE}/api/genres`);
    return await res.json();
  },

  async generateTopics(genreId, videoFormat = "shorts_9_16") {
    const res = await fetch(`${API_BASE}/api/topics/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ genre_id: genreId, video_format: videoFormat })
    });
    return await res.json();
  },

  async getApiKeys() {
    const res = await fetch(`${API_BASE}/api/settings/keys`);
    return await res.json();
  },

  async saveApiKeys(keys) {
    const res = await fetch(`${API_BASE}/api/settings/keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(keys)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || "Failed to save key");
    return data;
  },

  async getProjects() {
    const res = await fetch(`${API_BASE}/api/projects`);
    return await res.json();
  },

  async createProject(topic, video_format = "shorts_9_16") {
    const res = await fetch(`${API_BASE}/api/projects/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, video_format })
    });
    return await res.json();
  },

  async getProject(id) {
    const res = await fetch(`${API_BASE}/api/projects/${id}`);
    if (!res.ok) throw new Error("Project not found");
    return await res.json();
  },

  // Step 1: Script
  async generateScript(projectId, { topic, video_format, tone, target_duration, user_notes }) {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/script`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, video_format, tone, target_duration, user_notes })
    });
    return await res.json();
  },

  // Step 2 & 3: Audio & Timestamps
  async generateAudio(projectId, { script_text, voice_id, rate, pitch }) {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/audio`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, script_text, voice_id, rate, pitch })
    });
    return await res.json();
  },

  // Step 4: Prompts
  async generatePrompts(projectId, { topic, style_preference }) {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/prompts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, topic, style_preference })
    });
    return await res.json();
  },

  // Step 5: Images
  async generateImages(projectId, sceneId = null, promptOverride = null) {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/images`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: projectId,
        scene_id: sceneId,
        prompt_override: promptOverride
      })
    });
    return await res.json();
  },

  // Step 6: Subtitles
  async generateSubtitles(projectId, style = "hormozi") {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/subtitles?style=${style}`, {
      method: "POST"
    });
    return await res.json();
  },

  // Step 7: Render Video
  async renderVideo(projectId, { video_format, subtitle_style, bgm_track, bgm_volume }) {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: projectId,
        video_format,
        subtitle_style,
        bgm_track,
        bgm_volume
      })
    });
    return await res.json();
  },

  // Step 8: Metadata
  async generateMetadata(projectId) {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/metadata`, {
      method: "POST"
    });
    return await res.json();
  },

  // Step 9: Thumbnail
  async generateThumbnail(projectId, customText = null) {
    let url = `${API_BASE}/api/projects/${projectId}/thumbnail`;
    if (customText) url += `?custom_text=${encodeURIComponent(customText)}`;
    const res = await fetch(url, { method: "POST" });
    return await res.json();
  },

  // 1-Click AutoPilot
  async triggerAutoPilot(data) {
    const res = await fetch(`${API_BASE}/api/autopilot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    return await res.json();
  }
};
